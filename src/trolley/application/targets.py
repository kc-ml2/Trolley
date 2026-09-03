from typing import Any

from trolley.config import Settings
from trolley.connectors import database
from trolley.persistence.models import Target
from trolley.targets import TargetDefinition, load_targets


def configured_targets(settings: Settings) -> dict[str, TargetDefinition]:
    return load_targets(settings.targets)


async def sync_targets(settings: Settings) -> None:
    definitions = configured_targets(settings)
    existing = {target.name: target for target in await Target.all()}
    for name, definition in definitions.items():
        target = existing.get(name)
        if target is None:
            await Target.create(name=name, kind=definition.kind)
        elif target.kind != definition.kind or not target.is_active:
            target.kind = definition.kind
            target.is_active = True
            await target.save()
    for name, target in existing.items():
        if name not in definitions and target.is_active:
            target.is_active = False
            await target.save()


async def list_targets(settings: Settings) -> list[dict[str, Any]]:
    definitions = configured_targets(settings)
    return [
        {"name": definition.name, "kind": definition.kind}
        for definition in sorted(definitions.values(), key=lambda item: item.name)
    ]


async def test_target_connection(settings: Settings, name: str) -> dict[str, Any]:
    definition = configured_targets(settings).get(name)
    if definition is None:
        raise ValueError(f"Unknown target: {name}")
    result = await database.test_connection(definition.configuration)
    return {"target": definition.name, "kind": definition.kind, **result}


async def get_target_schema(settings: Settings, name: str) -> dict[str, Any]:
    definition = configured_targets(settings).get(name)
    if definition is None:
        raise ValueError(f"Unknown target: {name}")
    schema = await database.inspect_schema(definition.configuration)
    return {"target": definition.name, "kind": definition.kind, "schemas": schema}
