"""Validate JSON inputs consistently without echoing potentially sensitive values."""

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


def validate_arguments(arguments: dict, schema: dict) -> None:
    try:
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(arguments)
    except ValidationError:
        # jsonschema's default message includes the rejected value and schema.
        raise ValueError("Arguments do not match the Operation input schema") from None
