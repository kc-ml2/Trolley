from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from trolley.application.targets import (
    create_target,
)
from trolley.application.targets import (
    test_target_connection as check_target_connection,
)
from trolley.config import Settings
from trolley.main import create_app


def test_postgresql_target_connection_returns_safe_result(tmp_path, monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
    )
    connector = AsyncMock(
        return_value={
            "status": "connected",
            "latency_ms": 12.5,
            "server_version": "16.3",
        }
    )
    monkeypatch.setattr("trolley.application.targets.database.test_connection", connector)

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            await create_target(
                "payments-db",
                "postgresql",
                {"timeout": 3},
                "PAYMENTS_DATABASE_URL",
            )
            result = await check_target_connection("payments-db")
            assert result == {
                "target": "payments-db",
                "kind": "postgresql",
                "status": "connected",
                "latency_ms": 12.5,
                "server_version": "16.3",
            }
            assert "PAYMENTS_DATABASE_URL" not in str(result)
            connector.assert_awaited_once_with({"timeout": 3}, "PAYMENTS_DATABASE_URL")

        client.portal.call(scenario)
