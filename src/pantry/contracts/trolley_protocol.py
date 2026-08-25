import json
from typing import Any, ClassVar, Literal, Self

from pydantic import BaseModel, Field, model_validator

MAX_TROLLEY_MESSAGE_BYTES = 64 * 1024
MAX_AGENT_REPORTS = 100


class SizeLimitedMessage(BaseModel):
    max_message_bytes: ClassVar[int] = MAX_TROLLEY_MESSAGE_BYTES

    @model_validator(mode="after")
    def validate_message_size(self) -> Self:
        size = len(json.dumps(self.model_dump(mode="json"), separators=(",", ":")).encode())
        if size > self.max_message_bytes:
            raise ValueError(f"message must be at most {self.max_message_bytes} bytes")
        return self


class HelloMessage(SizeLimitedMessage):
    type: Literal["hello"]
    version: str = Field(min_length=1, max_length=64)
    runtime_info: dict[str, Any]
    agents: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_AGENT_REPORTS)


class HeartbeatMessage(SizeLimitedMessage):
    type: Literal["heartbeat"]
    metrics: dict[str, Any]
    agents: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_AGENT_REPORTS)
