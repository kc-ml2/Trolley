import pytest
from fastapi.testclient import TestClient

from pantry.config import Settings
from pantry.domain.accounts import AccountKind, AccountRole
from pantry.main import create_app
from pantry.models import Account, ApiKey
from pantry.services.auth import authenticate_secret, create_api_key

BOOTSTRAP_SECRET = "sk-pantry-bootstrap-admin"


def test_bootstraps_first_admin_and_api_key(tmp_path) -> None:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite://{tmp_path}/test.db",
            bootstrap_admin_email="admin@example.com",
            bootstrap_admin_api_key=BOOTSTRAP_SECRET,
        )
    )
    with TestClient(app) as client:

        async def load() -> tuple[Account, ApiKey, object]:
            account = await Account.all().get()
            api_key = await ApiKey.all().get()
            auth = await authenticate_secret(BOOTSTRAP_SECRET)
            return account, api_key, auth

        account, api_key, auth = client.portal.call(load)
        assert account.kind == AccountKind.HUMAN
        assert account.email == "admin@example.com"
        assert account.role == AccountRole.ADMIN
        assert api_key.name == "Bootstrap Admin"
        assert BOOTSTRAP_SECRET not in api_key.secret_hash
        assert auth.status == "authenticated"
        assert auth.account.id == account.id


def test_normalizes_bootstrap_api_key_and_stores_identifying_prefix(tmp_path) -> None:
    secret = "sk-pantry-distinct-random-part"
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite://{tmp_path}/test.db",
            bootstrap_admin_email="admin@example.com",
            bootstrap_admin_api_key=f"  {secret}  ",
        )
    )
    with TestClient(app) as client:

        async def load() -> tuple[ApiKey, object]:
            return await ApiKey.all().get(), await authenticate_secret(secret)

        api_key, auth = client.portal.call(load)
        assert api_key.key_prefix == secret[:20]
        assert auth.status == "authenticated"


def test_rejects_partial_bootstrap_configuration(tmp_path) -> None:
    app = create_app(
        Settings(
            _env_file=None,
            database_url=f"sqlite://{tmp_path}/test.db",
            bootstrap_admin_email="admin@example.com",
        )
    )
    with pytest.raises(ValueError, match="must be set together"):
        with TestClient(app):
            pass


def test_does_not_bootstrap_when_an_account_already_exists(tmp_path) -> None:
    database_url = f"sqlite://{tmp_path}/test.db"
    initial_app = create_app(Settings(_env_file=None, database_url=database_url))
    with TestClient(initial_app) as client:

        async def seed() -> None:
            account = await Account.create(email="existing@example.com")
            await create_api_key(account=account, name="Existing", secret="existing-secret")

        client.portal.call(seed)

    bootstrap_app = create_app(
        Settings(
            _env_file=None,
            database_url=database_url,
            bootstrap_admin_email="admin@example.com",
            bootstrap_admin_api_key=BOOTSTRAP_SECRET,
        )
    )
    with TestClient(bootstrap_app) as client:

        async def load() -> tuple[int, object]:
            return await Account.all().count(), await authenticate_secret(BOOTSTRAP_SECRET)

        count, auth = client.portal.call(load)
        assert count == 1
        assert auth.status == "invalid"
