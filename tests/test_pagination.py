from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trolley.application import groups
from trolley.application.execution import execute_operation
from trolley.application.operations import create_operation, update_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import ExecutionPage, PageCursor, User


def test_paginated_operation_uses_bound_opaque_cursor(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://example/test"}},
    )
    connector = AsyncMock(
        side_effect=[
            {"rows": [{"id": 1}, {"id": 2}], "has_more": True, "next_cursor": None},
            {"rows": [{"id": 3}], "has_more": False, "next_cursor": None},
        ]
    )
    monkeypatch.setattr("trolley.application.execution.database.execute", connector)

    with TestClient(create_app(settings)) as client:

        async def scenario():
            await create_operation(
                "logs",
                "db",
                {
                    "sql": "select id from logs where kind = $1",
                    "parameters": ["kind"],
                    "pagination": {"order_by": ["id"]},
                },
                input_schema={
                    "type": "object",
                    "properties": {"kind": {"type": "string"}},
                    "required": ["kind"],
                    "additionalProperties": False,
                },
            )
            root = await User.get(email="root@example.com")
            context = AuthContext(
                user_id=str(root.id), api_key_id=str(uuid4()), role=UserRole.ADMIN
            )
            first = await execute_operation("logs", {"kind": "error"}, context, page_size=2)
            assert first["result"]["has_more"] is True
            cursor = first["result"]["next_cursor"]
            assert cursor and cursor != "2"
            saved = await PageCursor.get(id=cursor)
            assert saved.offset == 2
            assert saved.page_size == 2
            audit = await ExecutionPage.get(execution_id=first["execution_id"])
            assert (audit.offset, audit.page_size, audit.input_cursor) == (0, 2, None)
            assert audit.query_fingerprint == saved.fingerprint

            with pytest.raises(ValueError, match="same page_size"):
                await execute_operation(
                    "logs", {"kind": "error"}, context, page_size=1, cursor=cursor
                )
            with pytest.raises(ValueError, match="conditions changed"):
                await execute_operation(
                    "logs", {"kind": "warning"}, context, page_size=2, cursor=cursor
                )
            other = await User.create(email="other@example.com", name="Other")
            other_context = AuthContext(
                user_id=str(other.id), api_key_id=str(uuid4()), role=UserRole.USER
            )
            with pytest.raises(ValueError, match="conditions changed"):
                await execute_operation(
                    "logs", {"kind": "error"}, other_context, page_size=2, cursor=cursor
                )

            second = await execute_operation(
                "logs", {"kind": "error"}, context, page_size=2, cursor=cursor
            )
            assert second["result"] == {
                "rows": [{"id": 3}],
                "has_more": False,
                "next_cursor": None,
            }
            audit = await ExecutionPage.get(execution_id=second["execution_id"])
            assert (audit.offset, audit.page_size) == (2, 2)
            assert str(audit.input_cursor) == cursor

            saved.expires_at = datetime.now(UTC) - timedelta(seconds=1)
            await saved.save()
            with pytest.raises(ValueError, match="expired"):
                await execute_operation("logs", {"kind": "error"}, context, cursor=cursor)
            saved.expires_at = datetime.now(UTC) + timedelta(minutes=1)
            await saved.save()
            assert connector.await_args_list[0].kwargs == {"offset": 0, "page_size": 2}
            assert connector.await_args_list[1].kwargs == {"offset": 2, "page_size": 2}

            with pytest.raises(ValueError, match="does not support"):
                await create_operation("single", "db", {"sql": "select 1"})
                await execute_operation("single", {}, context, page_size=10)

            await groups.create_group("readers")
            await groups.set_user_groups(other.email, ["readers"])
            await update_operation("logs", access="restricted")
            await groups.grant_group_operation("readers", "logs")
            connector.side_effect = None
            connector.return_value = {"rows": [{"id": 1}], "has_more": True}
            granted = await execute_operation("logs", {"kind": "error"}, other_context)
            await groups.revoke_group_operation("readers", "logs")
            before = connector.await_count
            with pytest.raises(PermissionError, match="denied"):
                await execute_operation(
                    "logs",
                    {"kind": "error"},
                    other_context,
                    cursor=granted["result"]["next_cursor"],
                )
            assert connector.await_count == before

            await update_operation(
                "logs",
                definition={
                    "sql": "select id from logs where kind = $1 and id > 0",
                    "parameters": ["kind"],
                    "pagination": {"order_by": ["id"]},
                },
            )
            with pytest.raises(ValueError, match="conditions changed"):
                await execute_operation(
                    "logs", {"kind": "error"}, context, page_size=2, cursor=cursor
                )

        client.portal.call(scenario)


def test_pagination_definition_validation(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://example/test"}},
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            invalid = [
                {"sql": "select 1", "pagination": {"order_by": []}},
                {"sql": "select 1", "pagination": {"order_by": ["bad-name"]}},
                {
                    "sql": "delete from logs",
                    "fetch": False,
                    "pagination": {"order_by": ["id"]},
                },
            ]
            for index, definition in enumerate(invalid):
                with pytest.raises(ValueError, match="[Pp]agination"):
                    await create_operation(f"invalid_{index}", "db", definition)

        client.portal.call(scenario)
