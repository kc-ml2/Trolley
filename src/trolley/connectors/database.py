from time import perf_counter
from typing import Any

import asyncpg


def database_url(configuration: dict) -> str:
    url = configuration.get("url")
    if not url:
        raise ValueError("A PostgreSQL target needs 'url'")
    return url


async def test_connection(configuration: dict) -> dict[str, Any]:
    started_at = perf_counter()
    connection = await asyncpg.connect(
        database_url(configuration),
        timeout=configuration.get("timeout", 10),
    )
    try:
        await connection.fetchval("SELECT 1")
        server_version = await connection.fetchval("SHOW server_version")
        return {
            "status": "connected",
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            "server_version": server_version,
        }
    finally:
        await connection.close()


async def inspect_schema(configuration: dict) -> list[dict[str, Any]]:
    connection = await asyncpg.connect(
        database_url(configuration),
        timeout=configuration.get("timeout", 30),
    )
    try:
        rows = await connection.fetch(
            """
            SELECT
                c.table_schema,
                c.table_name,
                t.table_type,
                c.column_name,
                c.ordinal_position,
                c.data_type,
                c.udt_name,
                c.is_nullable = 'YES' AS nullable,
                c.column_default,
                COALESCE(k.is_primary_key, false) AS is_primary_key,
                fk.foreign_schema,
                fk.foreign_table,
                fk.foreign_column
            FROM information_schema.columns c
            JOIN information_schema.tables t
              ON t.table_schema = c.table_schema
             AND t.table_name = c.table_name
            LEFT JOIN (
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name,
                    true AS is_primary_key
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_schema = tc.constraint_schema
                 AND kcu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY'
            ) k
              ON k.table_schema = c.table_schema
             AND k.table_name = c.table_name
             AND k.column_name = c.column_name
            LEFT JOIN (
                SELECT
                    tc.table_schema,
                    tc.table_name,
                    kcu.column_name,
                    ccu.table_schema AS foreign_schema,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON kcu.constraint_schema = tc.constraint_schema
                 AND kcu.constraint_name = tc.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON ccu.constraint_schema = tc.constraint_schema
                 AND ccu.constraint_name = tc.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
            ) fk
              ON fk.table_schema = c.table_schema
             AND fk.table_name = c.table_name
             AND fk.column_name = c.column_name
            WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
            """
        )
    finally:
        await connection.close()

    schemas: dict[str, dict[str, Any]] = {}
    tables: dict[tuple[str, str], dict[str, Any]] = {}
    for record in rows:
        row = dict(record)
        schema_name = row["table_schema"]
        table_name = row["table_name"]
        schema = schemas.setdefault(schema_name, {"name": schema_name, "tables": []})
        table = tables.get((schema_name, table_name))
        if table is None:
            table = {
                "name": table_name,
                "type": "view" if row["table_type"] == "VIEW" else "table",
                "columns": [],
                "primary_key": [],
                "foreign_keys": [],
            }
            tables[(schema_name, table_name)] = table
            schema["tables"].append(table)
        column = {
            "name": row["column_name"],
            "type": row["data_type"],
            "database_type": row["udt_name"],
            "nullable": row["nullable"],
            "default": row["column_default"],
        }
        table["columns"].append(column)
        if row["is_primary_key"]:
            table["primary_key"].append(row["column_name"])
        if row["foreign_table"]:
            table["foreign_keys"].append(
                {
                    "column": row["column_name"],
                    "references": (
                        f"{row['foreign_schema']}.{row['foreign_table']}.{row['foreign_column']}"
                    ),
                }
            )
    return list(schemas.values())


async def execute(
    configuration: dict,
    definition: dict,
    arguments: dict,
) -> Any:
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

    connection = await asyncpg.connect(
        database_url(configuration), timeout=configuration.get("timeout", 30)
    )
    try:
        if definition.get("fetch", True):
            rows = await connection.fetch(sql, *values)
            return {"rows": [dict(row) for row in rows]}
        status = await connection.execute(sql, *values)
        return {"status": status}
    finally:
        await connection.close()
