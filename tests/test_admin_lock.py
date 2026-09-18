from fastapi.testclient import TestClient

from trolley.application.users import create_user, set_user_role
from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import User


def test_cli_role_is_authoritative(tmp_path):
    with TestClient(create_app(Settings(database_url=f"sqlite://{tmp_path}/test.db"))) as client:

        async def check():
            await create_user("admin@example.com", "Admin", UserRole.ADMIN)
            user = await User.get(email="admin@example.com")
            _, secret = await create_api_key(user, "test")
            verifier = TrolleyTokenVerifier()
            assert (await verifier.verify_token(secret)).claims["role"] == "admin"
            await set_user_role(user.email, UserRole.USER)
            assert (await verifier.verify_token(secret)).claims["role"] == "user"

        client.portal.call(check)
