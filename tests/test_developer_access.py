from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.mcpserver.exceptions import ToolError

from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import (
    Group,
    GroupMembership,
    GroupTargetGrant,
    Operation,
    QueryExecution,
    Target,
    TargetGrant,
    User,
)


def test_developer_exploration_and_admin_publication(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://reader:secret@localhost/db"}},
    )
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario():
            server = app.routes[-1].app.state.mcp_server
            dev = await User.create(email="dev@example.com", name="Dev", role=UserRole.DEVELOPER)
            member = await User.create(email="user@example.com", name="User")
            root = await User.get(email="root@example.com")
            target = await Target.get(name="db")

            async def login(user):
                _, secret = await create_api_key(user, "test")
                token = await TrolleyTokenVerifier(settings.admin_emails).verify_token(secret)
                return auth_context_var.set(AuthenticatedUser(token))

            async def call(tool_name, **kwargs):
                return await server._tool_manager.get_tool(tool_name).fn(**kwargs)

            ctx = await login(root)
            try:
                await call("set_target_access", name="db", email=dev.email, allowed=True)
                assert len(await call("list_targets")) == 1
            finally:
                auth_context_var.reset(ctx)

            ctx = await login(dev)
            try:
                names = {t.name for t in await server.list_tools()}
                assert {
                    "query_target",
                    "get_target_schema",
                    "execute",
                    "get_target_notes",
                    "update_target_notes",
                } <= names
                notes = await call("get_target_notes", name="db")
                assert notes["version"] == 0
                updated = await call(
                    "update_target_notes",
                    name="db",
                    expected_version=0,
                    data_notes="Content may be an array",
                )
                assert updated["version"] == 1
                assert not {"create_operation", "update_operation", "grant_operation"} & names
                for name, args in (
                    ("create_operation", {}),
                    ("set_user_role", {"email": dev.email, "role": UserRole.ADMIN}),
                    ("set_target_access", {"name": "db", "allowed": True, "email": dev.email}),
                ):
                    with pytest.raises(ToolError, match="scope"):
                        await call(name, **args)
                assert len(await call("list_targets")) == 1
                with patch(
                    "trolley.connectors.database.execute", new_callable=AsyncMock
                ) as execute:
                    execute.return_value = {
                        "rows": [{"n": 7}],
                        "has_more": False,
                        "next_cursor": None,
                    }
                    result = await call("query_target", name="db", sql="SELECT $1 AS n", params=[7])
                    assert result["rows"] == [{"n": 7}]
                    assert execute.call_args.kwargs["readonly"] is True
                    assert execute.call_args.args[2] == {"0": 7}
                    assert await Operation.all().count() == 0
                    record = await QueryExecution.get(id=result["execution_id"])
                    assert record.status == "succeeded"
                    assert str(record.requested_by) == str(dev.id)
                    execute.side_effect = RuntimeError("secret connection details")
                    with pytest.raises(ToolError, match="Query failed") as error:
                        await call("query_target", name="db", sql="SELECT 1")
                    assert "secret" not in str(error.value)

                await TargetGrant.filter(user=dev).delete()
                assert await call("list_targets") == []
                for name, args in (
                    ("query_target", {"name": "db", "sql": "SELECT 1"}),
                    ("get_target_schema", {"name": "db"}),
                    ("get_target_notes", {"name": "db"}),
                    (
                        "update_target_notes",
                        {"name": "db", "expected_version": 1, "data_notes": "denied"},
                    ),
                ):
                    with pytest.raises(ToolError, match="access denied"):
                        await call(name, **args)
                group = await Group.create(name="developers")
                await GroupMembership.create(group=group, user=dev)
                await GroupTargetGrant.create(group=group, target=target)
                assert len(await call("list_targets")) == 1
                await GroupMembership.filter(user=dev).delete()
                assert await call("list_targets") == []
                await TargetGrant.create(user=dev, target=target)
                target.is_active = False
                await target.save()
                assert await call("list_targets") == []
                target.is_active = True
                await target.save()
                dev.is_active = False
                await dev.save()
                assert await call("list_targets") == []
            finally:
                auth_context_var.reset(ctx)

            # A Target grant alone never gives an ordinary user free SQL access.
            await TargetGrant.create(user=member, target=target)
            ctx = await login(member)
            try:
                names = {t.name for t in await server.list_tools()}
                assert "execute" in names
                assert not {"query_target", "list_targets", "get_target_schema"} & names
                with pytest.raises(ToolError, match="scope"):
                    await call("query_target", name="db", sql="SELECT 1")
            finally:
                auth_context_var.reset(ctx)

        client.portal.call(scenario)
