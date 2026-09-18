import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from trolley.application import queries


@pytest.mark.parametrize("fails", [False, True])
def test_audit_failure_does_not_mask_query(monkeypatch, fails):
    execution = SimpleNamespace(
        id="test-execution", save=AsyncMock(side_effect=RuntimeError("audit"))
    )
    monkeypatch.setattr(queries, "require_target", AsyncMock(return_value=object()))
    monkeypatch.setattr(
        queries, "configured_targets", lambda _: {"db": SimpleNamespace(configuration={})}
    )
    monkeypatch.setattr(queries.QueryExecution, "create", AsyncMock(return_value=execution))
    run = AsyncMock(return_value={"rows": [], "has_more": False})
    if fails:
        run.side_effect = RuntimeError("secret database diagnostics")
    monkeypatch.setattr(queries.database, "execute", run)
    context = SimpleNamespace(user_id="user", api_key_id="key")
    if fails:
        with pytest.raises(ValueError, match="Query failed") as caught:
            asyncio.run(queries.query_target(None, context, "db", "SELECT 1"))
        assert "secret" not in str(caught.value)
    else:
        result = asyncio.run(queries.query_target(None, context, "db", "SELECT 1"))
        assert result["rows"] == []
        assert "audit_warning" in result
    assert run.await_count == 1
