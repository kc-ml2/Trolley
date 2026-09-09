"""Single-process, bounded export jobs. No bodies are stored in the catalog."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from jsonschema import validate

from trolley.application.access import can_access_operation
from trolley.application.pagination import query_fingerprint
from trolley.auth.context import AuthContext
from trolley.auth.roles import effective_role
from trolley.connectors.export import export_jsonl
from trolley.persistence.models import ApiKey, ExportJob, Operation
from trolley.targets import get_targets
from trolley.validation.operations import validate_definition

logger = logging.getLogger(__name__)


class ExportManager:
    def __init__(self, settings):
        self.settings = settings
        self.limits = settings.exports
        self.directory = Path(self.limits.directory).resolve()
        self.tasks = set()
        self.lock = asyncio.Lock()
        self.cleaner = None

    def path(self, job):
        return self.directory / f"{job.id}.jsonl.gz"

    async def open(self):
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.directory.chmod(0o700)
        await ExportJob.filter(status="running").update(
            status="failed", finished_at=datetime.now(UTC)
        )
        for path in self.directory.glob("*.part"):
            path.unlink(missing_ok=True)
        await self.cleanup()
        self.cleaner = asyncio.create_task(self.sweep())

    async def close(self):
        tasks = list(self.tasks)
        if self.cleaner:
            tasks.append(self.cleaner)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def sweep(self):
        while True:
            await asyncio.sleep(30)
            try:
                await self.cleanup()
            except Exception:
                logger.exception("Export cleanup failed")

    async def cleanup(self):
        for job in await ExportJob.all():
            if job.status in ("failed", "expired") or (
                job.status == "succeeded" and job.expires_at <= datetime.now(UTC)
            ):
                self.path(job).unlink(missing_ok=True)
                if job.status == "succeeded":
                    job.status = "expired"
                    await job.save()

    async def resolve(self, name, arguments, context):
        key = await ApiKey.get(
            id=context.api_key_id, user_id=context.user_id, is_active=True
        ).prefetch_related("user")
        user = key.user
        if not user.is_active:
            raise PermissionError("User is inactive")
        current = AuthContext(
            str(user.id),
            str(key.id),
            effective_role(user.email, user.role, self.settings.admin_emails),
        )
        operation = await Operation.get(name=name).prefetch_related("target")
        if (
            not operation.is_active
            or not operation.target.is_active
            or not await can_access_operation(current, operation)
        ):
            raise PermissionError("Operation access denied")
        validate_definition(operation.target, operation.definition, operation.input_schema)
        if operation.definition.get("export") is not True:
            raise ValueError("Operation is not export-enabled")
        values = dict(arguments)
        bindings = operation.definition.get("bindings", {})
        if set(values) & set(bindings):
            raise ValueError("Server-bound parameters cannot be supplied by the client")
        validate(values, operation.input_schema)
        values.update({name: user.email for name in bindings})
        if set(values) != set(operation.definition.get("parameters", [])):
            raise ValueError("Arguments must match Operation parameters")
        target = get_targets().get(operation.target.name)
        if target is None or target.kind != operation.target.kind:
            raise ValueError("Target is not configured")
        return operation, values, target

    async def start(self, name, arguments, context):
        async with self.lock:
            await self.cleanup()
            if self.tasks:
                raise ValueError("An export is already running; retry later")
            if (
                await ExportJob.filter(status__in=["running", "succeeded"]).count()
                >= self.limits.max_jobs
            ):
                raise ValueError("Export storage quota reached; wait for existing files to expire")
            operation, values, target = await self.resolve(name, arguments or {}, context)
            job = await ExportJob.create(
                operation=operation,
                user_id=context.user_id,
                api_key_id=context.api_key_id,
                arguments=values,
                fingerprint=query_fingerprint(operation, values),
                expires_at=datetime.now(UTC) + timedelta(seconds=self.limits.ttl_seconds),
            )
            task = asyncio.create_task(self.run(job, operation, values, target))
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)
            return self.present(job)

    async def run(self, job, operation, values, target):
        partial = self.path(job).with_suffix(".part")
        try:
            rows, size, file_size = await export_jsonl(
                target.configuration, operation.definition, values, partial, self.limits
            )
            partial.replace(self.path(job))
            job.status = "succeeded"
            job.row_count, job.byte_count, job.file_bytes = rows, size, file_size
            job.expires_at = datetime.now(UTC) + timedelta(seconds=self.limits.ttl_seconds)
        except BaseException as error:
            job.status = "failed"
            self.path(job).unlink(missing_ok=True)
            # DB exceptions can contain source records; do not persist or log their text.
            logger.warning("Export %s failed (%s)", job.id, type(error).__name__)
        finally:
            partial.unlink(missing_ok=True)
            job.finished_at = datetime.now(UTC)
            try:
                await job.save()
            except Exception:
                self.path(job).unlink(missing_ok=True)
                logger.error("Could not finalize export %s", job.id)

    async def get(self, job_id, context):
        try:
            job = await ExportJob.get_or_none(
                id=UUID(job_id), user_id=context.user_id
            ).prefetch_related("operation")
        except ValueError as error:
            raise ValueError("Export not found") from error
        if job is None:
            raise ValueError("Export not found")
        original = job.operation
        arguments = {
            k: v
            for k, v in job.arguments.items()
            if k not in original.definition.get("bindings", {})
        }
        operation, values, _ = await self.resolve(original.name, arguments, context)
        if query_fingerprint(operation, values) != job.fingerprint:
            raise PermissionError(
                "Export definition or caller identity changed; create a new export"
            )
        if job.expires_at <= datetime.now(UTC) and job.status == "succeeded":
            self.path(job).unlink(missing_ok=True)
            job.status = "expired"
            await job.save()
        return job

    def present(self, job):
        return {
            "export_id": str(job.id),
            "status": job.status,
            "row_count": job.row_count,
            "uncompressed_bytes": job.byte_count,
            "file_bytes": job.file_bytes,
            "expires_at": job.expires_at.isoformat(),
            "download_url": f"{self.settings.public_base_url.rstrip('/')}/exports/{job.id}/download"
            if job.status == "succeeded"
            else None,
            "download_auth": "Bearer API key of the export owner; never put keys in URLs or chat",
        }
