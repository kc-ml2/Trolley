import os

from pantry.contracts.credentials import CredentialResult
from pantry.models import Credential


def resolve_credential(credential: Credential | None) -> CredentialResult:
    if credential is None:
        return CredentialResult(status="not_configured")
    if not credential.is_active:
        return CredentialResult(status="inactive")

    secret = os.getenv(credential.secret_env, "").strip()
    if not secret:
        return CredentialResult(status="missing_secret")
    return CredentialResult(status="configured", authorization=f"Bearer {secret}")
