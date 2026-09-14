from copy import deepcopy

import pytest

from trolley.validation.caller import compile_definition
from trolley.validation.operations import validate_definition

SCHEMA = {
    "type": "object",
    "properties": {"start": {"type": "string"}},
    "required": ["start"],
    "additionalProperties": False,
}
DEFINITION = {
    "data_scope": "caller",
    "source": {"schema": "public", "relation": "usage"},
    "ownership": {"column": "owner_email", "identity": "authenticated_user.email"},
    "columns": ["id", "created_at"],
    "filters": [{"column": "created_at", "operator": "gte", "parameter": "start"}],
    "output": "file",
}


def test_compiles_only_owned_relation_and_bound_filters():
    validate_definition(None, DEFINITION, SCHEMA)
    compiled = compile_definition(DEFINITION, SCHEMA)
    assert compiled["sql"] == (
        'SELECT "id", "created_at" FROM "public"."usage" '
        'WHERE "owner_email" = $1 AND "created_at" >= $2'
    )
    assert compiled["parameters"] == ["trolley_caller_email", "start"]
    assert compiled["bindings"] == {"trolley_caller_email": "authenticated_user.email"}
    assert "sql" not in DEFINITION


@pytest.mark.parametrize(
    "change",
    [
        {"data_scope": None},
        {"sql": "select * from secrets"},
        {"source": {"schema": "public", "relation": "usage JOIN secrets ON true"}},
        {"columns": ["(SELECT secret FROM secrets)"]},
        {"ownership": {"column": "email", "identity": "client.email"}},
        {"filters": [{"column": "owner_email", "operator": "eq", "parameter": "start"}]},
        {"filters": [{"column": "created_at", "operator": "OR true --", "parameter": "start"}]},
        {"bindings": {}},
        {"parameters": ["email"]},
    ],
)
def test_rejects_unrestricted_caller_queries(change):
    with pytest.raises(ValueError):
        validate_definition(None, {**DEFINITION, **change}, SCHEMA)


def test_scope_and_closed_schema_are_required():
    with pytest.raises(ValueError, match="data_scope"):
        validate_definition(None, {"sql": "select 1"}, {"type": "object"})
    schema = deepcopy(SCHEMA)
    schema["properties"]["owner_email"] = {"type": "string"}
    with pytest.raises(ValueError, match="public input"):
        validate_definition(None, DEFINITION, schema)
    with pytest.raises(ValueError, match="additionalProperties"):
        validate_definition(None, DEFINITION, {**SCHEMA, "additionalProperties": True})
