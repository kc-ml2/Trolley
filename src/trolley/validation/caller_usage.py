"""Caller aggregates over a source, authorized through a correlated EXISTS."""

from copy import deepcopy

from trolley.validation.caller import _CALLER, _OPERATORS, identifier


def compile_usage(definition: dict, input_schema: dict) -> dict:
    allowed = {
        "data_scope",
        "source",
        "ownership",
        "dimensions",
        "metrics",
        "filters",
        "output",
        "pagination",
    }
    if set(definition) - allowed:
        raise ValueError("Caller aggregates accept only structured fields; no SQL or bindings")
    source = definition.get("source")
    owner = definition.get("ownership")
    if not isinstance(source, dict) or set(source) != {"schema", "relation"}:
        raise ValueError("Source requires schema and relation")
    if not isinstance(owner, dict) or set(owner) != {
        "source",
        "source_column",
        "match_column",
        "column",
        "json_key",
        "identity",
    }:
        raise ValueError(
            "Mapped ownership requires source, source_column, match_column, "
            "column, json_key and identity"
        )
    if owner["identity"] != "authenticated_user.email":
        raise ValueError("Ownership must use authenticated_user.email")
    mapping = owner["source"]
    if not isinstance(mapping, dict) or set(mapping) != {"schema", "relation"}:
        raise ValueError("Ownership source requires schema and relation")
    relation = f"{identifier(source['schema'])}.{identifier(source['relation'])}"
    owner_relation = f"{identifier(mapping['schema'])}.{identifier(mapping['relation'])}"
    # JSON keys are deliberately restricted to identifiers, never arbitrary SQL.
    identifier(owner["json_key"])
    owner_column = f"o.{identifier(owner['column'])} -> '{owner['json_key']}'"
    owner_text = f"o.{identifier(owner['column'])} ->> '{owner['json_key']}'"
    predicate = (
        f"EXISTS (SELECT 1 FROM {owner_relation} AS o WHERE "
        f"o.{identifier(owner['match_column'])} = s.{identifier(owner['source_column'])} "
        f"AND jsonb_typeof({owner_column}) = 'string' "
        f"AND lower(btrim({owner_text})) = $1)"
    )
    dimensions = definition.get("dimensions", [])
    metrics = definition.get("metrics")
    if not isinstance(dimensions, list) or not isinstance(metrics, list) or not metrics:
        raise ValueError("Dimensions must be a list and metrics a non-empty list")
    expressions, projections, aliases = {}, [], set()
    for item in dimensions:
        if not isinstance(item, dict) or set(item) != {"column", "transform", "as"}:
            raise ValueError("Dimension requires column, transform and as")
        alias = identifier(item["as"])
        column = f"s.{identifier(item['column'])}"
        if item["transform"] == "date":
            column = f"{column}::date"
        elif item["transform"] != "identity":
            raise ValueError("Dimension transform must be identity or date")
        if item["as"] in aliases:
            raise ValueError("Output aliases must be unique")
        aliases.add(item["as"])
        expressions[item["as"]] = column
        projections.append(f"{column} AS {alias}")
    for item in metrics:
        if not isinstance(item, dict) or item.get("function") not in ("count", "sum"):
            raise ValueError("Metric function must be count or sum")
        expected = {"function", "as"} | ({"column"} if item["function"] == "sum" else set())
        if set(item) != expected:
            raise ValueError("Unexpected metric fields")
        alias = identifier(item["as"])
        if item["as"] in aliases:
            raise ValueError("Output aliases must be unique")
        aliases.add(item["as"])
        expr = (
            "COUNT(*)"
            if item["function"] == "count"
            else f"COALESCE(SUM(s.{identifier(item['column'])}), 0)"
        )
        projections.append(f"{expr} AS {alias}")
    properties = input_schema.get("properties", {})
    if input_schema.get("additionalProperties") is not False or _CALLER in properties:
        raise ValueError("Caller inputs must be closed and cannot include caller identity")
    parameters, predicates = [_CALLER], [predicate]
    filters = definition.get("filters", [])
    if not isinstance(filters, list):
        raise ValueError("Filters must be a list")
    for item in filters:
        if not isinstance(item, dict) or set(item) != {"dimension", "operator", "parameter"}:
            raise ValueError("Aggregate filters require dimension, operator and parameter")
        dimension, operator, parameter = item["dimension"], item["operator"], item["parameter"]
        if not all(isinstance(v, str) for v in (dimension, operator, parameter)):
            raise ValueError("Filter fields must be strings")
        if dimension not in expressions or operator not in _OPERATORS:
            raise ValueError("Unknown dimension or operator")
        if parameter not in properties or parameter in parameters:
            raise ValueError("Filter parameter must be a unique public input")
        parameters.append(parameter)
        placeholder = f"${len(parameters)}"
        # JSON date inputs are strings; asyncpg otherwise expects datetime.date.
        if any(d["as"] == dimension and d["transform"] == "date" for d in dimensions):
            placeholder += "::text::date"
        predicates.append(f"{expressions[dimension]} {_OPERATORS[operator]} {placeholder}")
    if set(parameters[1:]) != set(properties) or set(properties) != set(
        input_schema.get("required", [])
    ):
        raise ValueError("Caller inputs must exactly match required filter parameters")
    sql = f"SELECT {', '.join(projections)} FROM {relation} AS s WHERE " + " AND ".join(predicates)
    if expressions:
        sql += " GROUP BY " + ", ".join(expressions.values())
    return {
        **deepcopy(definition),
        "sql": sql,
        "parameters": parameters,
        "bindings": {_CALLER: "authenticated_user.email"},
        "fetch": True,
    }
