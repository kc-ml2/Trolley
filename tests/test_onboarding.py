from fastapi.testclient import TestClient

from trolley.config import Settings
from trolley.main import create_app


def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        public_base_url="https://trolley.example.com/root/",
        admin_emails=frozenset({"admin@example.com"}),
    )


def test_discovery_describes_user_managed_bearer_authentication(tmp_path) -> None:
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.get("/.well-known/trolley")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Trolley",
        "mcp_url": "https://trolley.example.com/root/mcp/",
        "onboarding_url": "https://trolley.example.com/root/onboarding.md",
        "authentication": {
            "type": "bearer",
            "secret_input": "user_managed",
            "recommended_environment_variable": "TROLLEY_API_KEY",
        },
    }


def test_onboarding_tells_agent_not_to_request_the_api_key(tmp_path) -> None:
    with TestClient(create_app(settings(tmp_path))) as client:
        response = client.get("/onboarding.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "https://trolley.example.com/root/mcp/" in response.text
    assert "Never ask the user to paste an API key into the conversation" in response.text
    assert "${TROLLEY_API_KEY}" in response.text
    assert "request one from their Trolley administrator" in response.text
    assert "call `list_operations`" in response.text
    assert "call `execute`" in response.text
