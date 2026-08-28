from dataclasses import dataclass

from trolley.auth.enums import Scope


@dataclass(frozen=True, slots=True)
class ToolPolicy:
    scope: Scope
    required_text: tuple[str, ...] = ()
