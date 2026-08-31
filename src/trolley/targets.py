from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from trolley.domain.targets import TargetKind

_configured_path: str | Path = "targets.yaml"


@dataclass(frozen=True)
class TargetDefinition:
    name: str
    kind: TargetKind
    configuration: dict[str, Any]


def configure_targets(path: str | Path) -> None:
    global _configured_path
    _configured_path = path


def get_targets() -> dict[str, TargetDefinition]:
    return load_targets(_configured_path)


def load_targets(path: str | Path) -> dict[str, TargetDefinition]:
    target_path = Path(path)
    if not target_path.exists():
        return {}
    if target_path.stat().st_mode & 0o077:
        raise ValueError("targets file must not be accessible by group or others")

    document = yaml.safe_load(target_path.read_text()) or {}
    if not isinstance(document, dict) or not isinstance(document.get("targets", {}), dict):
        raise ValueError("targets file must contain a 'targets' mapping")

    definitions = {}
    for name, value in document.get("targets", {}).items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("target names must be non-empty strings")
        if not isinstance(value, dict):
            raise ValueError(f"target configuration must be a mapping: {name}")
        try:
            kind = TargetKind(value.get("kind"))
        except ValueError as error:
            raise ValueError(f"unsupported target kind for {name}: {value.get('kind')}") from error
        configuration = {key: item for key, item in value.items() if key != "kind"}
        if kind == TargetKind.POSTGRESQL and not configuration.get("url"):
            raise ValueError(f"PostgreSQL target needs 'url': {name}")
        if kind == TargetKind.HTTP and not configuration.get("base_url"):
            raise ValueError(f"HTTP target needs 'base_url': {name}")
        definitions[name] = TargetDefinition(name, kind, configuration)
    return definitions
