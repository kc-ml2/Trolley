from uuid import uuid4

from fastapi.testclient import TestClient

from trolley.application import grants, operations, targets, users
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.operations import OperationAccess
from trolley.domain.users import UserOperationAccess, UserRole
from trolley.main import create_app
from trolley.persistence.models import Target, User


def test_operation_access_matrix_and_inactive_target(tmp_path) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            standard_user = await User.create(email="standard@example.com", name="Standard")
            assigned_user = await User.create(email="assigned@example.com", name="Assigned")
            admin = await User.create(email="admin@example.com", name="Admin", role=UserRole.ADMIN)
            await users.update_user_access(assigned_user.email, UserOperationAccess.ASSIGNED_ONLY)
            await targets.create_target("db", "postgresql", {}, "DATABASE_URL")
            await operations.create_operation("public", "db", {"sql": "select 1"})
            await operations.create_operation(
                "restricted",
                "db",
                {"sql": "select 1"},
                access=OperationAccess.RESTRICTED,
            )
            await operations.create_operation(
                "admin_only",
                "db",
                {"sql": "select 1"},
                access=OperationAccess.ADMIN,
            )
            await grants.grant_operation(standard_user.email, "restricted")
            await grants.grant_operation(assigned_user.email, "public")

            def context(user: User, role: UserRole) -> AuthContext:
                return AuthContext(user_id=str(user.id), api_key_id=str(uuid4()), role=role)

            standard_names = {
                item["name"]
                for item in await operations.list_operations(context(standard_user, UserRole.USER))
            }
            assigned_names = {
                item["name"]
                for item in await operations.list_operations(context(assigned_user, UserRole.USER))
            }
            admin_names = {
                item["name"]
                for item in await operations.list_operations(context(admin, UserRole.ADMIN))
            }
            assert standard_names == {"public", "restricted"}
            assert assigned_names == {"public"}
            assert admin_names == {"public", "restricted", "admin_only"}

            target = await Target.get(name="db")
            target.is_active = False
            await target.save()
            assert await operations.list_operations(context(standard_user, UserRole.USER)) == []
            assert await operations.list_operations(context(admin, UserRole.ADMIN)) == []

        client.portal.call(scenario)
