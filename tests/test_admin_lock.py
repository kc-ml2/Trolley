import pytest
from fastapi.testclient import TestClient

from trolley.application.users import create_user
from trolley.auth.api_keys import create_api_key
from trolley.auth.enums import Scope
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import User


def test_admin_assignment_and_scope_require_allowlist(tmp_path) -> None:
    settings = Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db")
    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            with pytest.raises(PermissionError, match="not allowed"):
                await create_user(
                    "outsider@example.com",
                    "Outsider",
                    UserRole.ADMIN,
                    admin_emails=frozenset({"admin@example.com"}),
                )

            admin = await User.create(email="admin@example.com", name="Admin", role=UserRole.ADMIN)
            _, secret = await create_api_key(admin, "test")

            allowed = await TrolleyTokenVerifier(frozenset({"admin@example.com"})).verify_token(
                secret
            )
            locked = await TrolleyTokenVerifier(frozenset()).verify_token(secret)

            assert allowed is not None and Scope.ADMIN in allowed.scopes
            assert allowed.claims["role"] == UserRole.ADMIN
            assert locked is not None and Scope.ADMIN not in locked.scopes
            assert locked.claims["role"] == UserRole.USER

        client.portal.call(scenario)
