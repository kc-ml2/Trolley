from typing import Any

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from trolley.application.execution import execute_operation
from trolley.mcp.enums import SystemToolName
from trolley.mcp.schema import create_tool_signature, remove_missing_arguments
from trolley.persistence.models import Operation


class DynamicToolRegistry:
    def __init__(self, server: MCPServer) -> None:
        self.server = server
        self.names: set[str] = set()

    async def load(self) -> int:
        operations = await Operation.filter(is_active=True, target__is_active=True).order_by("name")
        conflicts = [operation.name for operation in operations if operation.name in SystemToolName]
        if conflicts:
            raise ValueError(f"Operations conflict with system tools: {', '.join(conflicts)}")
        active_names = {operation.name for operation in operations}
        for name in self.names - active_names:
            self.server.remove_tool(name)
        self.names &= active_names
        for operation in operations:
            self.register(operation)
        return len(self.names)

    async def reload(self, name: str) -> None:
        operation = await Operation.get(name=name).prefetch_related("target")
        if name in self.names:
            self.server.remove_tool(name)
            self.names.remove(name)
        if operation.is_active and operation.target.is_active:
            self.register(operation)

    def register(self, operation: Operation) -> None:
        if operation.name in SystemToolName:
            raise ValueError(f"Operation name is reserved by a system tool: {operation.name}")
        if operation.name in self.names:
            return

        async def invoke(**arguments: Any) -> dict:
            from trolley.mcp.pipeline import current_tool_context

            context = current_tool_context()
            try:
                return await execute_operation(
                    operation.name,
                    remove_missing_arguments(arguments),
                    context,
                )
            except (PermissionError, ValueError) as error:
                raise ToolError(str(error)) from error

        invoke.__name__ = operation.name
        invoke.__signature__ = create_tool_signature(operation.input_schema)
        self.server.add_tool(
            invoke,
            name=operation.name,
            description=operation.description,
            meta={"dynamic": True, "access": str(operation.access)},
        )
        registered = self.server._tool_manager.get_tool(operation.name)
        if registered is None:
            raise RuntimeError(f"Dynamic tool was not registered: {operation.name}")
        registered.parameters = operation.input_schema
        self.names.add(operation.name)
