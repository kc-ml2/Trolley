import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect
from websockets.exceptions import ConnectionClosedOK

from pantry.config import Settings
from pantry.domain.accounts import AccountKind
from pantry.main import create_app
from pantry.management import (
    accounts,
    agents,
    api_keys,
    credentials,
    models,
    providers,
    resources,
    trolleys,
)
from pantry.models import ApiKey, Trolley
from trolley.client import PantryClient
from trolley.config import TrolleySettings


def create_test_app(tmp_path):
    return create_app(Settings(_env_file=None, database_url=f"sqlite://{tmp_path}/test.db"))


def test_trolley_websocket_receives_configuration_and_heartbeats(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "  provider-secret  ")
    app = create_test_app(tmp_path)
    with TestClient(app) as client:

        async def seed():
            created = await trolleys.create_trolley("gpu-01")
            group = await resources.create_resource_group(
                "gpu-01",
                "baremetal",
                "time_window",
                configuration={"minimum_minutes": 30},
                attributes={"location": "lab-a"},
            )
            resource = await resources.create_resource(
                "baremetal",
                "server-01",
                "host",
                attributes={"architecture": "x86_64"},
            )
            await credentials.create_credential("litellm-key", "LITELLM_API_KEY")
            await providers.create_provider(
                "litellm",
                "http://litellm.test/v1",
                "litellm-key",
            )
            await models.create_model("hulk", "upstream-hulk", "litellm")
            await agents.create_agent(
                "reservation",
                "time_window",
                model_alias="hulk",
                configuration={"interval": 60},
            )
            return created, group, resource

        created, group, resource = client.portal.call(seed)
        headers = {"Authorization": f"Bearer {created.api_key}"}
        with client.websocket_connect("/trolley/connect", headers=headers) as websocket:
            websocket.send_json(
                {
                    "type": "hello",
                    "version": "0.1.0",
                    "runtime_info": {"hostname": "gpu-01", "os": "Linux"},
                    "agents": [{"name": "reservation", "version": "1.0"}],
                }
            )
            configuration = websocket.receive_json()
            assert configuration == {
                "type": "configuration",
                "providers": {
                    "litellm": {
                        "base_url": "http://litellm.test/v1",
                        "api_key": "provider-secret",
                    }
                },
                "resource_groups": [
                    {
                        "id": group["id"],
                        "name": "baremetal",
                        "allocation_mode": "time_window",
                        "configuration": {"minimum_minutes": 30},
                        "attributes": {"location": "lab-a"},
                        "resources": [
                            {
                                "id": resource["id"],
                                "name": "server-01",
                                "kind": "host",
                                "attributes": {"architecture": "x86_64"},
                            }
                        ],
                        "agents": {
                            "reservation": {
                                "configuration": {"interval": 60},
                                "model": {
                                    "alias": "hulk",
                                    "upstream_model": "upstream-hulk",
                                    "provider": "litellm",
                                },
                            }
                        },
                    }
                ],
            }

            websocket.send_json(
                {
                    "type": "heartbeat",
                    "metrics": {"memory_percent": 30.0},
                    "agents": [{"name": "reservation", "status": "running"}],
                }
            )
            assert websocket.receive_json() == {"type": "heartbeat_ack"}

        async def load_trolley() -> Trolley:
            return await Trolley.get(id=created.id)

        trolley = client.portal.call(load_trolley)
        assert trolley.version == "0.1.0"
        assert trolley.runtime_info["hostname"] == "gpu-01"
        assert trolley.metrics["memory_percent"] == 30.0
        assert trolley.last_seen_at is not None


