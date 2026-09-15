"""Catalog metadata, not executable instructions or authorization policy."""

from datetime import UTC, datetime

from tortoise.transactions import in_transaction

from trolley.application.target_access import require_target
from trolley.auth.context import AuthContext
from trolley.persistence.models import TargetNotes, TargetNotesRevision


def present(notes: TargetNotes | None) -> dict:
    return {
        "description": notes.description if notes else "",
        "data_notes": notes.data_notes if notes else "",
        "version": notes.version if notes else 0,
        "updated_by": str(notes.updated_by) if notes and notes.updated_by else None,
        "updated_at": notes.updated_at.isoformat() if notes and notes.updated_at else None,
    }


async def get_target_notes(context: AuthContext, name: str) -> dict:
    target = await require_target(context, name)
    return {"target": name, **present(await TargetNotes.get_or_none(target=target))}


async def update_target_notes(
    context: AuthContext,
    name: str,
    expected_version: int,
    description: str | None = None,
    data_notes: str | None = None,
) -> dict:
    target = await require_target(context, name)
    if expected_version < 0:
        raise ValueError("expected_version must be non-negative")
    if description is None and data_notes is None:
        raise ValueError("Provide description or data_notes; empty string clears a field")
    for value, limit in ((description, 2000), (data_notes, 20000)):
        if value is not None and len(value) > limit:
            raise ValueError(f"Field exceeds {limit} characters")
    async with in_transaction() as db:
        notes, _ = await TargetNotes.get_or_create(target=target, using_db=db)
        if notes.version != expected_version:
            raise ValueError("Target notes version conflict; fetch notes again before updating")
        before = present(notes)
        changes = {
            "description": notes.description if description is None else description,
            "data_notes": notes.data_notes if data_notes is None else data_notes,
            "version": expected_version + 1,
            "updated_by": context.user_id,
            "updated_at": datetime.now(UTC),
        }
        count = (
            await TargetNotes.filter(target=target, version=expected_version)
            .using_db(db)
            .update(**changes)
        )
        if count != 1:
            raise ValueError("Target notes version conflict; fetch notes again before updating")
        notes = await TargetNotes.get(target=target).using_db(db)
        after = present(notes)
        await TargetNotesRevision.create(
            target=target,
            version=notes.version,
            before=before,
            after=after,
            updated_by=context.user_id,
            using_db=db,
        )
    return {"target": name, **after}
