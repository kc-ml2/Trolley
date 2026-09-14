# Personal data access contract

## Identity

An API key authenticates its owning Trolley account, not the human currently typing.
The server resolves the active account's registered email and uses it as the caller
identity. Never accept identity from chat, SQL arguments, or an agent-provided email.
Sharing a key shares the owner's access. Administrators running a caller Operation
also receive their own data; cross-user investigation uses `query_target`.

Account email assignment and changes must be trusted. The database administrator
must ensure that the source's ownership column truthfully identifies the owner of
all data in each row. User-editable email labels are not a safe ownership boundary.
Use separate database roles/Targets or RLS for stronger isolation as needed.

## Explicit scope is mandatory

Every Operation definition must declare `data_scope`:

- `caller`: server-generated, read-only query with mandatory owner equality filter.
- `shared`: administrator-authored SQL, with results accessible to every authorized
  Operation caller. This is not personal-data isolation; review carefully.

Missing scope fails creation, update, and execution. Legacy SQL bindings are no
longer an accepted personal-data contract. Existing definitions must be rewritten
explicitly; no automatic conversion or silent shared default is provided.

## Caller definition

```json
{
  "data_scope": "caller",
  "source": {"schema": "public", "relation": "usage_logs"},
  "ownership": {"column": "owner_email", "identity": "authenticated_user.email"},
  "columns": ["id", "day", "total_tokens"],
  "filters": [{"column": "day", "operator": "gte", "parameter": "start_date"}],
  "output": "file"
}
```

Matching input schema:

```json
{
  "type": "object",
  "properties": {"start_date": {"type": "string"}},
  "required": ["start_date"],
  "additionalProperties": false
}
```

The server generates the equivalent of:

```sql
SELECT "id", "day", "total_tokens"
FROM "public"."usage_logs"
WHERE "owner_email" = $1 AND "day" >= $2
```

`$1` is bound by the server; `$2` is the caller's start_date. Only simple quoted
identifiers and fixed comparison operators (`eq`, `gte`, `gt`, `lte`, `lt`) are
accepted. Filter values are bound parameters. All public inputs must correspond
exactly to required filter parameters. No public owner filter, arbitrary SQL,
expressions, joins, subqueries, custom parameters, or custom bindings are accepted.
The internal `trolley_caller_email` parameter is reserved and cannot be supplied by
clients. Column existence/types are checked by PostgreSQL at execution, not by a
live introspection call during publication.

Inline and file execution use the same compiled predicate. Inline caller queries
are read-only and can use existing pagination. File output cannot paginate.
Changing identity/definition invalidates existing continuation/download access.

## Limits of the guarantee

The server guarantees that its generated query filters rows of the configured
source by authenticated identity. It cannot prove the contents of a row belong to
that identity. A view that labels a global aggregate with one person's email, or
returns another person's data in a column, violates the source contract. Views,
computed columns/functions, and identity mappings require administrator review.
Do not claim this replaces DB security, verifies arbitrary views, or certifies
administrator-authored shared SQL. Complex personal analytics should use a reviewed
owner-preserving source or separately designed DB-level isolation, not a raw SQL
escape hatch in caller scope.
