"""Opaque, expiring continuation tokens bound to a caller and query definition."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from trolley.persistence.models import PageCursor


def query_fingerprint(operation, arguments):
    return hashlib.sha256(
        json.dumps(
            {
                "definition": operation.definition,
                "input_schema": operation.input_schema,
                "target": str(operation.target_id),
                "arguments": arguments,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


async def resolve_page(operation, context, arguments, page_size, cursor, max_rows):
    fingerprint = query_fingerprint(operation, arguments)
    now = datetime.now(UTC)
    if cursor is not None:
        try:
            cursor_id = UUID(cursor)
        except ValueError as error:
            raise ValueError("Invalid page cursor") from error
        saved = await PageCursor.get_or_none(
            id=cursor_id,
            operation=operation,
            user_id=context.user_id,
            fingerprint=fingerprint,
            expires_at__gt=now,
        )
        if saved is None:
            raise ValueError("Invalid or expired cursor, or query conditions changed")
        if page_size is not None and page_size != saved.page_size:
            raise ValueError("Keep the same page_size when continuing a query")
        page_size = saved.page_size
        offset = saved.offset
        expires_at = saved.expires_at
    else:
        offset = 0
        expires_at = now + timedelta(minutes=15)
        page_size = page_size if page_size is not None else min(100, max_rows)
    if type(page_size) is not int or not 1 <= page_size <= max_rows:
        raise ValueError(f"page_size must be between 1 and {max_rows}")
    return offset, page_size, fingerprint, expires_at


async def next_page(operation, context, offset, page_size, fingerprint, expires_at):
    await PageCursor.filter(expires_at__lte=datetime.now(UTC)).delete()
    saved = await PageCursor.create(
        operation=operation,
        user_id=context.user_id,
        offset=offset,
        page_size=page_size,
        fingerprint=fingerprint,
        expires_at=expires_at,
    )
    return str(saved.id)
