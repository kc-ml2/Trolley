import pytest

from trolley.connectors.sql import pagination_query


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT id FROM logs -- comment", "SELECT id FROM logs -- comment"),
        ("SELECT 1; -- comment", "SELECT 1  -- comment"),
        (
            "SELECT 1; /* outer /* nested */ comment */",
            "SELECT 1  /* outer /* nested */ comment */",
        ),
        ("SELECT ';' AS value;", "SELECT ';' AS value"),
        ('SELECT 1 AS "semi;colon";', 'SELECT 1 AS "semi;colon"'),
        ("SELECT $$semi;--colon$$;", "SELECT $$semi;--colon$$"),
        ("SELECT $tag$semi;/*colon*/$tag$;", "SELECT $tag$semi;/*colon*/$tag$"),
        (r"SELECT E'it\'s;ok';", r"SELECT E'it\'s;ok'"),
        ("SELECT 'it''s;ok';", "SELECT 'it''s;ok'"),
    ],
)
def test_terminal_semicolon_and_comments(sql, expected):
    assert pagination_query(sql) == expected


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT 1; SELECT 2",
        "SELECT 1; /* ok */ SELECT 2",
        "SELECT 'bad",
        "SELECT /* bad",
        "SELECT $tag$bad",
    ],
)
def test_rejects_multiple_statements_and_incomplete_sql(sql):
    with pytest.raises(ValueError):
        pagination_query(sql)