def test_agents_match_opaque_group_mode_without_unneeded_secrets(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:

        async def seed():
            created = await trolleys.create_trolley("worker")
            group = await resources.create_resource_group(
                "worker",
                "gpu-workers",
                "task_lease",
            )
            await agents.create_agent(
                "container_execution",
                "task_lease",
                configuration={"runtime": "docker"},
            )
            await agents.create_agent("reservation", "time_window")
            await resources.create_resource(
                "gpu-workers",
                "disabled-gpu",
                "gpu",
            )
            await resources.update_resource(
                "gpu-workers",
                "disabled-gpu",
                is_active=False,
            )
            await resources.create_resource_group(
                "worker",
                "disabled-group",
                "time_window",
            )
            await resources.update_resource_group("disabled-group", is_active=False)
            return created, group

        created, group = client.portal.call(seed)
        headers = {"Authorization": f"Bearer {created.api_key}"}
        with client.websocket_connect("/trolley/connect", headers=headers) as websocket:
            websocket.send_json(
                {
                    "type": "hello",
                    "version": "0.1.0",
                    "runtime_info": {},
                    "agents": [],
                }
            )
            assert websocket.receive_json() == {
                "type": "configuration",
                "providers": {},
                "resource_groups": [
                    {
                        "id": group["id"],
                        "name": "gpu-workers",
                        "allocation_mode": "task_lease",
                        "configuration": {},
                        "attributes": {},
                        "resources": [],
                        "agents": {
                            "container_execution": {
                                "configuration": {"runtime": "docker"},
                            }
                        },
                    }
                ],
            }


def test_unmatched_agent_does_not_expose_its_provider_secret(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("UNUSED_API_KEY", "must-not-be-sent")
    app = create_test_app(tmp_path)
    with TestClient(app) as client:

        async def seed():
            created = await trolleys.create_trolley("worker")
            group = await resources.create_resource_group("worker", "custom", "matched-mode")
            await credentials.create_credential("unused-key", "UNUSED_API_KEY")
            await providers.create_provider("unused", "https://unused.test/v1", "unused-key")
            await models.create_model("unused-model", "upstream-unused", "unused")
            await agents.create_agent("unmatched", "other-mode", model_alias="unused-model")
            return created, group

        created, group = client.portal.call(seed)
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:
            websocket.send_json(
                {
                    "type": "hello",
                    "version": "0.1.0",
                    "runtime_info": {},
                    "agents": [],
                }
            )
            assert websocket.receive_json() == {
                "type": "configuration",
                "providers": {},
                "resource_groups": [
                    {
                        "id": group["id"],
                        "name": "custom",
                        "allocation_mode": "matched-mode",
                        "configuration": {},
                        "attributes": {},
                        "resources": [],
                        "agents": {},
                    }
                ],
            }


@pytest.mark.parametrize(
    "message",
    [
        "{",
        json.dumps(
            {
                "type": "heartbeat",
                "version": "0.1.0",
                "runtime_info": {},
            }
        ),
    ],
)
def test_invalid_trolley_message_closes_with_policy_violation(tmp_path, message: str) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "worker")
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:
            websocket.send_text(message)
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 1008


def test_human_account_cannot_connect_as_trolley(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:

        async def create_human_key() -> str:
            account = await accounts.create_account(
                AccountKind.HUMAN,
                email="human@example.com",
            )
            return (await api_keys.issue_api_key(account["id"], "Human key")).secret

        secret = client.portal.call(create_human_key)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                "/trolley/connect",
                headers={"Authorization": f"Bearer {secret}"},
            ):
                pass
        assert exc.value.code == 1008


def test_disabling_trolley_rejects_websocket(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "gpu-01")

        async def disable_trolley() -> None:
            await trolleys.update_trolley("gpu-01", is_active=False)

        client.portal.call(disable_trolley)
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                "/trolley/connect",
                headers={"Authorization": f"Bearer {created.api_key}"},
            ):
                pass
        assert exc.value.code == 1008


def test_revoked_api_key_before_hello_closes_existing_connection(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "worker")
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:

            async def revoke_key() -> None:
                key = await ApiKey.get(account_id=created.account_id)
                await api_keys.update_api_key(str(key.id), is_active=False)

            client.portal.call(revoke_key)
            websocket.send_json(
                {"type": "hello", "version": "0.1.0", "runtime_info": {}, "agents": []}
            )
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 1008


def test_revoked_api_key_closes_existing_connection_on_next_message(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "worker")
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:
            websocket.send_json(
                {"type": "hello", "version": "0.1.0", "runtime_info": {}, "agents": []}
            )
            websocket.receive_json()

            async def revoke_key() -> None:
                key = await ApiKey.get(account_id=created.account_id)
                await api_keys.update_api_key(str(key.id), is_active=False)

            client.portal.call(revoke_key)
            websocket.send_json({"type": "heartbeat", "metrics": {}, "agents": []})
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 1008


