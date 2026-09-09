import asyncio
import gzip
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from trolley.application.operations import create_operation, update_operation
from trolley.auth.api_keys import create_api_key
from trolley.auth.context import AuthContext
from trolley.config import ExportSettings, Settings
from trolley.main import create_app
from trolley.persistence.models import ExportJob, User


def test_export_ownership_download_expiry_and_revocation(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://unused/test"}},
        exports=ExportSettings(directory=str(tmp_path / "exports")),
    )

    async def write_export(configuration, definition, arguments, path, limits):
        assert arguments == {"email": "root@example.com"}
        with gzip.open(path, "wb") as f:
            f.write(b'{"id":1}\n')
        return 1, 9, path.stat().st_size

    writer = AsyncMock(side_effect=write_export)
    monkeypatch.setattr("trolley.application.exports.export_jsonl", writer)
    app = create_app(settings)
    with TestClient(app) as client:
        manager = app.routes[-1].app.state.mcp_server.export_manager

        async def setup():
            user = await User.get(email="root@example.com")
            key, secret = await create_api_key(user, "test")
            other = await User.create(email="other@example.com", name="Other")
            _, other_secret = await create_api_key(other, "test")
            context = AuthContext(str(user.id), str(key.id), user.role)
            await create_operation(
                "report",
                "db",
                {
                    "sql": "select $1",
                    "parameters": ["email"],
                    "bindings": {"email": "authenticated_user.email"},
                    "export": True,
                },
            )
            with pytest.raises(ValueError, match="Server-bound"):
                await manager.start("report", {"email": "other@example.com"}, context)
            started = await manager.start("report", {}, context)
            await asyncio.gather(*list(manager.tasks))
            job = await manager.get(started["export_id"], context)
            assert job.status == "succeeded"
            assert not hasattr(job, "result")
            return secret, other_secret, str(job.id), context

        secret, other_secret, job_id, context = client.portal.call(setup)
        url = f"/exports/{job_id}/download"
        assert client.get(url).status_code == 401
        assert (
            client.get(url, headers={"Authorization": f"Bearer {other_secret}"}).status_code == 404
        )
        response = client.get(url, headers={"Authorization": f"Bearer {secret}"})
        assert response.status_code == 200
        assert gzip.decompress(response.content) == b'{"id":1}\n'

        async def deny_after_change():
            await update_operation("report", access="restricted")
            # Even administrators must retain the same binding identity.
            await User.filter(id=context.user_id).update(email="changed@example.com")
            with pytest.raises(PermissionError):
                await manager.get(job_id, context)
            await User.filter(id=context.user_id).update(email="root@example.com")

        client.portal.call(deny_after_change)

        async def expire():
            await ExportJob.filter(id=job_id).update(
                expires_at=datetime.now(UTC) - timedelta(seconds=1)
            )

        client.portal.call(expire)
        assert client.get(url, headers={"Authorization": f"Bearer {secret}"}).status_code == 409

        async def failure():
            writer.side_effect = ValueError("sensitive source record")
            started = await manager.start("report", {}, context)
            await asyncio.gather(*list(manager.tasks))
            job = await manager.get(started["export_id"], context)
            assert job.status == "failed"
            assert not manager.path(job).exists()
            await update_operation("report", definition={"sql": "select 1"})
            with pytest.raises(ValueError, match="export-enabled"):
                await manager.start("report", {}, context)

        client.portal.call(failure)
