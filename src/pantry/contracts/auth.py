from dataclasses import dataclass

from pantry.models import Account, ApiKey


@dataclass(frozen=True, slots=True)
class AuthResult:
    status: str
    account: Account | None = None
    api_key: ApiKey | None = None
