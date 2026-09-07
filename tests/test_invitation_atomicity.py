from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trolley.application import groups, users
from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import ApiKey, GroupMembership, User


def test_invite_defers_privileges_until_finalization(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db", admin_emails=frozenset({"root@example.com"})
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            await groups.create_group("finance")
            user = await User.create(email="next@example.com", name="Next")
            service = AsyncMock()

            async def failed_delivery(*args):
                await user.refresh_from_db()
                assert user.role == "user"
                assert not await ApiKey.filter(user=user, is_active=True).exists()
                assert not await GroupMembership.filter(user=user).exists()
                raise RuntimeError("mail failed")

            service.send.side_effect = failed_delivery
            kwargs = {"admin_emails": frozenset({user.email}), "group_names": ["finance"]}
            with pytest.raises(RuntimeError, match="mail failed"):
                await users.invite_user(
                    user.email, user.name, "key", service, "https://example/onboarding", **kwargs
                )
            await user.refresh_from_db()
            assert user.role == "user"

            service.send.side_effect = None
            original = GroupMembership.get_or_create
            monkeypatch.setattr(
                GroupMembership,
                "get_or_create",
                AsyncMock(side_effect=RuntimeError("membership failed")),
            )
            with pytest.raises(RuntimeError, match="membership failed"):
                await users.invite_user(
                    user.email, user.name, "key", service, "https://example/onboarding", **kwargs
                )
            await user.refresh_from_db()
            assert user.role == "user"
            assert not await ApiKey.filter(user=user, is_active=True).exists()
            assert not await GroupMembership.filter(user=user).exists()
            monkeypatch.setattr(GroupMembership, "get_or_create", original)
            result = await users.invite_user(
                user.email, user.name, "key", service, "https://example/onboarding", **kwargs
            )
            assert result["user"]["role"] == "admin"
            assert result["user"]["groups"] == ["finance"]
            assert await ApiKey.filter(user=user, is_active=True).count() == 1

        client.portal.call(scenario)
