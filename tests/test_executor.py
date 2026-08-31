from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from trolley.application.execution import execute_operation
from trolley.application.operations import create_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Execution, User


def test_executes_registered_postgresql_operation(tmp_path, monkeypatch) -> None:
    targets_file = tmp_path / "targets.yaml"
    targets_file.write_text(
        "targets:\n  customers:\n    kind: postgresql\n    url: postgresql://example/test\n"
    )
    targets_file.chmod(0o600)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        targets_file=str(targets_file),
        admin_emails=frozenset({"root@example.com"}),
    )
    connector = AsyncMock(return_value={"rows": [{"id": 42}]})
    monkeypatch.setattr("trolley.application.execution.database.execute", connector)

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            await create_operation(
                "find_customer",
                "customers",
                {"sql": "select id from customers where id = $1", "parameters": ["id"]},
                input_schema={
                    "type": "object",
                    "properties": {"id": {"type": "integer"}},
                    "required": ["id"],
                    "additionalProperties": False,
                },
            )
            user = await User.create(email="user@example.com", name="User")
            context = AuthContext(
                user_id=str(user.id),
                api_key_id="00000000-0000-0000-0000-000000000002",
                role=UserRole.USER,
            )
            response = await execute_operation("find_customer", {"id": 42}, context)
            assert response["status"] == "succeeded"
            assert response["result"]["rows"] == [{"id": 42}]
            execution = await Execution.get()
            assert execution.arguments == {"id": 42}
            assert execution.status == "succeeded"

        client.portal.call(scenario)
