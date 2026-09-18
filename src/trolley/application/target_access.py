"""Group membership is the only Target boundary, including for administrators."""

from trolley.auth.context import AuthContext
from trolley.domain.users import UserRole
from trolley.persistence.models import Group, GroupTargetGrant, Target, User


async def member_target_names(context: AuthContext) -> set[str]:
    user = await User.get_or_none(id=context.user_id, is_active=True)
    if user is None:
        return set()
    return set(
        await GroupTargetGrant.filter(
            group__memberships__user=user, target__is_active=True
        ).values_list("target__name", flat=True)
    )


async def accessible_target_names(context: AuthContext) -> set[str]:
    user = await User.get_or_none(id=context.user_id, is_active=True)
    if user is None or context.role not in (UserRole.ADMIN, UserRole.DEVELOPER):
        return set()
    if user.role != context.role:
        return set()
    return await member_target_names(context)


async def require_target(context: AuthContext, name: str) -> Target:
    if name not in await accessible_target_names(context):
        raise PermissionError("Target unavailable or access denied")
    return await Target.get(name=name, is_active=True)


async def set_target_access(
    name: str, allowed: bool, email: str | None = None, group_name: str | None = None
) -> dict:
    """Local operator only. Direct user grants are no longer supported."""
    if email is not None or not group_name:
        raise ValueError("Target access requires a group; direct user grants are unsupported")
    target = await Target.get(name=name, is_active=True)
    group = await Group.get(name=group_name.strip())
    if allowed:
        await GroupTargetGrant.get_or_create(target=target, group=group)
    else:
        await GroupTargetGrant.filter(target=target, group=group).delete()
    return {"target": name, "group_name": group_name, "allowed": allowed}


async def list_target_grants() -> dict:
    return {"groups": await GroupTargetGrant.all().values("target__name", "group__name")}
