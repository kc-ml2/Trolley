from fastapi.testclient import TestClient

from trolley.application.operations import create_operation, disable_operation
from trolley.config import Settings
from trolley.main import create_app
from trolley.persistence.models import Target


def test_dynamic_tool_live_reload(tmp_path) -> None:
    settings = Settings(
        database_url=f"sqlite://{tmp_path}/test.db",
        admin_emails=frozenset({"root@example.com"}),
    )
    app = create_app(settings)
    with TestClient(app) as client:

        async def scenario() -> None:
            server = app.routes[-1].app.state.mcp_server
            registry = server.registry
            await Target.create(name="payments", kind="postgresql")
            await create_operation(
                "monthly_revenue",
                "payments",
                {"sql": "select $1::text as month", "parameters": ["month"]},
                input_schema={
                    "type": "object",
                    "properties": {"month": {"type": "string"}},
                    "required": ["month"],
                    "additionalProperties": False,
                },
            )
            await registry.reload("monthly_revenue")
            tools = {tool.name: tool for tool in await server.list_tools()}
            assert tools["monthly_revenue"].input_schema["required"] == ["month"]
            internal = server._tool_manager.get_tool("monthly_revenue")
            assert internal.fn_metadata.validate_arguments({"month": "2025-08"}) == {
                "month": "2025-08"
            }

            await disable_operation("monthly_revenue")
            await registry.reload("monthly_revenue")
            assert "monthly_revenue" not in {tool.name for tool in await server.list_tools()}

        client.portal.call(scenario)
