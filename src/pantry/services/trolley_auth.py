from pantry.domain.accounts import AccountKind
from pantry.models import ApiKey, Trolley
from pantry.services.auth import authenticate_secret


def bearer_token(authorization: str) -> str | None:
    scheme, _, token = authorization.partition(" ")
    return token if scheme.lower() == "bearer" and token else None


async def authenticate_trolley(authorization: str) -> tuple[Trolley, ApiKey] | None:
    token = bearer_token(authorization)
    if token is None:
        return None
    auth = await authenticate_secret(token)
    if (
        auth.status != "authenticated"
        or auth.account is None
        or auth.api_key is None
        or auth.account.kind != AccountKind.TROLLEY
    ):
        return None
    trolley = await Trolley.get_or_none(account=auth.account, is_active=True)
    return (trolley, auth.api_key) if trolley is not None else None


async def trolley_session_is_active(trolley_id: object, api_key_id: object) -> bool:
    return await Trolley.filter(
        id=trolley_id,
        is_active=True,
        account__is_active=True,
        account__api_keys__id=api_key_id,
        account__api_keys__is_active=True,
    ).exists()
