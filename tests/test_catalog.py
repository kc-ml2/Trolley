from fastapi.testclient import TestClient

from trolley.application.operations import create_operation, list_operations
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Target


def test_target_and_operation_catalog(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
    )
    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            await Target.create(name="customers", kind="postgresql")

            operation = await create_operation(
                "find_customer",
                "customers",
                {
                    "sql": "select id from customers where id = $1",
                    "parameters": ["customer_id"],
                },
                input_schema={
                    "type": "object",
                    "properties": {"customer_id": {"type": "integer"}},
                    "required": ["customer_id"],
                    "additionalProperties": False,
                },
            )
            assert operation["target"] == "customers"
            assert await Target.all().count() == 1
            context = AuthContext(user_id="admin", api_key_id="key", role=UserRole.ADMIN)
            assert len(await list_operations(context)) == 1

        client.portal.call(scenario)
