import pytest
from fastapi.testclient import TestClient

from trolley.config import Settings
from trolley.main import create_app
from trolley.mcp.token_verifier import TrolleyTokenVerifier
from trolley.persistence.models import ApiKey, GroupMembership, GroupTargetGrant, User


def settings(tmp_path, key="test-master"):
    return Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        targets={
            name: {"kind": "postgresql", "url": "postgresql://unused/db"}
            for name in ("db", "other")
        },
        provisioning={"key": key},
    )


AUTH = {"Authorization": "Bearer test-master"}
BODY = {"email": "User@Example.com", "targets": ["db"]}


def test_provision_and_reissue(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert client.post("/provision/user", json=BODY).status_code == 401
        assert client.post("/provisioning/api-keys", json=BODY, headers=AUTH).status_code == 404
        response = client.post("/provision/user", json=BODY, headers=AUTH)
        assert response.status_code == 201
        assert response.headers["cache-control"] == "no-store"
        first = response.json()["api_key"]
        second = client.post("/provision/user", json=BODY, headers=AUTH).json()["api_key"]
        assert first != second
        assert (
            client.post(
                "/provision/user", json=BODY, headers={"Authorization": f"Bearer {first}"}
            ).status_code
            == 401
        )

        async def check():
            assert await User.all().count() == 1
            assert (await User.first()).role == "user"
            assert await ApiKey.all().count() == 2
            assert await GroupMembership.all().count() == 1
            assert await GroupTargetGrant.all().count() == 1
            assert await TrolleyTokenVerifier().verify_token(first)
            assert await TrolleyTokenVerifier().verify_token("test-master") is None

        client.portal.call(check)


def test_multiple_targets_additive_and_deduplicated(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:
        first = client.post("/provision/user", json=BODY, headers=AUTH)
        assert first.status_code == 201
        result = client.post(
            "/provision/user", json={**BODY, "targets": [" other ", "other"]}, headers=AUTH
        )
        assert result.status_code == 201
        assert result.json()["targets"] == ["other"]

        async def check():
            assert await ApiKey.all().count() == 2
            assert await GroupMembership.all().count() == 2

        client.portal.call(check)
        result = client.post(
            "/provision/user", json={**BODY, "targets": ["other", "db", "db"]}, headers=AUTH
        )
        assert result.status_code == 201
        assert result.json()["targets"] == ["db", "other"]

        async def check_again():
            assert await ApiKey.all().count() == 3
            assert await GroupMembership.all().count() == 2

        client.portal.call(check_again)


@pytest.mark.parametrize("targets", [[], [""], ["  "], "db", [None], ["x" * 256]])
def test_invalid_targets(tmp_path, targets):
    with TestClient(create_app(settings(tmp_path))) as client:
        assert (
            client.post(
                "/provision/user", json={**BODY, "targets": targets}, headers=AUTH
            ).status_code
            == 422
        )


def test_inactive_target_rolls_back(tmp_path):
    from trolley.persistence.models import Target

    with TestClient(create_app(settings(tmp_path))) as client:

        async def deactivate():
            await Target.filter(name="other").update(is_active=False)

        client.portal.call(deactivate)
        assert (
            client.post(
                "/provision/user", json={**BODY, "targets": ["db", "other"]}, headers=AUTH
            ).status_code
            == 404
        )

        async def check():
            assert await User.all().count() == 0
            assert await ApiKey.all().count() == 0
            assert await GroupTargetGrant.all().count() == 0

        client.portal.call(check)


def test_existing_admin_and_inactive_account(tmp_path):
    with TestClient(create_app(settings(tmp_path))) as client:

        async def seed():
            await User.create(email="user@example.com", name="Original", role="admin")

        client.portal.call(seed)
        assert client.post("/provision/user", json=BODY, headers=AUTH).status_code == 201

        async def check():
            user = await User.get(email="user@example.com")
            assert user.role == "admin" and user.name == "Original"
            user.is_active = False
            await user.save()

        client.portal.call(check)
        assert client.post("/provision/user", json=BODY, headers=AUTH).status_code == 409


@pytest.mark.parametrize("key", [None, ""])
def test_disabled(tmp_path, key):
    with TestClient(create_app(settings(tmp_path, key))) as client:
        assert client.post("/provision/user", json=BODY, headers=AUTH).status_code == 404


def test_bad_target_and_rollback(tmp_path, monkeypatch):
    with TestClient(create_app(settings(tmp_path)), raise_server_exceptions=False) as client:
        assert (
            client.post(
                "/provision/user", json={**BODY, "targets": ["db", "missing"]}, headers=AUTH
            ).status_code
            == 404
        )
        from unittest.mock import AsyncMock

        monkeypatch.setattr(
            "trolley.provisioning.create_api_key", AsyncMock(side_effect=RuntimeError("failure"))
        )
        assert (
            client.post(
                "/provision/user", json={**BODY, "targets": ["db", "other"]}, headers=AUTH
            ).status_code
            == 500
        )

        async def check():
            assert await User.all().count() == 0
            assert await GroupTargetGrant.all().count() == 0
            assert await ApiKey.all().count() == 0

        client.portal.call(check)
