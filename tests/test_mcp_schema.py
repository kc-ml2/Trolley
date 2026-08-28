import inspect

from trolley.mcp.schema import create_tool_signature, remove_missing_arguments


def test_dynamic_tool_signature_maps_schema_types_and_missing_values() -> None:
    signature = create_tool_signature(
        {
            "type": "object",
            "properties": {
                "month": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["month"],
        }
    )

    assert signature.parameters["month"].annotation is str
    assert signature.parameters["month"].default is inspect.Parameter.empty
    assert signature.parameters["limit"].annotation is int

    optional_default = signature.parameters["limit"].default
    assert remove_missing_arguments({"month": "2025-08", "limit": optional_default}) == {
        "month": "2025-08"
    }
