import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from trolley.application import targets
from trolley.config import Settings
from trolley.connectors import database
from trolley.targets import load_targets


def configured_targets() -> dict:
    return {
        "replica": {
            "kind": "postgresql",
            "url": "postgresql://reader:secret@127.0.0.1:5433/litellm",
            "timeout": 3,
        }
    }


def test_loads_targets_without_exposing_configuration() -> None:
    settings = Settings(
        targets=configured_targets(),
        admin_emails=frozenset({"root@example.com"}),
    )

    definitions = load_targets(settings.targets)
    assert definitions["replica"].configuration["timeout"] == 3
    assert asyncio.run(targets.list_targets(settings)) == [
        {"name": "replica", "kind": "postgresql"}
    ]
    assert "secret" not in str(asyncio.run(targets.list_targets(settings)))


def test_rejects_postgresql_target_without_url() -> None:
    with pytest.raises(ValueError, match="needs 'url'"):
        load_targets({"broken": {"kind": "postgresql"}})


def test_rejects_non_postgresql_target() -> None:
    with pytest.raises(ValueError, match="unsupported target kind"):
        load_targets({"api": {"kind": "http", "base_url": "https://example.com"}})


def test_database_connection_reports_postgresql_version(monkeypatch) -> None:
    connection = AsyncMock()
    connection.fetchval.side_effect = [1, "17.11 (Debian 17.11-1.pgdg13+2)"]

    with patch("trolley.connectors.database.asyncpg.connect", AsyncMock(return_value=connection)):
        result = asyncio.run(
            database.test_connection({"url": "postgresql://example.invalid/test", "timeout": 3})
        )

    assert result["status"] == "connected"
    assert result["server_version"] == "17.11 (Debian 17.11-1.pgdg13+2)"
    assert connection.fetchval.await_args_list[0].args == ("SELECT 1",)
    assert connection.fetchval.await_args_list[1].args == ("SHOW server_version",)
    connection.close.assert_awaited_once()
