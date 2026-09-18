import asyncio
import logging
from datetime import UTC, datetime

from trolley.application.target_access import require_target
from trolley.application.targets import configured_targets
from trolley.auth.context import AuthContext
from trolley.config import Settings
from trolley.connectors import database
from trolley.persistence.models import QueryExecution

# Bound ad-hoc exploration independently of approved Operation execution.
_query_slots = asyncio.Semaphore(4)
logger = logging.getLogger(__name__)


async def query_target(
    settings: Settings,
    context: AuthContext,
    name: str,
    sql: str,
    params: list | None = None,
) -> dict:
    async with _query_slots:
        target = await require_target(context, name)
        definition = configured_targets(settings).get(name)
        if definition is None:
            raise PermissionError("Target unavailable or access denied")
        if not sql.strip():
            raise ValueError("sql must be a non-empty string")
        execution = await QueryExecution.create(
            target=target,
            requested_by=context.user_id,
            api_key_id=context.api_key_id,
            sql=sql,
        )
        values = params or []
        names = [str(i) for i in range(len(values))]
        response = None
        try:
            # asyncpg's prepared cursor accepts one statement; values use $1, $2, ... .
            result = await database.execute(
                definition.configuration,
                {"sql": sql, "parameters": names},
                dict(zip(names, values, strict=True)),
                readonly=True,
            )
            execution.status = "succeeded"
            response = {"execution_id": str(execution.id), **result}
            return response
        except Exception as error:
            execution.status = "failed"
            execution.error = "Query failed"
            # Database diagnostics can contain credentials, SQL literals, or server details.
            raise ValueError(
                f"Query failed ({execution.id}); check SQL, DB privileges and execution limits"
            ) from error
        except asyncio.CancelledError:
            execution.status = "cancelled"
            raise
        finally:
            execution.finished_at = datetime.now(UTC)
            try:
                await asyncio.shield(execution.save())
            except Exception:
                logger.error("Could not finalize query audit record %s", execution.id)
                if response is not None:
                    response["audit_warning"] = (
                        "Query succeeded but audit finalization failed; do not retry the query."
                    )
