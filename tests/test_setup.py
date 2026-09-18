import asyncio
from argparse import Namespace
from unittest.mock import AsyncMock

from trolley.cli import manage_local, setup_admins
from trolley.config import Settings


def test_setup_emails_existing_account_without_printing_key(tmp_path, monkeypatch, capsys):
    settings = Settings(database_url=f"sqlite://{tmp_path}/test.db")
    monkeypatch.setattr("trolley.cli.EmailService.check", AsyncMock(return_value=True))
    send = AsyncMock()
    monkeypatch.setattr("trolley.cli.EmailService.send", send)

    async def check():
        await manage_local(
            settings, Namespace(action="create-user", email="admin@example.com", role="admin")
        )
        await setup_admins(settings, ["admin@example.com"], "initial")

    asyncio.run(check())
    send.assert_awaited_once()
    assert "sk-trolley-" in send.call_args.kwargs["html"]
    assert "sk-trolley-" not in capsys.readouterr().out
