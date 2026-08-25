import pytest
from fastapi.testclient import TestClient
from tortoise.exceptions import DoesNotExist

from pantry.config import Settings
from pantry.domain.accounts import AccountKind, AccountRole
from pantry.main import create_app
from pantry.management import accounts, agents, credentials, models, providers, resources, trolleys


@pytest.fixture
def app_client(tmp_path):
    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    with TestClient(app) as client:
        yield client


def test_manages_credential_provider_and_model(app_client, monkeypatch) -> None:
    monkeypatch.setenv("MANAGED_API_KEY", "secret-value")

    async def manage() -> tuple[dict, dict, dict, list[dict], list[dict], list[dict]]:
        credential = await credentials.create_credential("managed", "MANAGED_API_KEY")
        provider = await providers.create_provider(
            "primary",
            "http://provider.test/",
            credential_name="managed",
        )
        model = await models.create_model("coder", "provider-coder", "primary")
        return (
            credential,
            provider,
            model,
            await credentials.list_credentials(),
            await providers.list_providers(),
            await models.list_models(),
        )

    credential, provider, model, credential_list, provider_list, model_list = (
        app_client.portal.call(manage)
    )
    assert credential["secret_configured"] is True
    assert "secret-value" not in str(credential)
    assert provider["base_url"] == "http://provider.test"
    assert provider["credential_name"] == "managed"
    assert model["provider_name"] == "primary"
    assert credential_list == [credential]
    assert provider_list == [provider]
    assert model_list == [model]


def test_updates_and_disables_managed_objects(app_client) -> None:
    async def manage() -> tuple[dict, dict, dict]:
        await credentials.create_credential("managed", "OLD_API_KEY")
        await providers.create_provider("primary", "http://old.test", "managed")
        await models.create_model("coder", "old-model", "primary")
        credential = await credentials.update_credential(
            "managed",
            secret_env="NEW_API_KEY",
            is_active=False,
        )
        provider = await providers.update_provider(
            "primary",
            base_url="https://new.test/",
            clear_credential=True,
            is_active=False,
        )
        model = await models.update_model(
            "coder",
            upstream_model="new-model",
            is_active=False,
        )
        return credential, provider, model

    credential, provider, model = app_client.portal.call(manage)
    assert credential["secret_env"] == "NEW_API_KEY"
    assert credential["is_active"] is False
    assert provider["base_url"] == "https://new.test"
    assert provider["credential_name"] is None
    assert provider["is_active"] is False
    assert model["upstream_model"] == "new-model"
    assert model["is_active"] is False


@pytest.mark.parametrize(
    "base_url",
    [
        "provider.test",
        "ftp://provider.test",
        "http://user:password@provider.test",
        "http://provider.test?token=secret",
        "http://provider.test#fragment",
    ],
)
def test_rejects_unsafe_provider_urls(app_client, base_url: str) -> None:
    async def create() -> None:
        await providers.create_provider("unsafe", base_url)

    with pytest.raises(ValueError):
        app_client.portal.call(create)


def test_manages_human_and_trolley_accounts(app_client) -> None:
    async def manage() -> tuple[dict, object, list[dict]]:
        human = await accounts.create_account(
            AccountKind.HUMAN,
            email="human@example.com",
            role=AccountRole.ADMIN,
        )
        trolley = await trolleys.create_trolley("aws-production")
        return human, trolley, await accounts.list_accounts()

    human, trolley, listed = app_client.portal.call(manage)
    assert human["kind"] == "human"
    assert human["role"] == "admin"
    assert trolley.name == "aws-production"
    assert trolley.api_key.startswith("sk-pantry-")
    trolley_account = next(account for account in listed if account["id"] == trolley.account_id)
    assert trolley_account["kind"] == "trolley"
    assert trolley_account["role"] == "user"


@pytest.mark.parametrize(
    ("kind", "email", "name", "role"),
    [
        (AccountKind.HUMAN, None, "No Email", AccountRole.USER),
        (AccountKind.TROLLEY, None, None, AccountRole.USER),
        (AccountKind.TROLLEY, None, "admin-trolley", AccountRole.ADMIN),
    ],
)
def test_rejects_invalid_accounts(app_client, kind, email, name, role) -> None:
    async def create() -> None:
        await accounts.create_account(kind, email=email, name=name, role=role)

    with pytest.raises(ValueError):
        app_client.portal.call(create)


