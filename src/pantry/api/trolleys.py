from json import JSONDecodeError, loads

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from pantry.contracts.trolley_protocol import (
    MAX_TROLLEY_MESSAGE_BYTES,
    HeartbeatMessage,
    HelloMessage,
)
from pantry.services.trolley_auth import authenticate_trolley, trolley_session_is_active
from pantry.services.trolley_configuration import build_trolley_configuration
from pantry.services.trolley_runtime import record_heartbeat, record_hello

router = APIRouter(tags=["trolley"])


async def receive_trolley_json(websocket: WebSocket) -> object:
    message = await websocket.receive()
    if message["type"] == "websocket.disconnect":
        raise WebSocketDisconnect(message["code"], message.get("reason"))
    text = message.get("text")
    if text is None:
        raise ValueError("Trolley messages must be JSON text")
    if len(text.encode()) > MAX_TROLLEY_MESSAGE_BYTES:
        raise ValueError(f"message must be at most {MAX_TROLLEY_MESSAGE_BYTES} bytes")
    return loads(text)


@router.websocket("/trolley/connect")
async def connect_trolley(websocket: WebSocket) -> None:
    authentication = await authenticate_trolley(websocket.headers.get("authorization", ""))
    if authentication is None:
        await websocket.close(code=1008, reason="Trolley authentication required")
        return

    trolley, api_key = authentication
    await websocket.accept()
    try:
        payload = await receive_trolley_json(websocket)
        if not await trolley_session_is_active(trolley.id, api_key.id):
            await websocket.close(code=1008, reason="Trolley authorization revoked")
            return
        hello = HelloMessage.model_validate(payload)
        await record_hello(trolley, hello)

        try:
            configuration = await build_trolley_configuration(trolley)
        except ValueError as exc:
            await websocket.send_json({"type": "configuration_error", "message": str(exc)})
            await websocket.close(code=1011, reason="Invalid Trolley configuration")
            return
        await websocket.send_json(configuration)

        while True:
            payload = await receive_trolley_json(websocket)
            if not await trolley_session_is_active(trolley.id, api_key.id):
                await websocket.close(code=1008, reason="Trolley authorization revoked")
                return
            message_type = payload.get("type") if isinstance(payload, dict) else None
            if message_type != "heartbeat":
                raise ValueError("Unsupported Trolley message")
            heartbeat = HeartbeatMessage.model_validate(payload)
            await record_heartbeat(trolley, heartbeat)
            await websocket.send_json({"type": "heartbeat_ack"})
    except WebSocketDisconnect:
        return
    except (JSONDecodeError, ValidationError, ValueError):
        await websocket.close(code=1008, reason="Invalid Trolley message")
