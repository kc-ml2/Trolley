from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trolley.application import operation_requests, operations
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.operation_requests import OperationRequestStatus
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Target, User


def test_user_requests_operation_and_admin_resolves_it(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"admin@example.com"}),
    )

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            user = await User.create(email="user@example.com", name="User")
            context = AuthContext(
                user_id=str(user.id),
                api_key_id=str(uuid4()),
                role=UserRole.USER,
            )
            created = await operation_requests.request_operation(
                "Monthly revenue",
                "Return revenue and order count for a month",
                "Prepare the monthly report",
                context,
            )
            assert created["requested_by"] == "user@example.com"
            assert created["status"] == "pending"
            assert created["operation"] is None

            mine = await operation_requests.list_my_operation_requests(context)
            assert [item["id"] for item in mine] == [created["id"]]
            pending = await operation_requests.list_operation_requests(
                OperationRequestStatus.PENDING
            )
            assert [item["id"] for item in pending] == [created["id"]]

            target = await Target.create(name="reports", kind="postgresql")
            target.is_active = True
            await operations.create_operation(
                "monthly_revenue",
                "reports",
                {"sql": "select 1"},
            )
            resolved = await operation_requests.resolve_operation_request(
                created["id"],
                OperationRequestStatus.FULFILLED,
                "Added the requested report.",
                "monthly_revenue",
            )
            assert resolved["status"] == "fulfilled"
            assert resolved["operation"] == "monthly_revenue"
            assert resolved["admin_note"] == "Added the requested report."

            with pytest.raises(ValueError, match="already been resolved"):
                await operation_requests.resolve_operation_request(
                    created["id"], OperationRequestStatus.REJECTED
                )

        client.portal.call(scenario)


def test_fulfilled_request_requires_an_active_operation(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"admin@example.com"}),
    )

    with TestClient(create_app(settings)) as client:

        async def scenario() -> None:
            user = await User.create(email="user@example.com", name="User")
            context = AuthContext(str(user.id), str(uuid4()), UserRole.USER)
            created = await operation_requests.request_operation(
                "Missing report", "Create a missing report", "Needed for work", context
            )
            with pytest.raises(ValueError, match="operation_name is required"):
                await operation_requests.resolve_operation_request(
                    created["id"], OperationRequestStatus.FULFILLED
                )
            with pytest.raises(ValueError, match="only be resolved"):
                await operation_requests.resolve_operation_request(
                    created["id"], OperationRequestStatus.PENDING
                )

        client.portal.call(scenario)
