from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trolley.application import grants, operations, users
from trolley.application.execution import execute_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.main import create_app
from trolley.persistence.models import User


def test_user_specific_operation_access(tmp_path, monkeypatch) -> None:
    targets_file = tmp_path / "targets.yaml"
    targets_file.write_text(
        "targets:\n  db:\n    kind: postgresql\n    url: postgresql://example/test\n"
    )
    targets_file.chmod(0o600)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        targets_file=str(targets_file),
        admin_emails=frozenset({"root@example.com"}),
    )
    connector = AsyncMock(return_value={"rows": [{"ok": 1}]})
    monkeypatch.setattr("trolley.application.execution.database.execute", connector)

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            user = await User.create(email="limited@example.com", name="Limited")
            other = await User.create(email="other@example.com", name="Other")
            await operations.create_operation("public_report", "db", {"sql": "select 1"})
            await operations.create_operation(
                "private_report",
                "db",
                {"sql": "select 1"},
                access=OperationAccess.RESTRICTED,
            )
            await operations.create_operation(
                "admin_report",
                "db",
                {"sql": "select 1"},
                access=OperationAccess.ADMIN,
            )

            await users.update_user_access(user.email, UserOperationAccess.ASSIGNED_ONLY)
            await grants.grant_operation(user.email, "private_report")

            limited = AuthContext(user_id=str(user.id), api_key_id=str(uuid4()), role=UserRole.USER)
            standard = AuthContext(
                user_id=str(other.id), api_key_id=str(uuid4()), role=UserRole.USER
            )
            assert [item["name"] for item in await operations.list_operations(limited)] == [
                "private_report"
            ]
            assert [item["name"] for item in await operations.list_operations(standard)] == [
                "public_report"
            ]

            await execute_operation("private_report", {}, limited)
            with pytest.raises(PermissionError, match="denied"):
                await execute_operation("public_report", {}, limited)
            with pytest.raises(PermissionError, match="denied"):
                await execute_operation("private_report", {}, standard)
            with pytest.raises(ValueError, match="cannot be granted"):
                await grants.grant_operation(user.email, "admin_report")

            await operations.update_operation("private_report", access=OperationAccess.ADMIN)
            assert await operations.list_operations(limited) == []
            with pytest.raises(PermissionError, match="denied"):
                await execute_operation("private_report", {}, limited)

            await operations.update_operation("private_report", access=OperationAccess.RESTRICTED)
            revoked = await grants.revoke_operation(user.email, "private_report")
            assert revoked["revoked"] is True
            assert await operations.list_operations(limited) == []

        client.portal.call(scenario)
