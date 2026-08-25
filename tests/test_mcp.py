from fastapi.testclient import TestClient
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser

from pantry.config import Settings
from pantry.domain.accounts import AccountKind, AccountRole
from pantry.main import create_app
from pantry.mcp.auth import ADMIN_SCOPE, PantryTokenVerifier
from pantry.mcp.server import create_mcp_server
from pantry.models import Account
from pantry.services.auth import create_api_key

ADMIN_SECRET = "sk-pantry-admin"
USER_SECRET = "sk-pantry-user"


async def seed_users() -> None:
    admin = await Account.create(email="admin@example.com", role=AccountRole.ADMIN)
    user = await Account.create(email="user@example.com", role=AccountRole.USER)
    await create_api_key(account=admin, name="Admin MCP", secret=ADMIN_SECRET)
    await create_api_key(account=user, name="User", secret=USER_SECRET)


def initialize_payload() -> dict:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }


def test_mcp_http_requires_admin_role(tmp_path) -> None:
    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    with TestClient(app) as client:
        client.portal.call(seed_users)
        headers = {"Accept": "application/json, text/event-stream"}

        missing = client.post("/mcp/", headers=headers, json=initialize_payload())
        assert missing.status_code == 401

        user = client.post(
            "/mcp/",
            headers={**headers, "Authorization": f"Bearer {USER_SECRET}"},
            json=initialize_payload(),
        )
        assert user.status_code == 403

        admin = client.post(
            "/mcp/",
            headers={**headers, "Authorization": f"Bearer {ADMIN_SECRET}"},
            json=initialize_payload(),
        )
        assert admin.status_code == 200
        assert admin.json()["result"]["serverInfo"]["name"] == "pantry-admin"


def test_mcp_token_verifier_only_grants_admin_scope(tmp_path) -> None:
    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    with TestClient(app) as client:
        client.portal.call(seed_users)
        verifier = PantryTokenVerifier()

        admin_token = client.portal.call(verifier.verify_token, ADMIN_SECRET)
        user_token = client.portal.call(verifier.verify_token, USER_SECRET)
        invalid_token = client.portal.call(verifier.verify_token, "invalid")

        assert admin_token is not None
        assert admin_token.scopes == [ADMIN_SCOPE]
        assert user_token is not None
        assert user_token.scopes == []
        assert invalid_token is None


def test_trolley_account_never_receives_admin_scope(tmp_path) -> None:
    trolley_secret = "sk-pantry-trolley-admin"
    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    with TestClient(app) as client:

        async def seed_invalid_trolley_admin() -> None:
            trolley = await Account.create(
                kind=AccountKind.TROLLEY,
                name="test-trolley",
                role=AccountRole.ADMIN,
            )
            await create_api_key(
                account=trolley,
                name="Trolley Runtime",
                secret=trolley_secret,
            )

        client.portal.call(seed_invalid_trolley_admin)
        token = client.portal.call(PantryTokenVerifier().verify_token, trolley_secret)
        assert token is not None
        assert token.scopes == []


def test_mcp_registers_minimal_management_tools() -> None:
    server = create_mcp_server("http://localhost:8000")

    async def list_tools() -> set[str]:
        return {tool.name for tool in await server.list_tools()}

    import asyncio

    names = asyncio.run(list_tools())
    assert names == {
        "list_credentials",
        "create_credential",
        "update_credential",
        "list_providers",
        "create_provider",
        "update_provider",
        "list_models",
        "create_model",
        "update_model",
        "list_accounts",
        "create_account",
        "update_account",
        "list_api_keys",
        "create_api_key",
        "update_api_key",
        "list_trolleys",
        "create_trolley",
        "update_trolley",
        "list_resource_groups",
        "create_resource_group",
        "update_resource_group",
        "list_resources",
        "create_resource",
        "update_resource",
        "list_agents",
        "create_agent",
        "update_agent",
    }


def test_admin_issues_user_api_key_through_mcp(tmp_path) -> None:
    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    server = create_mcp_server("http://localhost:8000")

    with TestClient(app) as client:
        client.portal.call(seed_users)

        async def call_tools() -> tuple[object, object, object]:
            token = await PantryTokenVerifier().verify_token(ADMIN_SECRET)
            assert token is not None
            context_token = auth_context_var.set(AuthenticatedUser(token))
            try:
                account = await server.call_tool(
                    "create_account",
                    {
                        "kind": AccountKind.HUMAN.value,
                        "email": "new-user@example.com",
                        "name": "New User",
                    },
                )
                account_id = account.structured_content["id"]
                issued = await server.call_tool(
                    "create_api_key",
                    {"account_id": account_id, "name": "Default"},
                )
                listed = await server.call_tool(
                    "list_api_keys",
                    {"account_id": account_id},
                )
                return account, issued, listed
            finally:
                auth_context_var.reset(context_token)

        account, issued, listed = client.portal.call(call_tools)
        secret = issued.structured_content["secret"]
        assert account.structured_content["kind"] == "human"
        assert account.structured_content["role"] == "user"
        assert secret.startswith("sk-pantry-")
        assert secret not in str(listed)
        assert listed.structured_content["result"][0]["key_prefix"] == secret[:20]

        auth = client.portal.call(PantryTokenVerifier().verify_token, secret)
        assert auth is not None
        assert auth.scopes == []

        key_id = issued.structured_content["id"]

        async def disable_key() -> None:
            token = await PantryTokenVerifier().verify_token(ADMIN_SECRET)
            assert token is not None
            context_token = auth_context_var.set(AuthenticatedUser(token))
            try:
                await server.call_tool(
                    "update_api_key",
                    {"api_key_id": key_id, "is_active": False},
                )
            finally:
                auth_context_var.reset(context_token)

        client.portal.call(disable_key)
        rejected = client.portal.call(PantryTokenVerifier().verify_token, secret)
        assert rejected is None


def test_mcp_tool_calls_management_layer(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("MCP_UPSTREAM_KEY", "upstream-secret")
    app = create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))
    server = create_mcp_server("http://localhost:8000")

    with TestClient(app) as client:
        client.portal.call(seed_users)

        async def call_tools() -> tuple[object, object, object]:
            token = await PantryTokenVerifier().verify_token(ADMIN_SECRET)
            assert token is not None
            context_token = auth_context_var.set(AuthenticatedUser(token))
            try:
                credential = await server.call_tool(
                    "create_credential",
                    {"name": "mcp-key", "secret_env": "MCP_UPSTREAM_KEY"},
                )
                provider = await server.call_tool(
                    "create_provider",
                    {
                        "name": "mcp-provider",
                        "base_url": "http://provider.test/v1",
                        "credential_name": "mcp-key",
                    },
                )
                model = await server.call_tool(
                    "create_model",
                    {
                        "alias": "mcp-model",
                        "upstream_model": "provider-model",
                        "provider_name": "mcp-provider",
                    },
                )
                return credential, provider, model
            finally:
                auth_context_var.reset(context_token)

        credential, provider, model = client.portal.call(call_tools)
        assert credential.structured_content["secret_configured"] is True
        assert "upstream-secret" not in str(credential)
        assert provider.structured_content["credential_name"] == "mcp-key"
        assert model.structured_content["alias"] == "mcp-model"
