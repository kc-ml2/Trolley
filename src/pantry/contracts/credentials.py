from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CredentialResult:
    status: str
    authorization: str | None = None
