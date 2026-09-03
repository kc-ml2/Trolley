import pytest
from fastapi.testclient import TestClient

from trolley.application.operations import create_operation
from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import Target


def test_rejects_reserved_names_and_parameter_mismatch(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
    )
    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            await Target.create(name="payments", kind="postgresql")
            with pytest.raises(ValueError, match="reserved"):
                await create_operation("create_user", "payments", {"sql": "select 1"})
            with pytest.raises(ValueError, match="only letters"):
                await create_operation("monthly revenue", "payments", {"sql": "select 1"})
            with pytest.raises(ValueError, match="must match"):
                await create_operation(
                    "monthly_revenue",
                    "payments",
                    {"sql": "select $1", "parameters": ["month"]},
                    input_schema={
                        "type": "object",
                        "properties": {"other": {"type": "string"}},
                        "required": ["other"],
                    },
                )

        client.portal.call(scenario)
