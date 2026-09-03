from dataclasses import dataclass
from typing import Any

from trolley.domain.targets import TargetKind

_configured_targets: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class TargetDefinition:
    name: str
    kind: TargetKind
    configuration: dict[str, Any]


def configure_targets(targets: dict[str, dict[str, Any]]) -> None:
    global _configured_targets
    _configured_targets = targets


def get_targets() -> dict[str, TargetDefinition]:
    return load_targets(_configured_targets)


def load_targets(targets: dict[str, dict[str, Any]]) -> dict[str, TargetDefinition]:
    if not isinstance(targets, dict):
        raise ValueError("targets must be a mapping")

    definitions = {}
    for name, value in targets.items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("target names must be non-empty strings")
        if not isinstance(value, dict):
            raise ValueError(f"target configuration must be a mapping: {name}")
        try:
            kind = TargetKind(value.get("kind"))
        except ValueError as error:
            raise ValueError(f"unsupported target kind for {name}: {value.get('kind')}") from error
        configuration = {key: item for key, item in value.items() if key != "kind"}
        if not configuration.get("url"):
            raise ValueError(f"PostgreSQL target needs 'url': {name}")
        definitions[name] = TargetDefinition(name, kind, configuration)
    return definitions
