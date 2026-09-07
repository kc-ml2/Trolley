import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from trolley.connectors.database import execute


def test_byte_limited_pages_advance_by_returned_rows(monkeypatch):
    connection = MagicMock()
    connection.transaction.return_value = AsyncMock()
    connection.close = AsyncMock()
    rows = [{"id": i, "payload": "x" * 120} for i in range(1, 5)]

    async def records(limit, offset):
        for row in rows[offset : offset + limit]:
            yield row

    connection.cursor.side_effect = lambda sql, limit, offset, **kwargs: records(limit, offset)
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr("trolley.connectors.database.asyncpg.connect", connect)
    config = {"url": "postgresql://unused/test", "max_result_bytes": 500}
    definition = {
        "sql": "SELECT id, payload FROM logs -- trailing",
        "pagination": {"order_by": ["id"]},
    }

    async def scenario():
        offset = 0
        found = []
        while True:
            page = await execute(config, definition, {}, page_size=4, offset=offset)
            assert len(page["rows"]) == 1
            found.extend(row["id"] for row in page["rows"])
            offset += len(page["rows"])
            if not page["has_more"]:
                break
        assert found == [1, 2, 3, 4]
        sql = connection.cursor.call_args.args[0]
        assert "-- trailing\n) AS trolley_page" in sql
        with pytest.raises(ValueError, match="byte limit"):
            await execute({**config, "max_result_bytes": 280}, definition, {}, page_size=4)
        empty = await execute(config, definition, {}, page_size=4, offset=4)
        assert empty == {"rows": [], "has_more": False, "next_cursor": None}
        assert connection.close.await_count == 6

        count = connect.await_count
        with pytest.raises(ValueError, match="query_timeout"):
            await execute({**config, "query_timeout": float("inf")}, definition, {}, page_size=4)
        assert connect.await_count == count

    asyncio.run(scenario())
