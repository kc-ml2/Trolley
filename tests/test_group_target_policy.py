from fastapi.testclient import TestClient

from trolley.application.access import accessible_operation_names, can_access_operation
from trolley.application.target_access import accessible_target_names
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import (
    Group,
    GroupMembership,
    GroupTargetGrant,
    Operation,
    Target,
    User,
)


def test_all_roles_use_group_boundary(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/policy.db",
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            target = await Target.create(name="db", kind="postgresql")
            group = await Group.create(name="team")
            operation = await Operation.create(
                name="tool",
                target=target,
                definition={"data_scope": "shared", "sql": "SELECT 1"},
            )
            for role in UserRole:
                user = await User.get_or_none(email=f"{role}@example.com")
                if user is None:
                    user = await User.create(email=f"{role}@example.com", name=str(role), role=role)
                ctx = AuthContext(str(user.id), "unused", role)
                assert not await can_access_operation(ctx, operation)
                assert not await accessible_target_names(ctx)
                await GroupMembership.create(user=user, group=group)
                await GroupTargetGrant.get_or_create(group=group, target=target)
                assert await accessible_operation_names(ctx) == {"tool"}
                assert await can_access_operation(ctx, operation)
                assert await accessible_target_names(ctx) == (
                    {"db"} if role != UserRole.USER else set()
                )
                await GroupMembership.filter(user=user).delete()
                assert not await can_access_operation(ctx, operation)
            target.is_active = False
            await target.save()
            assert not await accessible_operation_names(ctx)

        client.portal.call(scenario)


def test_identity_management_not_exposed_over_mcp():
    import asyncio

    from trolley.mcp.server import create_mcp_server

    server = create_mcp_server()
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert not names & {
        "invite_user",
        "create_api_key",
        "set_user_role",
        "set_user_groups",
        "set_target_access",
        "grant_operation",
        "grant_group_operation",
        "create_group",
        "delete_group",
    }
    assert {"create_operation", "update_operation", "execute"} <= names
