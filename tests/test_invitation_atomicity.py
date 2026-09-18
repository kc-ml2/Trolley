from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trolley.application.users import invite_user
from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import ApiKey, User


def test_failed_delivery_does_not_activate_key_or_change_role(tmp_path):
    with TestClient(create_app(Settings(database_url=f"sqlite://{tmp_path}/test.db"))) as client:

        async def check():
            user = await User.create(email="admin@example.com", name="Admin", role="admin")
            mail = AsyncMock()

            async def fail(*args, **kwargs):
                assert not await ApiKey.filter(user=user, is_active=True).exists()
                raise RuntimeError("mail failed")

            mail.send.side_effect = fail
            with pytest.raises(RuntimeError):
                await invite_user(
                    user.email, user.name, "key", mail, "https://example.com/onboarding.md"
                )
            assert not await ApiKey.filter(user=user, is_active=True).exists()
            await user.refresh_from_db()
            assert user.role == "admin"

        client.portal.call(check)
