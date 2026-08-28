from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from trolley.application import operations, targets
from trolley.application.execution import execute_operation
from trolley.auth.api_keys import create_api_key
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.mcp.enums import SystemToolName
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import User


async def authenticated(
    secret: str, admin_emails: frozenset[str] = frozenset()
) -> AuthenticatedUser:
    token = await TrolleyTokenVerifier(admin_emails).verify_token(secret)
    assert token is not None
    return AuthenticatedUser(token)


def test_bearer_auth_and_operation_access(tmp_path, monkeypatch) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            admin = await User.create(email="admin@example.com", name="Admin", role="admin")
            user = await User.create(email="user@example.com", name="User", role="user")
            _, admin_secret = await create_api_key(admin, "test")
            user_key, user_secret = await create_api_key(user, "test")

            admin_auth = await authenticated(admin_secret, frozenset({"admin@example.com"}))
            user_auth = await authenticated(user_secret)
            assert "trolley:admin" in admin_auth.scopes
            assert "trolley:admin" not in user_auth.scopes

            await targets.create_target("payments", "postgresql", {}, "PAYMENTS_URL")
            await operations.create_operation("revenue", "payments", {"sql": "select 1"})
            await operations.create_operation(
                "profit", "payments", {"sql": "select 2"}, access="admin"
            )
            user_operations = await operations.list_operations("user")
            assert [item["name"] for item in user_operations] == ["revenue"]
            assert "target" not in user_operations[0]
            assert "definition" not in user_operations[0]
            assert {item["name"] for item in await operations.list_operations("admin")} == {
                "profit",
                "revenue",
            }

            context = AuthContext(
                user_id=str(user.id), api_key_id=str(user_key.id), role=UserRole.USER
            )
            try:
                await execute_operation("profit", {}, context)
            except PermissionError as error:
                assert "admin" in str(error)
            else:
                raise AssertionError("admin operation was not rejected")

            token = auth_context_var.set(user_auth)
            try:
                from trolley.mcp.pipeline import validate_tool

                try:
                    validate_tool(SystemToolName.LIST_TARGETS)
                except PermissionError:
                    pass
                else:
                    raise AssertionError("user accessed an admin tool")
            finally:
                auth_context_var.reset(token)

        client.portal.call(scenario)
