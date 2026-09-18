from access_helpers import allow
from fastapi.testclient import TestClient

from trolley.application.access import accessible_operation_names
from trolley.application.operations import create_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Target, User


def test_target_is_the_operation_boundary(tmp_path):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
    )
    with TestClient(create_app(settings)) as client:

        async def scenario():
            for name in ("a", "b"):
                await Target.create(name=name, kind="postgresql")
                await create_operation(name, name, {"data_scope": "shared", "sql": "SELECT 1"})
            for role in UserRole:
                user = await User.create(email=f"{role}@example.com", name=str(role), role=role)
                ctx = AuthContext(str(user.id), "key", role)
                assert await accessible_operation_names(ctx) == set()
                await allow(user, "a")
                assert await accessible_operation_names(ctx) == {"a"}
                user.is_active = False
                await user.save()
                assert await accessible_operation_names(ctx) == set()

        client.portal.call(scenario)
