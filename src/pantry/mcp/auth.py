from mcp.server.auth.provider import AccessToken

from pantry.domain.accounts import AccountKind, AccountRole
from pantry.services.auth import authenticate_secret

ADMIN_SCOPE = "pantry:admin"


class PantryTokenVerifier:
    async def verify_token(self, token: str) -> AccessToken | None:
        auth = await authenticate_secret(token)
        if auth.status != "authenticated" or auth.account is None:
            return None

        is_human_admin = (
            auth.account.kind == AccountKind.HUMAN and auth.account.role == AccountRole.ADMIN
        )
        scopes = [ADMIN_SCOPE] if is_human_admin else []
        return AccessToken(
            token="",
            client_id=str(auth.api_key.id) if auth.api_key else str(auth.account.id),
            subject=str(auth.account.id),
            scopes=scopes,
        )
