import pytest

from trolley.validation.arguments import validate_arguments

SCHEMA = {
    "type": "object",
    "properties": {"day": {"type": "string", "format": "date"}},
    "required": ["day"],
    "additionalProperties": False,
}


@pytest.mark.parametrize("day", ["2026-09-01", "2024-02-29"])
def test_valid_dates(day):
    validate_arguments({"day": day}, SCHEMA)


@pytest.mark.parametrize(
    "arguments",
    [
        {"day": "2026-02-29"},
        {"day": "2026-09-01T00:00:00Z"},
        {"day": "secret-invalid-value"},
        {},
        {"day": "2026-09-01", "email": "private"},
    ],
)
def test_invalid_arguments_are_safe_errors(arguments):
    with pytest.raises(ValueError, match="input schema") as caught:
        validate_arguments(arguments, SCHEMA)
    assert "secret-invalid-value" not in str(caught.value)
    assert "private" not in str(caught.value)
