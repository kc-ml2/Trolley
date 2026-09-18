"""Explicit group provisioning for tests; never grant access automatically."""

from trolley.persistence.models import Group, GroupMembership, GroupTargetGrant, Target


async def allow(user, target_name):
    group, _ = await Group.get_or_create(name=f"test-{user.id}")
    target = await Target.get(name=target_name)
    await GroupMembership.get_or_create(user=user, group=group)
    await GroupTargetGrant.get_or_create(group=group, target=target)


async def revoke(user):
    await GroupMembership.filter(user=user).delete()
