import os
from time import perf_counter
from typing import Any

import asyncpg


def resolve_database_url(secret_env: str | None) -> str:
    if not secret_env:
        raise ValueError("A database target needs secret_env with its PostgreSQL URL")
    database_url = os.getenv(secret_env)
    if not database_url:
        raise ValueError(f"Credential environment variable is not set: {secret_env}")
    return database_url


async def test_connection(configuration: dict, secret_env: str | None) -> dict[str, Any]:
    started_at = perf_counter()
    connection = await asyncpg.connect(
        resolve_database_url(secret_env),
        timeout=configuration.get("timeout", 10),
    )
    try:
        await connection.fetchval("SELECT 1")
        return {
            "status": "connected",
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            "server_version": connection.get_server_version().to_string(),
        }
    finally:
        await connection.close()


async def execute(
    configuration: dict,
    definition: dict,
    arguments: dict,
    secret_env: str | None,
) -> Any:
    database_url = resolve_database_url(secret_env)

    sql = definition.get("sql")
    if not sql:
        raise ValueError("A database operation needs 'sql'")

    parameter_names = definition.get("parameters", [])
    unknown = set(arguments) - set(parameter_names)
    missing = set(parameter_names) - set(arguments)
    if unknown or missing:
        details = f"missing={sorted(missing)}, unknown={sorted(unknown)}"
        raise ValueError(f"Arguments do not match parameters; {details}")
    values = [arguments[name] for name in parameter_names]

    connection = await asyncpg.connect(database_url, timeout=configuration.get("timeout", 30))
    try:
        if definition.get("fetch", True):
            rows = await connection.fetch(sql, *values)
            return {"rows": [dict(row) for row in rows]}
        status = await connection.execute(sql, *values)
        return {"status": status}
    finally:
        await connection.close()
