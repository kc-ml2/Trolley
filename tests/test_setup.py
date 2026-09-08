import asyncio
from unittest.mock import AsyncMock

import pytest
from tortoise import Tortoise

from trolley.cli import parser, setup_admins
from trolley.config import Settings
from trolley.persistence.database import tortoise_config
from trolley.persistence.models import ApiKey, User


def test_setup_emails_admin_without_printing_key(tmp_path, monkeypatch, capsys):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/setup.db",
        admin_emails=frozenset({"admin@example.com"}),
        public_base_url="https://trolley.example.com",
    )
    monkeypatch.setattr("trolley.cli.EmailService.check", AsyncMock(return_value=True))
    send = AsyncMock()
    monkeypatch.setattr("trolley.cli.EmailService.send", send)

    async def scenario():
        await setup_admins(settings, ["ADMIN@example.com", "admin@example.com"], "setup")
        await Tortoise.init(config=tortoise_config(settings))
        try:
            user = await User.get(email="admin@example.com")
            assert user.role == "admin"
            assert await ApiKey.filter(user=user, is_active=True).count() == 1
        finally:
            await Tortoise.close_connections()

    asyncio.run(scenario())
    send.assert_awaited_once()
    assert "API key: sk-trolley-" in send.call_args.args[2]
    assert "sk-trolley-" not in capsys.readouterr().out


def test_setup_validates_all_recipients_before_sending(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/setup.db",
        admin_emails=frozenset({"admin@example.com"}),
    )
    check = AsyncMock(return_value=True)
    monkeypatch.setattr("trolley.cli.EmailService.check", check)
    with pytest.raises(PermissionError, match="admins.emails"):
        asyncio.run(setup_admins(settings, ["admin@example.com", "other@example.com"], "setup"))
    check.assert_not_called()
    assert not (tmp_path / "setup.db").exists()


def test_setup_parser_accepts_multiple_admins():
    args = parser().parse_args(["setup", "one@example.com", "two@example.com"])
    assert args.emails == ["one@example.com", "two@example.com"]
