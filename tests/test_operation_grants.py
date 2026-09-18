"""The removed per-operation permission contract must not reappear."""

import inspect

from trolley.application.operations import create_operation, update_operation
from trolley.persistence.models import Operation, User


def test_no_per_operation_policy():
    assert "access" not in inspect.signature(create_operation).parameters
    assert "access" not in inspect.signature(update_operation).parameters
    assert "access" not in Operation._meta.fields
    assert "operation_access" not in User._meta.fields
