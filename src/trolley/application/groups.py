from typing import Any

from tortoise.transactions import in_transaction

from trolley.auth.roles import normalize_email
from trolley.persistence.models import Group, GroupMembership, User


async def resolve_groups(names: list[str]) -> list[Group]:
    result = []
    for name in sorted(set(names)):
        group = await Group.get_or_none(name=name.strip())
        if group is None:
            raise ValueError(f"Unknown group: {name}")
        result.append(group)
    return result


async def create_group(name: str, description: str = "") -> dict[str, Any]:
    name = name.strip()
    if not name or len(name) > 255:
        raise ValueError("Group name must contain 1 to 255 characters")
    group = await Group.create(name=name, description=description.strip())
    return {"name": group.name, "description": group.description}


async def list_groups() -> list[dict[str, Any]]:
    return await Group.all().order_by("name").values("name", "description")


async def update_group(name: str, description: str) -> dict[str, Any]:
    group = (await resolve_groups([name]))[0]
    group.description = description.strip()
    await group.save()
    return {"name": group.name, "description": group.description}


async def delete_group(name: str) -> dict[str, Any]:
    group = (await resolve_groups([name]))[0]
    await group.delete()
    return {"name": group.name, "deleted": True}


async def set_user_groups(email: str, group_names: list[str]) -> dict[str, Any]:
    """Replace all memberships atomically; an empty list removes all memberships."""
    async with in_transaction():
        selected = await resolve_groups(group_names)
        user = await User.get(email=normalize_email(email), is_active=True)
        await GroupMembership.filter(user=user).delete()
        for group in selected:
            await GroupMembership.get_or_create(group=group, user=user)
    return {"email": user.email, "groups": sorted({g.name for g in selected})}


async def list_group_memberships(
    email: str | None = None, group_name: str | None = None
) -> list[dict]:
    query = GroupMembership.all()
    if email is not None:
        query = query.filter(user__email=normalize_email(email))
    if group_name is not None:
        query = query.filter(group__name=group_name.strip())
    return await query.order_by("group__name", "user__email").values(
        group="group__name", email="user__email"
    )
