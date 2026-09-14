from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trolley.application import grants, groups, operations, users
from trolley.application.execution import execute_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.main import create_app
from trolley.persistence.models import GroupMembership, User


def test_group_access_and_revocation(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        targets={"db": {"kind": "postgresql", "url": "postgresql://example/test"}},
        admin_emails=frozenset({"root@example.com"}),
    )
    monkeypatch.setattr(
        "trolley.application.execution.database.execute", AsyncMock(return_value={"rows": []})
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            await groups.create_group("engineering")
            await groups.create_group("finance")
            await users.create_user(
                "member@example.com", "Member", group_names=["engineering", "finance"]
            )
            user = await User.get(email="member@example.com")
            context = AuthContext(user_id=str(user.id), api_key_id=str(uuid4()), role=UserRole.USER)
            await operations.create_operation(
                "private",
                "db",
                {"data_scope": "shared", "sql": "select 1"},
                access=OperationAccess.RESTRICTED,
            )
            await operations.create_operation(
                "public", "db", {"data_scope": "shared", "sql": "select 1"}
            )
            await operations.create_operation(
                "legacy",
                "db",
                {"data_scope": "shared", "sql": "select 1"},
                access=OperationAccess.USER,
            )

            async def names():
                return {o["name"] for o in await operations.list_operations(context)}

            assert await names() == {"public", "legacy"}
            with pytest.raises(PermissionError):
                await execute_operation("private", {}, context)
            for name in ["engineering", "finance"]:
                await groups.grant_group_operation(name, "private")
                await groups.grant_group_operation(name, "private")
            assert len(await groups.list_group_operation_grants()) == 2
            assert await names() == {"public", "legacy", "private"}
            await execute_operation("private", {}, context)
            await users.update_user_access(user.email, UserOperationAccess.ASSIGNED_ONLY)
            assert await names() == {"private"}
            await groups.set_user_groups(user.email, ["finance"])
            assert await names() == {"private"}
            with pytest.raises(ValueError, match="Unknown group"):
                await groups.set_user_groups(user.email, ["missing"])
            assert await names() == {"private"}
            await operations.update_operation("private", access=OperationAccess.ADMIN)
            assert await names() == set()
            with pytest.raises(PermissionError):
                await execute_operation("private", {}, context)
            with pytest.raises(ValueError, match="cannot be granted"):
                await groups.grant_group_operation("finance", "private")
            await operations.update_operation("private", access=OperationAccess.RESTRICTED)
            await grants.grant_operation(user.email, "private")
            await groups.revoke_group_operation("finance", "private")
            assert await names() == {"private"}
            await grants.revoke_operation(user.email, "private")
            assert await names() == set()
            await groups.grant_group_operation("finance", "private")
            await operations.disable_operation("private")
            assert await names() == set()
            with pytest.raises(ValueError, match="inactive"):
                await execute_operation("private", {}, context)
            await operations.update_operation("private")
            await groups.delete_group("finance")
            assert await names() == set()
            assert await groups.list_group_memberships(email=user.email) == []
            await groups.set_user_groups(user.email, [])

        client.portal.call(scenario)


def test_invitation_groups(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db", admin_emails=frozenset({"root@example.com"})
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            await groups.create_group("finance")
            email_service = AsyncMock()
            with pytest.raises(ValueError, match="Unknown group"):
                await users.invite_user(
                    "new@example.com",
                    "New",
                    "key",
                    email_service,
                    "https://example/onboarding",
                    group_names=["missing"],
                )
            assert not await User.exists(email="new@example.com")
            email_service.send.assert_not_called()
            result = await users.invite_user(
                "new@example.com",
                "New",
                "key",
                email_service,
                "https://example/onboarding",
                group_names=["finance", "finance"],
            )
            assert result["user"]["groups"] == ["finance"]
            assert await GroupMembership.all().count() == 1
            await groups.create_group("engineering")
            email_service.send.side_effect = RuntimeError("mail failed")
            with pytest.raises(RuntimeError):
                await users.invite_user(
                    "new@example.com",
                    "New",
                    "key",
                    email_service,
                    "https://example/onboarding",
                    group_names=["engineering"],
                )
            assert await groups.list_group_memberships(email="new@example.com") == [
                {"group": "finance", "email": "new@example.com"}
            ]

        client.portal.call(scenario)