@pytest.mark.parametrize(
    ("operation", "args"),
    [
        ("credential", ("", "VALID_ENV")),
        ("credential", ("name", "not-valid-env")),
        ("provider", ("", "http://provider.test/v1")),
        ("provider", ("name", "   ")),
        ("model", ("", "upstream", "primary")),
        ("model", ("alias", "", "primary")),
        ("agent", ("reservation", "   ")),
        ("resource_group", ("worker", "group", "   ")),
        ("resource", ("group", "resource", "   ")),
    ],
)
def test_rejects_empty_management_identifiers(app_client, operation, args) -> None:
    async def create() -> None:
        if operation == "credential":
            await credentials.create_credential(*args)
        elif operation == "provider":
            await providers.create_provider(*args)
        elif operation == "model":
            if not await providers.list_providers():
                await providers.create_provider("primary", "http://provider.test/v1")
            await models.create_model(*args)
        elif operation == "agent":
            await agents.create_agent(*args)
        elif operation == "resource_group":
            await trolleys.create_trolley("worker")
            await resources.create_resource_group(*args)
        else:
            await trolleys.create_trolley("worker")
            await resources.create_resource_group("worker", "group", "mode")
            await resources.create_resource(*args)

    with pytest.raises(ValueError):
        app_client.portal.call(create)


def test_manages_opaque_agent_allocation_modes(app_client) -> None:
    async def manage() -> tuple[dict, dict, dict]:
        await providers.create_provider("primary", "http://provider.test/v1")
        await models.create_model("small", "upstream-small", "primary")
        created = await agents.create_agent(
            "reservation",
            "time_window",
            model_alias="small",
            configuration={"interval": 300},
        )
        updated = await agents.update_agent(
            "reservation",
            allocation_mode="custom_mode",
            clear_model=True,
            is_active=False,
        )
        listed = (await agents.list_agents())[0]
        return created, updated, listed

    created, updated, listed = app_client.portal.call(manage)
    assert created["allocation_mode"] == "time_window"
    assert created["model_alias"] == "small"
    assert created["configuration"] == {"interval": 300}
    assert updated["allocation_mode"] == "custom_mode"
    assert updated["model_alias"] is None
    assert updated["is_active"] is False
    assert listed == updated


def test_manages_resource_groups_and_resources_as_opaque_data(app_client) -> None:
    async def manage() -> tuple[dict, dict, dict, dict]:
        await trolleys.create_trolley("worker-01")
        group = await resources.create_resource_group(
            "worker-01",
            "gpu-workers",
            "task_lease",
            configuration={"lease_seconds": 120},
            attributes={"location": "lab-a"},
        )
        resource = await resources.create_resource(
            "gpu-workers",
            "gpu-0",
            "accelerator/custom",
            attributes={"model": "H100"},
        )
        updated_group = await resources.update_resource_group(
            "gpu-workers",
            allocation_mode="vendor-specific-mode",
        )
        updated_resource = await resources.update_resource(
            "gpu-workers",
            "gpu-0",
            kind="vendor-specific-kind",
            is_active=False,
        )
        return group, resource, updated_group, updated_resource

    group, resource, updated_group, updated_resource = app_client.portal.call(manage)
    assert group["allocation_mode"] == "task_lease"
    assert group["configuration"] == {"lease_seconds": 120}
    assert group["attributes"] == {"location": "lab-a"}
    assert resource["kind"] == "accelerator/custom"
    assert resource["attributes"] == {"model": "H100"}
    assert updated_group["allocation_mode"] == "vendor-specific-mode"
    assert updated_resource["kind"] == "vendor-specific-kind"
    assert updated_resource["is_active"] is False


def test_management_rejects_missing_references(app_client) -> None:
    async def create_provider() -> None:
        await providers.create_provider("primary", "http://provider.test", "missing")

    async def create_model() -> None:
        await models.create_model("coder", "provider-model", "missing")

    with pytest.raises(DoesNotExist):
        app_client.portal.call(create_provider)
    with pytest.raises(DoesNotExist):
        app_client.portal.call(create_model)
