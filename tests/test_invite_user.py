from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trolley.application.users import invite_user
from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import ApiKey, User


@pytest.mark.parametrize("role", ["user", "developer", "admin"])
def test_invitation_preserves_role_and_hides_secret(tmp_path, role):
    settings = Settings(database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def check():
            user = await User.create(email="member@example.com", name="Member", role=role)
            mail = AsyncMock()
            result = await invite_user(
                user.email, user.name, "initial", mail, "https://example.com/onboarding.md"
            )
            assert result["user"]["role"] == role
            assert result["email_sent"]
            assert "secret" not in result["api_key"]
            assert "sk-trolley-" in mail.send.call_args.args[2]
            assert "sk-trolley-" in mail.send.call_args.kwargs["html"]
            assert await ApiKey.filter(user=user, is_active=True).count() == 1
            await user.refresh_from_db()
            assert user.role == role

        client.portal.call(check)


def test_missing_user_is_not_created_by_invitation(tmp_path):
    with TestClient(create_app(Settings(database_url=f"sqlite://{tmp_path}/test.db"))) as client:

        async def check():
            with pytest.raises(ValueError, match="Create the user"):
                await invite_user(
                    "missing@example.com",
                    "Missing",
                    "key",
                    AsyncMock(),
                    "https://example.com/onboarding.md",
                )
            assert await User.all().count() == 0

        client.portal.call(check)
