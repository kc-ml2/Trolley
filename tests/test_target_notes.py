from unittest.mock import AsyncMock, patch

import pytest
from access_helpers import allow, revoke
from fastapi.testclient import TestClient

from trolley.application import target_notes, targets
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import TargetNotesRevision, User


def test_notes_permissions_versions_and_persistence(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        targets={"db": {"kind": "postgresql", "url": "postgresql://localhost/db"}},
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            root = (
                await User.get_or_create(
                    email="root@example.com", defaults={"name": "Admin", "role": "admin"}
                )
            )[0]
            dev = await User.create(email="dev@example.com", name="Dev", role=UserRole.DEVELOPER)
            ctx = AuthContext(str(dev.id), str(dev.id), UserRole.DEVELOPER)
            admin = AuthContext(str(root.id), str(root.id), UserRole.ADMIN)
            await allow(root, "db")
            assert (await target_notes.get_target_notes(admin, "db"))["version"] == 0
            with pytest.raises(PermissionError):
                await target_notes.update_target_notes(ctx, "db", 0, data_notes="denied")
            await allow(dev, "db")
            first = await target_notes.update_target_notes(
                ctx, "db", 0, description="Logs", data_notes="Content can be an array."
            )
            assert first["version"] == 1
            with pytest.raises(ValueError, match="conflict"):
                await target_notes.update_target_notes(admin, "db", 0, data_notes="stale")
            assert await TargetNotesRevision.all().count() == 1
            second = await target_notes.update_target_notes(admin, "db", 1, description="")
            assert second["description"] == ""
            assert second["data_notes"] == first["data_notes"]
            revision = await TargetNotesRevision.get(version=2)
            assert revision.before["description"] == "Logs"
            assert revision.after == {k: v for k, v in second.items() if k != "target"}
            await targets.sync_targets(settings)
            assert (await target_notes.get_target_notes(ctx, "db"))["version"] == 2
            assert (await targets.list_targets(settings))[0]["description"] == ""
            with patch(
                "trolley.connectors.database.inspect_schema", new_callable=AsyncMock
            ) as inspect:
                inspect.return_value = []
                schema = await targets.get_target_schema(settings, "db")
                assert schema["data_notes"] == first["data_notes"]
            for kwargs in ({}, {"data_notes": "a" * 20001}, {"description": "a" * 2001}):
                with pytest.raises(ValueError):
                    await target_notes.update_target_notes(ctx, "db", 2, **kwargs)
            await revoke(dev)
            with pytest.raises(PermissionError):
                await target_notes.get_target_notes(ctx, "db")
            with pytest.raises(PermissionError):
                await target_notes.update_target_notes(ctx, "db", 2, data_notes="denied")

        client.portal.call(scenario)
