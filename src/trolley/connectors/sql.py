"""Prepare a single PostgreSQL query for a subquery wrapper.

This is lexical handling of delimiters, not SQL authorization or semantic validation.
PostgreSQL still parses the query and enforces the read-only transaction.
"""

import re

_DOLLAR_QUOTE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")


def pagination_query(sql: str) -> str:
    i = 0
    terminator = None
    while i < len(sql):
        if sql[i].isspace():
            i += 1
            continue
        if sql.startswith("--", i):
            end = sql.find("\n", i + 2)
            i = len(sql) if end < 0 else end + 1
            continue
        if sql.startswith("/*", i):
            depth = 1
            i += 2
            while i < len(sql) and depth:
                if sql.startswith("/*", i):
                    depth += 1
                    i += 2
                elif sql.startswith("*/", i):
                    depth -= 1
                    i += 2
                else:
                    i += 1
            if depth:
                raise ValueError("Unterminated SQL comment")
            continue
        if terminator is not None:
            raise ValueError("Pagination requires one SQL statement")
        if sql[i] == ";":
            terminator = i
            i += 1
            continue
        if sql[i] in ("'", '"'):
            quote = sql[i]
            escaped = (
                quote == "'"
                and i > 0
                and sql[i - 1] in "eE"
                and (i < 2 or not (sql[i - 2].isalnum() or sql[i - 2] == "_"))
            )
            i += 1
            while i < len(sql):
                if escaped and sql[i] == "\\":
                    i += 2
                elif sql[i] == quote:
                    i += 1
                    if i < len(sql) and sql[i] == quote:
                        i += 1
                    else:
                        break
                else:
                    i += 1
            else:
                raise ValueError("Unterminated SQL quote")
            continue
        dollar = _DOLLAR_QUOTE.match(sql, i)
        if dollar:
            end = sql.find(dollar[0], dollar.end())
            if end < 0:
                raise ValueError("Unterminated SQL dollar quote")
            i = end + len(dollar[0])
            continue
        i += 1
    if terminator is not None:
        sql = sql[:terminator] + " " + sql[terminator + 1 :]
    return sql.strip()
