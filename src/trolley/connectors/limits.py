"""Validate operator-controlled limits without lossy numeric coercion."""

import math


def execution_limits(configuration: dict) -> dict:
    limits = {}
    for field, default in (("timeout", 30), ("query_timeout", 30)):
        value = configuration.get(field, default)
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError(f"{field} must be a finite positive number")
        try:
            value = float(value)
        except (ValueError, OverflowError) as error:
            raise ValueError(f"{field} must be a finite positive number") from error
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{field} must be a finite positive number")
        limits[field] = value
    for field, default in (("max_rows", 1000), ("max_result_bytes", 1_000_000)):
        value = configuration.get(field, default)
        if isinstance(value, str) and value.isascii() and value.isdecimal():
            try:
                value = int(value)
            except ValueError as error:
                raise ValueError(f"{field} must be a positive integer") from error
        # Leave room for the PostgreSQL LIMIT lookahead (page_size + 1).
        if type(value) is not int or not 1 <= value < 2**63 - 1:
            raise ValueError(f"{field} must be a positive integer below 2**63 - 1")
        limits[field] = value
    return limits
