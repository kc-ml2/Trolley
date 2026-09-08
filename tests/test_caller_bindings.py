from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from trolley.application.execution import execute_operation
from trolley.application.operations import create_operation, update_operation
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.domain.users import UserRole
from trolley.main import create_app
from trolley.persistence.models import Execution, User
from trolley.validation.operations import validate_definition


def test_caller_email_binding(tmp_path, monkeypatch):
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
        targets={"db": {"kind": "postgresql", "url": "postgresql://unused/test"}},
    )
    connector = AsyncMock(return_value={"rows": [{"id": 1}], "has_more": True})
    monkeypatch.setattr("trolley.application.execution.database.execute", connector)
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario():
            definition = {
                "sql": "select id from logs where email = $1",
                "parameters": ["caller_email"],
                "bindings": {"caller_email": "authenticated_user.email"},
                "pagination": {"order_by": ["id"]},
            }
            # Even permissive client schemas cannot override server bindings.
            await create_operation("my_usage", "db", definition, input_schema={"type": "object"})
            user = await User.create(email="member@example.com", name="Member")
            root = await User.get(email="root@example.com")
            for caller in (user, root):
                context = AuthContext(
                    user_id=str(caller.id), api_key_id=str(uuid4()), role=caller.role
                )
                result = await execute_operation("my_usage", {}, context, page_size=1)
                assert connector.call_args.args[2] == {"caller_email": caller.email}
                audit = await Execution.get(id=result["execution_id"])
                assert audit.arguments == {"caller_email": caller.email}
                before = connector.await_count
                with pytest.raises(ValueError, match="cannot be supplied"):
                    await execute_operation(
                        "my_usage", {"caller_email": "other@example.com"}, context
                    )
                assert connector.await_count == before

            context = AuthContext(user_id=str(user.id), api_key_id=str(uuid4()), role=UserRole.USER)
            first = await execute_operation("my_usage", {}, context)
            cursor = first["result"]["next_cursor"]
            await execute_operation("my_usage", {}, context, cursor=cursor)
            user.email = "changed@example.com"
            await user.save()
            with pytest.raises(ValueError, match="conditions changed"):
                await execute_operation("my_usage", {}, context, cursor=cursor)
            await execute_operation("my_usage", {}, context)
            assert connector.call_args.args[2] == {"caller_email": user.email}

            server = app.routes[-1].app.state.mcp_server
            await server.registry.reload("my_usage")
            tools = {tool.name: tool for tool in await server.list_tools()}
            assert "caller_email" not in tools["my_usage"].input_schema.get("properties", {})
            monkeypatch.setattr("trolley.mcp.pipeline.current_tool_context", lambda: context)
            tool = server._tool_manager.get_tool("my_usage")
            await tool.fn()
            assert connector.call_args.args[2] == {"caller_email": user.email}
            with pytest.raises(ValueError, match="input_schema"):
                await update_operation(
                    "my_usage",
                    input_schema={
                        "type": "object",
                        "properties": {"caller_email": {"type": "string"}},
                    },
                )

        client.portal.call(scenario)


@pytest.mark.parametrize(
    "bindings", [None, [], {"email": "client.email"}, {"bad-name": "authenticated_user.email"}]
)
def test_invalid_binding_sources(bindings):
    with pytest.raises(ValueError, match="bindings"):
        validate_definition(
            None,
            {"sql": "select $1", "parameters": ["email"], "bindings": bindings},
            {"type": "object"},
        )


def test_binding_must_be_in_parameters_and_not_public_schema():
    definition = {
        "sql": "select $1",
        "parameters": ["email"],
        "bindings": {"email": "authenticated_user.email"},
    }
    with pytest.raises(ValueError, match="input_schema"):
        validate_definition(None, definition, {"type": "object", "required": ["email"]})
    with pytest.raises(ValueError, match="parameters"):
        validate_definition(None, {**definition, "parameters": []}, {"type": "object"})
