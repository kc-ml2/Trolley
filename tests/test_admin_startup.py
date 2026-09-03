from fastapi.testclient import TestClient

from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import ApiKey, User


def test_startup_creates_allowlisted_admin_users_without_keys(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"admin@example.com", "ops@example.com"}),
    )
    with TestClient(create_app(settings)) as client:

        async def assert_admins() -> None:
            users = await User.all().order_by("email")
            assert [user.email for user in users] == ["admin@example.com", "ops@example.com"]
            assert all(user.role == UserRole.ADMIN for user in users)
            assert await ApiKey.all().count() == 0

        client.portal.call(assert_admins)
