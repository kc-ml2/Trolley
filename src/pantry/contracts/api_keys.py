from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IssuedApiKey:
    id: str
    name: str
    key_prefix: str
    secret: str
    is_active: bool
