from fastapi.testclient import TestClient

from trolley.auth.api_keys import create_api_key
from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import User


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


def test_mcp_http_requires_valid_bearer_token(tmp_path) -> None:
    secret = "sk-trolley-test-admin"
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"admin@example.com"}),
    )
    with TestClient(create_app(settings)) as client:

        async def issue_key() -> None:
            admin = await User.get(email="admin@example.com")
            await create_api_key(admin, "test", secret=secret)

        client.portal.call(issue_key)
        headers = {"Accept": "application/json, text/event-stream"}

        missing = client.post("/mcp/", headers=headers, json=initialize_payload())
        invalid = client.post(
            "/mcp/",
            headers={**headers, "Authorization": "Bearer invalid"},
            json=initialize_payload(),
        )
        valid = client.post(
            "/mcp/",
            headers={**headers, "Authorization": f"Bearer {secret}"},
            json=initialize_payload(),
        )

        assert missing.status_code == 401
        assert invalid.status_code == 401
        assert valid.status_code == 200
        assert valid.json()["result"]["serverInfo"]["name"] == "trolley"
