import asyncio
import gzip
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.mcpserver.exceptions import ToolError

from trolley.application.operations import create_operation
from trolley.auth.api_keys import create_api_key
from trolley.config import ExportSettings, Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import ExportJob, OperationGrant, User


def test_file_operation_dispatch_and_status(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://unused/test"}},
        exports=ExportSettings(directory=str(tmp_path / "exports")),
    )

    async def write_file(configuration, definition, arguments, path, limits):
        assert arguments == {"trolley_caller_email": "member@example.com"}
        with gzip.open(path, "wb") as stream:
            stream.write(b'{"n":1}\n')
        return 1, 8, path.stat().st_size

    writer = AsyncMock(side_effect=write_file)
    inline = AsyncMock(return_value={"rows": [{"n": 1}]})
    monkeypatch.setattr("trolley.application.exports.export_jsonl", writer)
    monkeypatch.setattr("trolley.application.execution.database.execute", inline)
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario():
            server = app.routes[-1].app.state.mcp_server
            member = await User.create(email="member@example.com", name="Member")
            other = await User.create(email="other@example.com", name="Other")
            file_op = await create_operation(
                "get_my_weekly_data",
                "db",
                {
                    "data_scope": "caller",
                    "source": {"schema": "public", "relation": "logs"},
                    "columns": ["id"],
                    "ownership": {"column": "email", "identity": "authenticated_user.email"},
                    "output": "file",
                },
                access="restricted",
            )
            from trolley.persistence.models import Operation

            operation = await Operation.get(id=file_op["id"])
            await OperationGrant.create(user=member, operation=operation)
            await create_operation("summary", "db", {"data_scope": "shared", "sql": "select 1"})
            await server.registry.load()

            async def login(user):
                _, secret = await create_api_key(user, "test")
                token = await TrolleyTokenVerifier(settings.admin_emails).verify_token(secret)
                return auth_context_var.set(AuthenticatedUser(token))

            async def call(tool_name, **kwargs):
                return await server._tool_manager.get_tool(tool_name).fn(**kwargs)

            ctx = await login(member)
            try:
                names = {t.name for t in await server.list_tools()}
                assert "get_my_weekly_data" in names
                assert "get_execution" in names
                assert not {"start_export", "get_my_export"} & names
                # Both public entry points dispatch to file generation without inline SQL.
                for tool_name, args in (
                    ("get_my_weekly_data", {}),
                    ("execute", {"name": "get_my_weekly_data"}),
                ):
                    started = await call(tool_name, **args)
                    assert started["output"] == "file"
                    assert started["status"] == "running"
                    await asyncio.gather(*list(server.export_manager.tasks))
                    status = await call("get_execution", execution_id=started["execution_id"])
                    assert status["status"] == "succeeded"
                    assert status["download_url"]
                    assert "rows" not in status
                inline.assert_not_awaited()
                assert writer.await_count == 2
                assert await ExportJob.all().count() == 2
                with pytest.raises(ToolError, match="pagination"):
                    await call("execute", name="get_my_weekly_data", page_size=10)
                with pytest.raises(ToolError, match="Server-bound"):
                    await call(
                        "execute",
                        name="get_my_weekly_data",
                        arguments={"trolley_caller_email": other.email},
                    )
                result = await call("execute", name="summary")
                status = await call("get_execution", execution_id=result["execution_id"])
                assert status["output"] == "inline"
                assert status["status"] == "succeeded"
                assert "result" not in status
                await OperationGrant.filter(user=member).delete()
                with pytest.raises(ToolError, match="access denied"):
                    await call("get_execution", execution_id=started["execution_id"])
            finally:
                auth_context_var.reset(ctx)
            for user in (other, await User.get(role=UserRole.ADMIN)):
                ctx = await login(user)
                try:
                    with pytest.raises(ToolError, match="not found"):
                        await call("get_execution", execution_id=started["execution_id"])
                finally:
                    auth_context_var.reset(ctx)

        client.portal.call(scenario)


def test_file_output_validation():
    from trolley.validation.operations import DEFAULT_INPUT_SCHEMA, validate_definition

    for definition, message in (
        ({"output": "csv"}, "output must"),
        ({"output": "file", "fetch": False}, "requires fetch"),
        ({"output": "file", "pagination": {"order_by": ["id"]}}, "pagination"),
        ({"export": True}, "instead of"),
    ):
        with pytest.raises(ValueError, match=message):
            validate_definition(
                None,
                {"data_scope": "shared", "sql": "select 1", **definition},
                DEFAULT_INPUT_SCHEMA,
            )
    for output in ("inline", "file"):
        validate_definition(
            None,
            {"data_scope": "shared", "sql": "select 1", "output": output},
            DEFAULT_INPUT_SCHEMA,
        )
