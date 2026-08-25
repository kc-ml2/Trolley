from pantry.management.validation import require_text
from pantry.models import Resource, ResourceGroup, Trolley


def serialize_resource(resource: Resource) -> dict:
    return {
        "id": str(resource.id),
        "resource_group": resource.group.name,
        "name": resource.name,
        "kind": resource.kind,
        "attributes": resource.attributes,
        "is_active": resource.is_active,
    }


def serialize_resource_group(group: ResourceGroup) -> dict:
    return {
        "id": str(group.id),
        "trolley": group.trolley.name,
        "name": group.name,
        "allocation_mode": group.allocation_mode,
        "configuration": group.configuration,
        "attributes": group.attributes,
        "is_active": group.is_active,
    }


async def list_resource_groups() -> list[dict]:
    groups = await ResourceGroup.all().prefetch_related("trolley").order_by("name")
    return [serialize_resource_group(group) for group in groups]


async def create_resource_group(
    trolley_name: str,
    name: str,
    allocation_mode: str,
    *,
    configuration: dict | None = None,
    attributes: dict | None = None,
) -> dict:
    trolley = await Trolley.get(name=require_text(trolley_name, "trolley_name"))
    group = await ResourceGroup.create(
        trolley=trolley,
        name=require_text(name, "name"),
        allocation_mode=require_text(allocation_mode, "allocation_mode"),
        configuration=configuration or {},
        attributes=attributes or {},
    )
    return serialize_resource_group(group)


async def update_resource_group(
    name: str,
    *,
    allocation_mode: str | None = None,
    configuration: dict | None = None,
    attributes: dict | None = None,
    is_active: bool | None = None,
) -> dict:
    group = await ResourceGroup.get(name=require_text(name, "name")).prefetch_related("trolley")
    if allocation_mode is not None:
        group.allocation_mode = require_text(allocation_mode, "allocation_mode")
    if configuration is not None:
        group.configuration = configuration
    if attributes is not None:
        group.attributes = attributes
    if is_active is not None:
        group.is_active = is_active
    await group.save()
    return serialize_resource_group(group)


async def list_resources(resource_group: str | None = None) -> list[dict]:
    query = Resource.all()
    if resource_group is not None:
        query = query.filter(group__name=require_text(resource_group, "resource_group"))
    resources = await query.prefetch_related("group").order_by("group__name", "name")
    return [serialize_resource(resource) for resource in resources]


async def create_resource(
    resource_group: str,
    name: str,
    kind: str,
    *,
    attributes: dict | None = None,
) -> dict:
    group = await ResourceGroup.get(name=require_text(resource_group, "resource_group"))
    resource = await Resource.create(
        group=group,
        name=require_text(name, "name"),
        kind=require_text(kind, "kind"),
        attributes=attributes or {},
    )
    return serialize_resource(resource)


async def update_resource(
    resource_group: str,
    name: str,
    *,
    kind: str | None = None,
    attributes: dict | None = None,
    is_active: bool | None = None,
) -> dict:
    resource = await Resource.get(
        group__name=require_text(resource_group, "resource_group"),
        name=require_text(name, "name"),
    ).prefetch_related("group")
    if kind is not None:
        resource.kind = require_text(kind, "kind")
    if attributes is not None:
        resource.attributes = attributes
    if is_active is not None:
        resource.is_active = is_active
    await resource.save()
    return serialize_resource(resource)
