"""Opt-in tests against a disposable PostgreSQL database, never an operational Target.

Set TROLLEY_TEST_POSTGRES_URL. The role must be able to create schemas/functions.
Only the uniquely named schema created by this test is removed on completion.
"""

import asyncio
import gzip
import json
import os
from uuid import uuid4

import asyncpg
import pytest

from trolley.config import ExportSettings
from trolley.connectors.database import execute
from trolley.connectors.export import export_jsonl


@pytest.mark.skipif(
    not os.getenv("TROLLEY_TEST_POSTGRES_URL"), reason="Disposable PostgreSQL URL not configured"
)
def test_real_postgresql_pagination(tmp_path):
    async def scenario():
        url = os.environ["TROLLEY_TEST_POSTGRES_URL"]
        schema = "trolley_test_" + uuid4().hex
        connection = await asyncpg.connect(url)
        created = False
        try:
            await connection.execute(f'CREATE SCHEMA "{schema}"')
            created = True
            await connection.execute(
                f'CREATE TABLE "{schema}".logs (id integer PRIMARY KEY, payload text)'
            )
            await connection.executemany(
                f'INSERT INTO "{schema}".logs VALUES ($1, $2)',
                [(i, "x" * 120) for i in range(1, 6)],
            )
            config = {"url": url}
            definition = {
                "data_scope": "shared",
                "sql": (
                    f'SELECT id, payload FROM "{schema}".logs WHERE id >= $1; -- trailing comment'
                ),
                "parameters": ["minimum"],
                "pagination": {"order_by": ["id"]},
            }
            first = await execute(config, definition, {"minimum": 2}, page_size=2)
            assert [r["id"] for r in first["rows"]] == [2, 3]
            assert first["has_more"] is True
            last = await execute(config, definition, {"minimum": 2}, page_size=2, offset=2)
            assert [r["id"] for r in last["rows"]] == [4, 5]
            assert last["has_more"] is False
            empty = await execute(config, definition, {"minimum": 99}, page_size=2)
            assert empty == {"rows": [], "has_more": False, "next_cursor": None}

            collected = []
            offset = 0
            while True:
                page = await execute(
                    {**config, "max_result_bytes": 500},
                    definition,
                    {"minimum": 1},
                    page_size=5,
                    offset=offset,
                )
                assert len(page["rows"]) == 1
                collected.extend(r["id"] for r in page["rows"])
                offset += len(page["rows"])
                if not page["has_more"]:
                    break
            assert collected == [1, 2, 3, 4, 5]
            with pytest.raises(ValueError, match="byte limit"):
                await execute(
                    {**config, "max_result_bytes": 280}, definition, {"minimum": 1}, page_size=5
                )

            for sql in [
                "SELECT 1 AS id -- comment",
                "SELECT 1 AS id; /* nested /* comment */ ok */",
                "SELECT 1 AS id, $$a;--b$$ AS value; -- last",
            ]:
                result = await execute(
                    config,
                    {"data_scope": "shared", "sql": sql, "pagination": {"order_by": ["id"]}},
                    {},
                    page_size=1,
                )
                assert result["rows"][0]["id"] == 1

            await connection.execute(f'''CREATE FUNCTION "{schema}".write_row() RETURNS integer
                LANGUAGE plpgsql AS $$ BEGIN
                INSERT INTO "{schema}".logs VALUES (99, 'should roll back');
                RETURN 99; END $$''')
            with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
                await execute(
                    config,
                    {
                        "data_scope": "shared",
                        "sql": f'SELECT "{schema}".write_row() AS id',
                        "pagination": {"order_by": ["id"]},
                    },
                    {},
                    page_size=1,
                )
            assert not await connection.fetchval(
                f'SELECT EXISTS(SELECT 1 FROM "{schema}".logs WHERE id=99)'
            )
            with pytest.raises(ValueError, match="timed out"):
                await execute(
                    {**config, "query_timeout": 0.05},
                    {
                        "data_scope": "shared",
                        "sql": "SELECT pg_sleep(2), 1 AS id",
                        "pagination": {"order_by": ["id"]},
                    },
                    {},
                    page_size=1,
                )
            definition = {
                "data_scope": "shared",
                "sql": f'SELECT id, payload FROM "{schema}".logs WHERE id >= $1 ORDER BY id',
                "parameters": ["minimum"],
            }
            limits = ExportSettings()
            path = tmp_path / "export.gz"
            rows, _, _ = await export_jsonl(config, definition, {"minimum": 2}, path, limits)
            assert rows == 4
            with gzip.open(path, "rt") as stream:
                assert [json.loads(line)["id"] for line in stream] == [2, 3, 4, 5]
            with pytest.raises(ValueError, match="limit"):
                await export_jsonl(
                    config,
                    definition,
                    {"minimum": 1},
                    tmp_path / "limit.gz",
                    ExportSettings(max_rows=1),
                )
            with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
                await export_jsonl(
                    config,
                    {"data_scope": "shared", "sql": f'SELECT "{schema}".write_row()'},
                    {},
                    tmp_path / "write.gz",
                    limits,
                )
        finally:
            if created:
                await connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
            await connection.close()

    asyncio.run(scenario())
