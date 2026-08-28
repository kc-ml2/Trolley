from typing import Any

from trolley.application.presenters import present_target
from trolley.connectors import database
from trolley.domain.targets import TargetKind
from trolley.persistence.models import Target


async def list_targets() -> list[dict[str, Any]]:
    return [present_target(target) for target in await Target.all().order_by("name")]


async def create_target(
    name: str,
    kind: TargetKind,
    configuration: dict[str, Any],
    secret_env: str | None = None,
) -> dict[str, Any]:
    target = await Target.create(
        name=name.strip(),
        kind=kind,
        configuration=configuration,
        secret_env=secret_env,
    )
    return present_target(target)


async def test_target_connection(name: str) -> dict[str, Any]:
    target = await Target.get(name=name, is_active=True)
    if target.kind != TargetKind.POSTGRESQL:
        raise ValueError("Connection testing currently supports only PostgreSQL targets")
    result = await database.test_connection(target.configuration, target.secret_env)
    return {"target": target.name, "kind": target.kind, **result}
