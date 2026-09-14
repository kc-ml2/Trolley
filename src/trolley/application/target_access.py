"""Target grants authorize exploration, never Operation publication."""

from trolley.auth.context import AuthContext
from trolley.auth.roles import normalize_email
from trolley.domain.users import UserRole
from trolley.persistence.models import Group, GroupTargetGrant, Target, TargetGrant, User


async def accessible_target_names(context: AuthContext) -> set[str]:
    user = await User.get_or_none(id=context.user_id, is_active=True)
    if user is None:
        return set()
    if context.role == UserRole.ADMIN and user.role == UserRole.ADMIN:
        return set(await Target.filter(is_active=True).values_list("name", flat=True))
    if context.role != UserRole.DEVELOPER or user.role != UserRole.DEVELOPER:
        return set()
    direct = await TargetGrant.filter(user=user, target__is_active=True).values_list(
        "target__name", flat=True
    )
    grouped = await GroupTargetGrant.filter(
        group__memberships__user=user, target__is_active=True
    ).values_list("target__name", flat=True)
    return set(direct) | set(grouped)


async def require_target(context: AuthContext, name: str) -> Target:
    if name not in await accessible_target_names(context):
        raise PermissionError("Target unavailable or access denied")
    return await Target.get(name=name, is_active=True)


async def set_target_access(
    name: str,
    allowed: bool,
    email: str | None = None,
    group_name: str | None = None,
) -> dict:
    """Admin-only MCP entry point; grants do not assign the developer role."""
    if bool(email) == bool(group_name):
        raise ValueError("Provide exactly one of email or group_name")
    target = await Target.get(name=name, is_active=True)
    if email:
        user = await User.get(email=normalize_email(email), is_active=True)
        model, principal = TargetGrant, {"user": user}
    else:
        group = await Group.get(name=group_name.strip())
        model, principal = GroupTargetGrant, {"group": group}
    if allowed:
        await model.get_or_create(target=target, **principal)
    else:
        await model.filter(target=target, **principal).delete()
    return {"target": name, "email": email, "group_name": group_name, "allowed": allowed}


async def list_target_grants() -> dict:
    return {
        "users": await TargetGrant.all().values("target__name", "user__email"),
        "groups": await GroupTargetGrant.all().values("target__name", "group__name"),
    }
