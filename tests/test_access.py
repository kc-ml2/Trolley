from pantry.domain.accounts import AccountKind, AccountRole
from pantry.models import Account


def test_account_defaults_to_human_user(tmp_path) -> None:
    from fastapi.testclient import TestClient

    from pantry.config import Settings
    from pantry.main import create_app

    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    with TestClient(app) as client:

        async def create_account() -> Account:
            return await Account.create(email="default-role@example.com")

        account = client.portal.call(create_account)
        assert account.kind == AccountKind.HUMAN
        assert account.role == AccountRole.USER
