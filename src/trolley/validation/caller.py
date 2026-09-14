"""Compile a restricted caller-owned relation query; never wrap arbitrary SQL."""

import re
from copy import deepcopy

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_CALLER = "trolley_caller_email"
_OPERATORS = {"eq": "=", "gte": ">=", "gt": ">", "lte": "<=", "lt": "<"}


def identifier(value):
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ValueError("Caller query identifiers must be simple SQL identifiers")
    return '"' + value + '"'


def compile_definition(definition: dict, input_schema: dict) -> dict:
    scope = definition.get("data_scope")
    if scope not in ("caller", "shared"):
        raise ValueError("data_scope must explicitly be 'caller' or 'shared'")
    if scope == "shared":
        if "ownership" in definition or "source" in definition or "filters" in definition:
            raise ValueError("Ownership/source/filters require caller data_scope")
        if definition.get("bindings"):
            raise ValueError("Personal data requires caller data_scope, not SQL bindings")
        return deepcopy(definition)
    allowed = {"data_scope", "source", "ownership", "columns", "filters", "output", "pagination"}
    if set(definition) - allowed:
        raise ValueError(
            "Caller Operations accept only structured source/columns/filters; no SQL or bindings"
        )
    source = definition.get("source")
    if not isinstance(source, dict) or set(source) != {"schema", "relation"}:
        raise ValueError("Caller source requires schema and relation")
    relation = f"{identifier(source['schema'])}.{identifier(source['relation'])}"
    ownership = definition.get("ownership")
    if (
        not isinstance(ownership, dict)
        or set(ownership) != {"column", "identity"}
        or ownership["identity"] != "authenticated_user.email"
    ):
        raise ValueError("Caller ownership requires column and authenticated_user.email identity")
    owner = identifier(ownership["column"])
    columns = definition.get("columns")
    if not isinstance(columns, list) or not columns:
        raise ValueError("Caller columns must be a non-empty list")
    projection = ", ".join(identifier(column) for column in columns)
    if len(set(columns)) != len(columns):
        raise ValueError("Caller columns must be unique")
    properties = input_schema.get("properties", {})
    if _CALLER in properties or ownership["column"] in properties:
        raise ValueError("Owner identity must not be a public input")
    if input_schema.get("additionalProperties") is not False:
        raise ValueError("Caller input_schema requires additionalProperties: false")
    filters = definition.get("filters", [])
    if not isinstance(filters, list):
        raise ValueError("Caller filters must be a list")
    predicates = [f"{owner} = $1"]
    parameters = [_CALLER]
    for item in filters:
        if not isinstance(item, dict) or set(item) != {"column", "operator", "parameter"}:
            raise ValueError("Caller filters require column, operator and parameter")
        column = identifier(item["column"])
        if item["column"] == ownership["column"]:
            raise ValueError("Owner column cannot be filtered by public input")
        operator = item["operator"]
        if not isinstance(operator, str) or operator not in _OPERATORS:
            raise ValueError("Unsupported caller filter operator")
        parameter = item["parameter"]
        if not isinstance(parameter, str) or parameter not in properties or parameter == _CALLER:
            raise ValueError("Filter parameter must be a declared public input")
        if parameter in parameters:
            raise ValueError("Caller filter parameters must be unique")
        parameters.append(parameter)
        predicates.append(f"{column} {_OPERATORS[operator]} ${len(parameters)}")
    if set(parameters[1:]) != set(properties) or set(properties) != set(
        input_schema.get("required", [])
    ):
        raise ValueError("Caller inputs must exactly match required filter parameters")
    return {
        **deepcopy(definition),
        "sql": f"SELECT {projection} FROM {relation} WHERE " + " AND ".join(predicates),
        "parameters": parameters,
        "bindings": {_CALLER: "authenticated_user.email"},
        "fetch": True,
    }
