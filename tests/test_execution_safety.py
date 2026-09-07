import asyncio
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trolley.application.execution import execute_operation
from trolley.application.operations import create_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.connectors.database import execute
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Execution, User
from trolley.serialization import json_value


def test_result_serialization_and_audit_failures(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://example/test"}},
    )
    connector = AsyncMock(
        return_value={"rows": [{"date": datetime(2026, 1, 1), "amount": Decimal("1.2300")}]}
    )
    monkeypatch.setattr("trolley.application.execution.database.execute", connector)
    with TestClient(create_app(settings)) as client:

        async def scenario():
            await create_operation("report", "db", {"sql": "select 1"})
            root = await User.get(email="root@example.com")
            context = AuthContext(
                user_id=str(root.id), api_key_id=str(uuid4()), role=UserRole.ADMIN
            )
            result = await execute_operation("report", {}, context)
            record = await Execution.get(id=result["execution_id"])
            assert (
                record.result
                == result["result"]
                == {
                    "rows": [{"date": "2026-01-01T00:00:00", "amount": "1.2300"}],
                    "has_more": False,
                    "next_cursor": None,
                }
            )
            assert record.status == "succeeded"

            connector.return_value = {"rows": [{"unsupported": object()}]}
            with pytest.raises(ValueError, match="Unsupported result type"):
                await execute_operation("report", {}, context)
            failed = await Execution.get(status="failed")
            assert failed.result is None
            assert failed.finished_at is not None

            original_save = Execution.save

            async def broken_finalization(self, *args, **kwargs):
                if self.status != "running":
                    raise RuntimeError("catalog unavailable")
                return await original_save(self, *args, **kwargs)

            monkeypatch.setattr(Execution, "save", broken_finalization)
            connector.return_value = {"status": "UPDATE 1"}
            result = await execute_operation("report", {}, context)
            assert result["status"] == "succeeded"
            assert "do not retry" in result["audit_warning"]
            connector.side_effect = ValueError("original query failure")
            with pytest.raises(ValueError, match="original query failure"):
                await execute_operation("report", {}, context)

        client.portal.call(scenario)


def test_connector_limits_and_timeout(monkeypatch):
    connection = MagicMock()
    connection.transaction.return_value = AsyncMock()
    connection.close = AsyncMock()
    connection.execute = AsyncMock(return_value="UPDATE 1")
    monkeypatch.setattr(
        "trolley.connectors.database.asyncpg.connect", AsyncMock(return_value=connection)
    )

    async def rows():
        for index in range(3):
            yield {"index": index, "amount": Decimal("1.50")}

    connection.cursor.side_effect = lambda *args, **kwargs: rows()
    config = {"url": "postgresql://example/test"}

    async def scenario():
        result = await execute(config, {"sql": "select 1"}, {})
        assert len(result["rows"]) == 3
        assert result["rows"][0]["amount"] == "1.50"
        assert result["has_more"] is False
        paged = await execute(
            config,
            {"sql": "select index, amount from logs", "pagination": {"order_by": ["index"]}},
            {},
            page_size=2,
            offset=5,
        )
        assert paged == {
            "rows": [{"index": 0, "amount": "1.50"}, {"index": 1, "amount": "1.50"}],
            "has_more": True,
            "next_cursor": None,
        }
        sql, limit, offset = connection.cursor.call_args.args
        assert 'ORDER BY "index" ASC LIMIT $1::bigint OFFSET $2::bigint' in sql
        assert (limit, offset) == (3, 5)
        assert connection.transaction.call_args.kwargs == {"readonly": True}
        with pytest.raises(ValueError, match="row limit"):
            await execute({**config, "max_rows": 2}, {"sql": "select 1"}, {})
        with pytest.raises(ValueError, match="byte limit"):
            await execute({**config, "max_result_bytes": 12}, {"sql": "select 1"}, {})
        transaction = connection.transaction.return_value
        assert transaction.__aexit__.await_args.args[0] is ValueError
        assert await execute(config, {"sql": "update example", "fetch": False}, {}) == {
            "status": "UPDATE 1"
        }

        async def slow():
            await asyncio.sleep(1)
            yield {"id": 1}

        connection.cursor.side_effect = lambda *args, **kwargs: slow()
        with pytest.raises(ValueError, match="timed out"):
            await execute({**config, "query_timeout": 0.01}, {"sql": "select 1"}, {})
        assert connection.close.await_count == 6

    asyncio.run(scenario())


def test_json_value_nested_types():
    assert json_value({"values": [Decimal("0.123456789123456789"), b"abc", float("inf")]}) == {
        "values": ["0.123456789123456789", {"base64": "YWJj"}, "inf"]
    }