def test_disabled_trolley_closes_existing_connection_on_next_message(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "worker")
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:
            websocket.send_json(
                {"type": "hello", "version": "0.1.0", "runtime_info": {}, "agents": []}
            )
            websocket.receive_json()

            async def disable_trolley() -> None:
                await trolleys.update_trolley("worker", is_active=False)

            client.portal.call(disable_trolley)
            websocket.send_json({"type": "heartbeat", "metrics": {}, "agents": []})
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 1008


@pytest.mark.parametrize(
    "message",
    [
        {"type": "hello", "version": "x" * 65, "runtime_info": {}, "agents": []},
        {
            "type": "hello",
            "version": "0.1.0",
            "runtime_info": {"payload": "x" * (64 * 1024)},
            "agents": [],
        },
        {
            "type": "hello",
            "version": "0.1.0",
            "runtime_info": {},
            "agents": [{}] * 101,
        },
    ],
)
def test_oversized_hello_closes_with_policy_violation(tmp_path, message: dict) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "worker")
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:
            websocket.send_json(message)
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 1008


def test_oversized_heartbeat_is_rejected(tmp_path) -> None:
    app = create_test_app(tmp_path)
    with TestClient(app) as client:
        created = client.portal.call(trolleys.create_trolley, "worker")
        with client.websocket_connect(
            "/trolley/connect",
            headers={"Authorization": f"Bearer {created.api_key}"},
        ) as websocket:
            websocket.send_json(
                {"type": "hello", "version": "0.1.0", "runtime_info": {}, "agents": []}
            )
            websocket.receive_json()
            websocket.send_json(
                {"type": "heartbeat", "metrics": {"payload": "x" * (64 * 1024)}, "agents": []}
            )
            with pytest.raises(WebSocketDisconnect) as exc:
                websocket.receive_json()
            assert exc.value.code == 1008


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.responses = iter(
            [
                json.dumps(
                    {
                        "type": "configuration",
                        "providers": {
                            "litellm": {
                                "base_url": "http://litellm.test/v1",
                                "api_key": "memory-only-secret",
                            }
                        },
                        "resource_groups": [
                            {
                                "name": "baremetal",
                                "agents": {"reservation": {"model": "hulk"}},
                            }
                        ],
                    }
                ),
                json.dumps({"type": "heartbeat_ack"}),
            ]
        )

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        try:
            return next(self.responses)
        except StopIteration as exc:
            raise ConnectionClosedOK(None, None) from exc


@pytest.mark.parametrize(
    "pantry_url",
    [
        "pantry.test",
        "ftp://pantry.test",
        "https://user:password@pantry.test",
        "https://pantry.test?token=secret",
        "https://pantry.test#fragment",
    ],
)
def test_runtime_rejects_invalid_pantry_urls(pantry_url: str) -> None:
    with pytest.raises(ValidationError):
        TrolleySettings(
            PANTRY_URL=pantry_url,
            PANTRY_API_KEY="sk-pantry-trolley",
        )


def test_runtime_keeps_configuration_in_memory(monkeypatch) -> None:
    settings = TrolleySettings(
        PANTRY_URL="http://pantry.test",
        PANTRY_API_KEY="sk-pantry-trolley",
        TROLLEY_HEARTBEAT_INTERVAL=0.01,
    )
    runtime = PantryClient(settings)
    websocket = FakeWebSocket()
    monkeypatch.setattr("trolley.client.runtime_info", lambda: {"hostname": "test"})
    monkeypatch.setattr("trolley.client.runtime_metrics", lambda: {"memory_percent": 1})

    with pytest.raises(ConnectionClosedOK):
        asyncio.run(runtime.session(websocket))

    assert runtime.configuration.providers["litellm"]["api_key"] == "memory-only-secret"
    assert runtime.configuration.resource_groups == [
        {
            "name": "baremetal",
            "agents": {"reservation": {"model": "hulk"}},
        }
    ]
    assert websocket.sent[0]["type"] == "hello"
    assert websocket.sent[1]["type"] == "heartbeat"
