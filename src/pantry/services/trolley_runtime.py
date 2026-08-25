from datetime import UTC, datetime

from pantry.contracts.trolley_protocol import HeartbeatMessage, HelloMessage
from pantry.models import Trolley


async def record_hello(trolley: Trolley, message: HelloMessage) -> None:
    trolley.version = message.version
    trolley.runtime_info = message.runtime_info
    trolley.agents = message.agents
    trolley.last_seen_at = datetime.now(UTC)
    await trolley.save()


async def record_heartbeat(trolley: Trolley, message: HeartbeatMessage) -> None:
    trolley.metrics = message.metrics
    trolley.agents = message.agents
    trolley.last_seen_at = datetime.now(UTC)
    await trolley.save()
