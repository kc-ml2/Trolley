from mcp.server.auth.provider import AccessToken

from trolley.auth.api_keys import hash_secret
from trolley.auth.enums import Scope
from trolley.auth.roles import effective_role
from trolley.domain.users import UserRole
from trolley.persistence.models import ApiKey


class TrolleyTokenVerifier:
    def __init__(self, admin_emails: frozenset[str]) -> None:
        self.admin_emails = admin_emails

    async def verify_token(self, token: str) -> AccessToken | None:
        api_key = await ApiKey.get_or_none(
            secret_hash=hash_secret(token), is_active=True
        ).prefetch_related("user")
        if api_key is None or not api_key.user.is_active:
            return None

        role = effective_role(api_key.user.email, api_key.user.role, self.admin_emails)
        scopes = [Scope.USE]
        if role == UserRole.ADMIN:
            scopes.append(Scope.ADMIN)
        return AccessToken(
            token="",
            client_id=str(api_key.id),
            subject=str(api_key.user.id),
            scopes=scopes,
            claims={"role": role},
        )
