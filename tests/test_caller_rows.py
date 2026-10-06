import asyncio
import gzip
import json
import os
from copy import deepcopy
from uuid import uuid4

import asyncpg
import pytest
from test_caller_usage import DEFINITION

from trolley.config import ExportSettings
from trolley.connectors.database import execute
from trolley.connectors.export import export_jsonl
from trolley.validation.caller import compile_definition

ROWS = {
    "data_scope": "caller",
    "source": DEFINITION["source"],
    "ownership": DEFINITION["ownership"],
    "columns": ["id", "messages", "response"],
    "filters": [
        {"column": "at", "operator": "gte", "parameter": "start", "type": "timestamp"},
        {"column": "at", "operator": "lt", "parameter": "end", "type": "timestamp"},
    ],
    "output": "file",
}
SCHEMA = {
    "type": "object",
    "properties": {p: {"type": "string"} for p in ("start", "end")},
    "required": ["start", "end"],
    "additionalProperties": False,
}


def test_raw_mapping_same_for_inline_and_file():
    compiled = compile_definition(ROWS, SCHEMA)
    assert compiled["sql"] == compile_definition({**ROWS, "output": "inline"}, SCHEMA)["sql"]
    assert "EXISTS" in compiled["sql"]
    assert "$2::text::timestamp" in compiled["sql"]
    assert compiled["bindings"] == {"trolley_caller_email": "authenticated_user.email"}
    for field, value in [("identity", "client.email"), ("json_key", "x' OR true --")]:
        bad = deepcopy(ROWS)
        bad["ownership"][field] = value
        with pytest.raises(ValueError):
            compile_definition(bad, SCHEMA)
    bad = deepcopy(ROWS)
    bad["filters"][0]["type"] = "timestamp); DELETE"
    with pytest.raises(ValueError):
        compile_definition(bad, SCHEMA)


@pytest.mark.skipif(not os.getenv("TROLLEY_TEST_POSTGRES_URL"), reason="Disposable PostgreSQL only")
def test_raw_inline_and_gzip_owner_isolation(tmp_path):
    async def scenario():
        url = os.environ["TROLLEY_TEST_POSTGRES_URL"]
        connection = await asyncpg.connect(url)
        schema = "rows_test_" + uuid4().hex
        try:
            await connection.execute(f'CREATE SCHEMA "{schema}"')
            await connection.execute(f'''CREATE TABLE "{schema}".keys(token text, metadata jsonb);
                CREATE TABLE "{schema}".logs(id integer, api_key text, at timestamp,
                    messages jsonb, response jsonb);
                INSERT INTO "{schema}".keys VALUES
                ('a', '{{"owner_email":" Alice@Example.com "}}'),
                ('a', '{{"owner_email":"alice@example.com"}}'),
                ('b', '{{"owner_email":"bob@example.com"}}'),
                ('c', '{{"owner_email":["alice@example.com"]}}'), ('d', '{{}}');''')
            for i, key in enumerate(["a", "b", "c", "d", "missing"], 1):
                await connection.execute(
                    f'''INSERT INTO "{schema}".logs VALUES
                    ($1, $2, '2026-09-01', $3::jsonb, $4::jsonb)''',
                    i,
                    key,
                    json.dumps([{"role": "user", "content": [{"type": "text", "text": "hello"}]}]),
                    json.dumps({"answer": "world"}),
                )
            definition = deepcopy(ROWS)
            definition["source"]["schema"] = schema
            definition["ownership"]["source"]["schema"] = schema
            compiled = compile_definition(definition, SCHEMA)
            args = {
                "trolley_caller_email": "alice@example.com",
                "start": "2026-09-01",
                "end": "2026-09-02",
            }
            result = await execute({"url": url}, compiled, args, readonly=True)
            assert [r["id"] for r in result["rows"]] == [1]
            path = tmp_path / "rows.gz"
            await export_jsonl({"url": url}, compiled, args, path, ExportSettings())
            rows = [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]
            assert rows == result["rows"]
            # asyncpg's existing JSONB contract is a JSON-encoded string, not a dict.
            assert json.loads(rows[0]["messages"])[0]["content"][0]["text"] == "hello"
            assert json.loads(rows[0]["response"]) == {"answer": "world"}
            args["trolley_caller_email"] = "bob@example.com"
            assert [
                r["id"]
                for r in (await execute({"url": url}, compiled, args, readonly=True))["rows"]
            ] == [2]
        finally:
            await connection.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
            await connection.close()

    asyncio.run(scenario())
