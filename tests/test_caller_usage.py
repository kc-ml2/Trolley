import asyncio
import os
from copy import deepcopy
from uuid import uuid4

import asyncpg
import pytest

from trolley.validation.caller import compile_definition

DEFINITION = {
    "data_scope": "caller",
    "source": {"schema": "public", "relation": "logs"},
    "ownership": {
        "source": {"schema": "public", "relation": "keys"},
        "source_column": "api_key",
        "match_column": "token",
        "column": "metadata",
        "json_key": "owner_email",
        "identity": "authenticated_user.email",
    },
    "dimensions": [{"column": "day", "transform": "date", "as": "usage_date"}],
    "metrics": [
        {"function": "count", "as": "requests"},
        {"function": "sum", "column": "cost", "as": "cost"},
    ],
    "filters": [{"dimension": "usage_date", "operator": "gte", "parameter": "start"}],
}
SCHEMA = {
    "type": "object",
    "properties": {"start": {"type": "string", "format": "date"}},
    "required": ["start"],
    "additionalProperties": False,
}


def test_mapped_aggregate_compiles():
    result = compile_definition(DEFINITION, SCHEMA)
    assert "EXISTS (SELECT 1" in result["sql"]
    assert "lower(btrim(o.\"metadata\" ->> 'owner_email')) = $1" in result["sql"]
    assert result["sql"].index("WHERE") < result["sql"].index("GROUP BY")
    assert result["parameters"] == ["trolley_caller_email", "start"]
    assert result["bindings"] == {"trolley_caller_email": "authenticated_user.email"}
    assert "sql" not in DEFINITION


@pytest.mark.parametrize(
    "patch",
    [
        {"sql": "SELECT 1"},
        {"bindings": {}},
        {"columns": ["token"]},
        {"metrics": [{"function": "arbitrary", "as": "x"}]},
        {"dimensions": [{"column": "day", "transform": "date); SELECT 1", "as": "x"}]},
        {"metrics": [{"function": "count", "as": "usage_date"}]},
        {"filters": [{"dimension": "owner_email", "operator": "eq", "parameter": "start"}]},
    ],
)
def test_reject_unsafe_definitions(patch):
    with pytest.raises(ValueError):
        compile_definition({**DEFINITION, **patch}, SCHEMA)


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity", "client.email"),
        ("json_key", "x' OR true --"),
        ("match_column", "token OR true"),
        ("source_column", "api_key;DELETE"),
    ],
)
def test_reject_ownership_injection(field, value):
    definition = deepcopy(DEFINITION)
    definition["ownership"][field] = value
    with pytest.raises(ValueError):
        compile_definition(definition, SCHEMA)


def test_cannot_expose_caller_parameter():
    schema = deepcopy(SCHEMA)
    schema["properties"]["trolley_caller_email"] = {"type": "string"}
    with pytest.raises(ValueError):
        compile_definition(DEFINITION, schema)


@pytest.mark.skipif(not os.getenv("TROLLEY_TEST_POSTGRES_URL"), reason="Disposable PostgreSQL only")
def test_actual_owner_isolation_and_duplicate_mapping():
    async def scenario():
        connection = await asyncpg.connect(os.environ["TROLLEY_TEST_POSTGRES_URL"])
        schema = "usage_test_" + uuid4().hex
        try:
            await connection.execute(f'CREATE SCHEMA "{schema}"')
            await connection.execute(f'''CREATE TABLE "{schema}".keys(token text, metadata jsonb);
                CREATE TABLE "{schema}".logs(api_key text, day date, cost integer);
                INSERT INTO "{schema}".keys VALUES
                ('a', '{{"owner_email":" Alice@Example.com "}}'),
                ('a', '{{"owner_email":"alice@example.com"}}'),
                ('b', '{{"owner_email":"bob@example.com"}}'),
                ('c', '{{"owner_email":["alice@example.com"]}}');
                INSERT INTO "{schema}".logs VALUES
                ('a', '2026-09-01', 3), ('a', '2026-09-02', 4),
                ('b', '2026-09-02', 999), ('c', '2026-09-02', 888);''')
            definition = deepcopy(DEFINITION)
            definition["source"]["schema"] = schema
            definition["ownership"]["source"]["schema"] = schema
            sql = compile_definition(definition, SCHEMA)["sql"]
            rows = await connection.fetch(sql, "alice@example.com", "2026-09-02")
            assert len(rows) == 1
            assert rows[0]["requests"] == 1 and rows[0]["cost"] == 4
            assert not await connection.fetch(sql, "unknown@example.com", "2026-09-01")
        finally:
            await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await connection.close()

    asyncio.run(scenario())
