from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trolley.config import Settings
from trolley.main import create_app
from trolley.operator_wizard import add_user
from trolley.persistence.models import Group, GroupMembership, GroupTargetGrant, Target, User


@pytest.mark.parametrize("confirm", ["y", "n"])
def test_new_user_is_saved_only_after_confirmation(tmp_path, confirm):
    settings = Settings(database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def check():
            await Target.create(name="db", kind="postgresql")
            answers = iter(["Admin@Example.com", "admin", "team", "db", confirm])
            await add_user(settings, ask=lambda _: next(answers), tell=lambda _: None)
            assert await User.all().count() == (1 if confirm == "y" else 0)
            assert await Group.all().count() == (1 if confirm == "y" else 0)
            if confirm == "y":
                assert (await User.first()).role == "admin"
                assert await GroupTargetGrant.all().count() == 1

        client.portal.call(check)


def test_existing_group_and_duplicate_user(tmp_path):
    settings = Settings(database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def check():
            await Group.create(name="team")
            answers = iter(["user@example.com", "", "team", "y"])
            await add_user(settings, ask=lambda _: next(answers), tell=lambda _: None)
            assert await GroupMembership.all().count() == 1
            assert await GroupTargetGrant.all().count() == 0
            answers = iter(["user@example.com"])
            await add_user(settings, ask=lambda _: next(answers), tell=lambda _: None)
            assert await User.all().count() == 1

        client.portal.call(check)


def test_mail_failure_keeps_settings(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        smtp_host="smtp.example.com",
        email_from="sender@example.com",
    )
    monkeypatch.setattr("trolley.email.EmailService.check", AsyncMock(return_value=True))
    monkeypatch.setattr(
        "trolley.operator_wizard.invite_user", AsyncMock(side_effect=RuntimeError("mail"))
    )
    with TestClient(create_app(settings)) as client:

        async def check():
            answers = iter(["admin@example.com", "admin", "team", "", "y", "y"])
            messages = []
            await add_user(settings, ask=lambda _: next(answers), tell=messages.append)
            assert await User.all().count() == 1
            assert any("invitation failed" in m for m in messages)

        client.portal.call(check)
