from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from trolley.application import target_notes, targets
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Target, TargetGrant, TargetNotesRevision, User


def test_notes_permissions_versions_and_persistence(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://localhost/db"}},
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            root = await User.get(email="root@example.com")
            dev = await User.create(email="dev@example.com", name="Dev", role=UserRole.DEVELOPER)
            ctx = AuthContext(str(dev.id), str(dev.id), UserRole.DEVELOPER)
            admin = AuthContext(str(root.id), str(root.id), UserRole.ADMIN)
            assert (await target_notes.get_target_notes(admin, "db"))["version"] == 0
            with pytest.raises(PermissionError):
                await target_notes.update_target_notes(ctx, "db", 0, data_notes="denied")
            await TargetGrant.create(user=dev, target=await Target.get(name="db"))
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
            await TargetGrant.filter(user=dev).delete()
            with pytest.raises(PermissionError):
                await target_notes.get_target_notes(ctx, "db")
            with pytest.raises(PermissionError):
                await target_notes.update_target_notes(ctx, "db", 2, data_notes="denied")

        client.portal.call(scenario)
