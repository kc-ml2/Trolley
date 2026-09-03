from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trolley.application.users import invite_user
from trolley.config import Settings
from trolley.email import EmailService, EmailUnavailableError
from trolley.main import create_app
from trolley.persistence.models import ApiKey, User


def test_invite_user_emails_key_without_returning_secret(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"admin@example.com"}),
        email_from="trolley@example.com",
        smtp_host="smtp.example.com",
    )
    app = create_app(settings)
    app.routes[-1].app.state.email_service.check = AsyncMock(return_value=True)
    service = EmailService(settings)
    service.send = AsyncMock()

    with TestClient(app) as client:

        async def scenario() -> None:
            result = await invite_user(
                " User@Example.com ",
                "Reporting User",
                "initial-access",
                service,
                "https://trolley.example.com/onboarding.md",
            )
            assert result["user"]["email"] == "user@example.com"
            assert result["api_key"]["is_active"] is True
            assert result["email_sent"] is True
            assert "secret" not in result
            body = service.send.await_args.args[2]
            assert "sk-trolley-" in body
            assert "https://trolley.example.com/onboarding.md" in body
            assert "agent conversation" in body

            retried = await invite_user(
                "user@example.com",
                "Ignored Name",
                "second-access",
                service,
                "https://trolley.example.com/onboarding.md",
            )
            assert retried["user"]["id"] == result["user"]["id"]

        client.portal.call(scenario)


def test_invite_user_emails_key_to_allowlisted_admin(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"owner@example.com", "admin2@example.com"}),
    )
    service = EmailService(settings)
    service.send = AsyncMock()

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            existing_admin = await User.get(email="admin2@example.com")
            result = await invite_user(
                " Admin2@Example.com ",
                "Second Admin",
                "admin-access",
                service,
                "https://trolley.example.com/onboarding.md",
                admin_emails=settings.admin_emails,
            )
            assert result["user"]["id"] == str(existing_admin.id)
            assert result["user"]["role"] == "admin"
            assert result["email_sent"] is True
            assert "secret" not in result

        client.portal.call(scenario)


def test_invite_user_promotes_allowlisted_existing_user(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"owner@example.com"}),
    )
    service = EmailService(settings)
    service.send = AsyncMock()

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            user = await User.create(email="next@example.com", name="Next", role="user")
            result = await invite_user(
                user.email,
                user.name,
                "admin-access",
                service,
                "https://trolley.example.com/onboarding.md",
                admin_emails=frozenset({"owner@example.com", "next@example.com"}),
            )
            await user.refresh_from_db()
            assert result["user"]["role"] == "admin"
            assert user.role == "admin"

        client.portal.call(scenario)


def test_invite_user_disables_key_when_email_fails(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"admin@example.com"}),
    )
    service = EmailService(settings)
    service.send = AsyncMock(side_effect=EmailUnavailableError("failed"))

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            with pytest.raises(EmailUnavailableError):
                await invite_user(
                    "user@example.com",
                    "User",
                    "initial-access",
                    service,
                    "https://trolley.example.com/onboarding.md",
                )
            user = await User.get(email="user@example.com")
            key = await ApiKey.get(user=user)
            assert key.is_active is False

        client.portal.call(scenario)
