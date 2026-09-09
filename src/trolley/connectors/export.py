"""Stream one read-only PostgreSQL snapshot to a bounded gzip JSONL file."""

import asyncio
import gzip
import json
import os
from pathlib import Path

import asyncpg

from trolley.connectors.database import database_url
from trolley.connectors.sql import pagination_query
from trolley.serialization import json_value


async def export_jsonl(configuration, definition, arguments, path: Path, limits):
    sql = f"SELECT * FROM (\n{pagination_query(definition['sql'])}\n) AS trolley_export"
    values = [arguments[name] for name in definition.get("parameters", [])]
    rows = size = 0
    connection = None
    try:
        async with asyncio.timeout(limits.timeout_seconds):
            connection = await asyncpg.connect(
                database_url(configuration), timeout=configuration.get("timeout", 30)
            )
            async with connection.transaction(isolation="repeatable_read", readonly=True):
                # Exclusive creation; partial files are never available for download.
                with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb") as output:
                    os.fchmod(raw.fileno(), 0o600)
                    async for record in connection.cursor(sql, *values, prefetch=1):
                        data = (
                            json.dumps(json_value(dict(record)), ensure_ascii=False) + "\n"
                        ).encode()
                        rows += 1
                        size += len(data)
                        if rows > limits.max_rows or size > limits.max_bytes:
                            raise ValueError("Export limit exceeded")
                        output.write(data)
                        await asyncio.sleep(0)
                        if raw.tell() > limits.max_bytes:
                            raise ValueError("Compressed export limit exceeded")
                if (await asyncio.to_thread(path.stat)).st_size > limits.max_bytes:
                    raise ValueError("Compressed export limit exceeded")
        return rows, size, (await asyncio.to_thread(path.stat)).st_size
    finally:
        if connection is not None:
            try:
                await connection.close(timeout=5)
            except BaseException:
                connection.terminate()
                raise
