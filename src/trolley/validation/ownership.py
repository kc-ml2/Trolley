"""Shared, restricted SQL primitives for caller-owned queries."""

import re

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("Caller query identifiers must be simple SQL identifiers")
    return '"' + value + '"'


def mapped_predicate(owner: dict) -> str:
    if not isinstance(owner, dict) or set(owner) != {
        "source",
        "source_column",
        "match_column",
        "column",
        "json_key",
        "identity",
    }:
        raise ValueError(
            "Mapped ownership requires source, source_column, match_column, "
            "column, json_key and identity"
        )
    if owner["identity"] != "authenticated_user.email":
        raise ValueError("Ownership must use authenticated_user.email")
    source = owner["source"]
    if not isinstance(source, dict) or set(source) != {"schema", "relation"}:
        raise ValueError("Ownership source requires schema and relation")
    relation = f"{identifier(source['schema'])}.{identifier(source['relation'])}"
    identifier(owner["json_key"])
    column = f"o.{identifier(owner['column'])}"
    key = owner["json_key"]
    return (
        f"EXISTS (SELECT 1 FROM {relation} AS o WHERE "
        f"o.{identifier(owner['match_column'])} = s.{identifier(owner['source_column'])} "
        f"AND jsonb_typeof({column} -> '{key}') = 'string' "
        f"AND lower(btrim({column} ->> '{key}')) = $1)"
    )
