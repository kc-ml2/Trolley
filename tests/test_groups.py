import pytest
from fastapi.testclient import TestClient

from trolley.application import groups
from trolley.application.target_access import member_target_names, set_target_access
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Target, User


def test_group_membership_and_revocation(tmp_path):
    with TestClient(
        create_app(
            Settings(
                database_url=f"sqlite://{tmp_path}/test.db",
            )
        )
    ) as client:

        async def scenario():
            user = await User.create(email="member@example.com", name="Member")
            await Target.create(name="db", kind="postgresql")
            ctx = AuthContext(str(user.id), "key", UserRole.USER)
            for name in ("one", "two"):
                await groups.create_group(name)
                await set_target_access("db", True, group_name=name)
            await groups.set_user_groups(user.email, ["one", "two"])
            assert await member_target_names(ctx) == {"db"}
            await set_target_access("db", False, group_name="one")
            assert await member_target_names(ctx) == {"db"}
            with pytest.raises(ValueError):
                await groups.set_user_groups(user.email, ["missing"])
            assert await member_target_names(ctx) == {"db"}
            await groups.delete_group("two")
            assert await member_target_names(ctx) == set()
            assert await User.exists(id=user.id)

        client.portal.call(scenario)
