import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

from websockets.asyncio.client import ClientConnection, connect

from trolley import __version__
from trolley.config import TrolleySettings
from trolley.system import runtime_info, runtime_metrics


@dataclass(slots=True)
class RuntimeConfiguration:
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    resource_groups: list[dict[str, Any]] = field(default_factory=list)


class PantryClient:
    def __init__(self, settings: TrolleySettings) -> None:
        self.settings = settings
        self.configuration = RuntimeConfiguration()

    def websocket_url(self) -> str:
        base = self.settings.pantry_url.rstrip("/")
        if base.startswith("https://"):
            base = f"wss://{base.removeprefix('https://')}"
        elif base.startswith("http://"):
            base = f"ws://{base.removeprefix('http://')}"
        return f"{base}/trolley/connect"

    async def run(self) -> None:
        headers = {"Authorization": f"Bearer {self.settings.pantry_api_key}"}
        async for websocket in connect(self.websocket_url(), additional_headers=headers):
            try:
                await self.session(websocket)
            except Exception:
                self.configuration = RuntimeConfiguration()
                continue

    async def session(self, websocket: ClientConnection) -> None:
        await websocket.send(
            json.dumps(
                {
                    "type": "hello",
                    "version": __version__,
                    "runtime_info": runtime_info(),
                    "agents": [],
                }
            )
        )
        message = json.loads(await websocket.recv())
        if message.get("type") != "configuration":
            raise RuntimeError("Pantry did not provide a valid configuration")
        self.configuration = RuntimeConfiguration(
            providers=message.get("providers", {}),
            resource_groups=message.get("resource_groups", []),
        )

        while True:
            await asyncio.sleep(self.settings.heartbeat_interval)
            await self.send_heartbeat(websocket)

    async def send_heartbeat(self, websocket: ClientConnection) -> None:
        await websocket.send(
            json.dumps(
                {
                    "type": "heartbeat",
                    "metrics": runtime_metrics(),
                    "agents": [],
                }
            )
        )
        acknowledgement = json.loads(await websocket.recv())
        if acknowledgement.get("type") != "heartbeat_ack":
            raise RuntimeError("Pantry did not acknowledge heartbeat")
