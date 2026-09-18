from fastapi.testclient import TestClient

from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import ApiKey, Group, User


def test_empty_startup(tmp_path):
    with TestClient(create_app(Settings(database_url=f"sqlite://{tmp_path}/test.db"))) as client:

        async def check():
            assert await User.all().count() == 0
            assert await Group.all().count() == 0
            assert await ApiKey.all().count() == 0

        client.portal.call(check)
