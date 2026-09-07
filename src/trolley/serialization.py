"""Stable, lossless JSON representation for PostgreSQL result values."""

import base64
import math
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from ipaddress import (
    IPv4Address,
    IPv4Interface,
    IPv4Network,
    IPv6Address,
    IPv6Interface,
    IPv6Network,
)
from uuid import UUID


def json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)  # Never round monetary values through a float.
    if isinstance(
        value,
        (UUID, IPv4Address, IPv6Address, IPv4Interface, IPv6Interface, IPv4Network, IPv6Network),
    ):
        return str(value)
    if isinstance(value, timedelta):
        return {"days": value.days, "seconds": value.seconds, "microseconds": value.microseconds}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    raise ValueError(f"Unsupported result type: {type(value).__name__}")
