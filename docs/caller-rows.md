# Mapped caller ownership for raw rows and files

The mapped `ownership` used by aggregates also works with `columns`. Both inline
and file execution use the same correlated EXISTS predicate. Duplicate owner rows
do not duplicate source rows. The caller email is supplied by the server, never
accepted as an input. Missing/non-string JSON owner emails do not authorize rows.

Example definition (review the sensitivity of messages/response before publication):

```json
{
  "data_scope": "caller",
  "source": {"schema": "public", "relation": "LiteLLM_SpendLogs"},
  "ownership": {
    "source": {"schema": "public", "relation": "LiteLLM_VerificationToken"},
    "source_column": "api_key",
    "match_column": "token",
    "column": "metadata",
    "json_key": "owner_email",
    "identity": "authenticated_user.email"
  },
  "columns": ["request_id", "session_id", "startTime", "model", "messages", "response"],
  "filters": [
    {"column": "startTime", "operator": "gte", "parameter": "start", "type": "timestamp"},
    {"column": "startTime", "operator": "lt", "parameter": "end", "type": "timestamp"}
  ],
  "output": "file"
}
```

Declare required string inputs `start` and `end`, with `additionalProperties: false`.
For example, `2026-09-01 00:00:00` through `2026-09-15 00:00:00` uses an inclusive
start and exclusive end. Confirm the source timestamp storage convention first.
`timestamp` refers to a timestamp without timezone; supply timezone-free values.
Use `timestamptz` only for timezone-aware columns/semantics, with explicit offsets.
`date` is also supported. These fixed casts bind strings via text; arbitrary SQL
casts are not allowed. Existing untyped filters retain their previous behavior.

File output cannot paginate. Set output to inline (or omit it) to return bounded
rows; inline queries can use pagination with a unique output ordering.

JSONB values currently follow asyncpg's default representation: JSON-encoded strings
inside each JSONL row. They are not redacted or flattened. Parse those strings to
recover nested arrays/objects. This change does not alter that existing output contract.
Caller isolation establishes ownership of the key, not authorship of every message.
Shared keys and owner reassignment affect access to historical records. Source text
is untrusted data and may contain secrets. Keep downloads private.
