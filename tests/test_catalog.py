from fastapi.testclient import TestClient

from trolley.application.operations import create_operation, list_operations
from trolley.application.targets import create_target, list_targets
from trolley.config import Settings
from trolley.main import create_app


def test_target_and_operation_catalog(tmp_path) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            target = await create_target(
                "customers",
                "postgresql",
                {"timeout": 5},
                "CUSTOMER_DATABASE_URL",
            )
            assert target["secret_configured"] is False

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
            assert len(await list_targets()) == 1
            assert len(await list_operations()) == 1

        client.portal.call(scenario)
