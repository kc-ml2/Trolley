# Trolley guide

[← README](../README.md) · [File exports](exports.md)

## Developer exploration

Administrators publish Operations; developers do not. To enable ad-hoc exploration:

1. Create an account with `create_user(role="developer", ...)`, or assign an existing
   non-admin account using `set_user_role(email=..., role="developer")`.
2. Grant a configured Target with `set_target_access(name=..., email=..., allowed=true)`.
   For a group, use `group_name` instead of `email`. Only developer members gain
   exploration access. Use `allowed=false` to revoke the grant.
3. Reconnect the developer client after changing its role. Use `list_targets`,
   `get_target_schema(name=...)`, then `query_target(name=..., sql=..., params=[...])`.
   Bind SQL values with PostgreSQL `$1`, `$2`, … placeholders.

Queries run read-only, obey Target timeouts/result limits, and create audit records,
not Operations. Direct-query pagination/export is not available. Only administrators
can create, update, disable, or share Operations. Ordinary users continue to execute
Operations without needing Target grants.

Configure restricted database credentials: all developers using a Target share its
DB privileges. There is no automatic caller-specific filtering for free SQL. Query
SQL is recorded and may contain sensitive literals; protect the catalog.

[Role and Target access details](target-query-design.md)

## 1. Install and start Trolley

Follow the [Docker quick start](deployment.md#quick-start) or
[local Python setup](deployment.md#local-development). Docker configuration starts from
[trolley.docker.example.yaml](../trolley.docker.example.yaml); local Python uses
[trolley.example.yaml](../trolley.example.yaml). Keep `trolley.yaml` private.

| Setting | Purpose |
|---|---|
| `server.public_base_url` | Public links, not the bind address; CLI listens on `0.0.0.0:8000` |
| `catalog.database_url` | Trolley accounts, permissions, Operations, and history |
| `admins.emails` | Emails eligible for administrator access |
| `targets` | PostgreSQL connections; credentials are managed only by the server operator |
| `smtp` | Optional invitation email delivery |
| `exports` | Optional file export limits; see [exports](exports.md) |

Use `TROLLEY_CONFIG_FILE=/etc/trolley/trolley.yaml` for another configuration path.
Run CLI commands with the same configuration and working directory as the server,
especially when catalog or export paths are relative.

```bash
trolley target list
trolley target check
trolley target test payments-db
```

With SMTP configured, `trolley setup admin@example.com` emails initial administrator
access. Every run creates a new key; existing keys remain valid. Multiple recipients
are processed independently. Setup does not install a service or edit the allowlist.
Without SMTP, use `trolley admin issue-key admin@example.com --name initial-admin`.

## 2. Connect your MCP client

Give your agent the `/onboarding.md` URL from your invitation. Enter the API key yourself
in the client's secret settings—never in chat. Reconnect, then ask:

> Trolley, what can you do for me right now?

The agent calls `get_my_capabilities` for your role, available system tools, and next
steps. `list_operations` lists accessible saved database Operations, not built-in
administrator tools; an empty list does not mean you lack admin access.

For manual setup, adapt this to your client's secret-management mechanism:

```json
{
  "mcpServers": {
    "trolley": {
      "url": "https://trolley.example.com/mcp/",
      "headers": {"Authorization": "Bearer <key-entered-privately>"}
    }
  }
}
```

Use your server's URL. Environment-variable substitution depends on the client.
Refresh discovery when Tools or permissions change.

## 3. Create a Tool and share it with a group

A **Target** is a configured database connection. An **Operation** exposes an
administrator-approved query definition, inputs, and access policy as a Tool.
`shared` definitions use SQL; `caller` definitions use structured ownership and a
server-generated query. A **grant** gives a user or group permission to run a Tool.

As an administrator:

1. Call `list_targets`, then `get_target_schema({"name": "payments-db"})`.
2. Review SQL against the actual schema. Schema discovery returns the live schema in
   one response; it does not paginate it.
3. Call `create_operation` (example table/columns below):

```json
{
  "name": "monthly_revenue",
  "target_name": "payments-db",
  "description": "Revenue for a calendar month",
  "access": "restricted",
  "definition": {
    "data_scope": "shared",
    "sql": "SELECT coalesce(sum(amount), 0) AS revenue FROM payments WHERE paid_at >= $1::text::date AND paid_at < ($1::text::date + interval '1 month')",
    "parameters": ["month"],
    "fetch": true
  },
  "input_schema": {
    "type": "object",
    "properties": {"month": {"type": "string", "pattern": "^\\d{4}-\\d{2}-01$"}},
    "required": ["month"],
    "additionalProperties": false
  }
}
```

`parameters` maps inputs to `$1`, `$2`, etc. Names must match schema-required inputs
for shared SQL Operations. Caller Operations use
[structured ownership](#caller-specific-operations). For shared SQL, dates arrive as
strings; cast through `text` and use a single statement suitable for a transaction.
Shared SQL supports `fetch: true` for rows or `fetch: false` for command status;
caller scope is always read-only and does not accept a `fetch` field.

4. `create_group({"name": "finance", "description": "Finance team"})`
5. `grant_group_operation({"group_name": "finance", "operation_name": "monthly_revenue"})`
6. `invite_user({"email": "analyst@example.com", "name": "Analyst", "group_names": ["finance"]})`

Groups must exist before invitation. Reinviting adds groups without removing existing
memberships. Allowlisted emails receive admin access on successful invitation; others
receive user access. The new key stays inactive until delivery and finalization succeed.
A failed invitation may leave an inactive key and user record, but does not apply new
role/group privileges. Retry after fixing the failure.

Without SMTP, use `create_user` with `group_names`, then `create_api_key`. The latter
returns the secret to the calling client once: use a trusted administrator client and
secure delivery channel. `invite_user` does not return the secret through MCP.

The member can now call the named Tool or `execute`:

```json
{"name": "monthly_revenue", "arguments": {"month": "2026-08-01"}}
```

## Managing access

| Operation access | Who can run it |
|---|---|
| `admin` | Administrators only; grants cannot override this |
| `restricted` | Administrators plus individual/group grant recipients |
| `public` | Administrators, standard signed-in users, and explicit grant recipients |

**Set access explicitly:** the default is `public`. Granting a public Operation to a
group does not make it private. Legacy `user` means `public`; unauthenticated access
is never allowed. Restricted Operations with zero grants remain admin-only.

User access defaults to `standard`. To exclude automatic public access:

```json
{"email": "analyst@example.com", "operation_access": "assigned_only"}
```

Pass this to `update_user_access`. Assigned-only users still receive both individual
and group grants. Multiple grants are additive: removing one does not revoke access
provided elsewhere. Groups control Tool access, **not row isolation**.

| Task | Tool |
|---|---|
| Create/list/edit/delete a group | `create_group`, `list_groups`, `update_group`, `delete_group` |
| Replace all user memberships | `set_user_groups(email, group_names)`; `[]` removes all |
| Inspect memberships | `list_group_memberships(email?, group_name?)` |
| Grant/revoke a group's Tool | `grant_group_operation`, `revoke_group_operation` |
| Inspect group grants | `list_group_operation_grants(group_name?, operation_name?)` |
| Grant/revoke an individual exception | `grant_operation`, `revoke_operation` |
| Inspect individual grants | `list_operation_grants` |
| List users/keys | `list_users`, `list_api_keys` |

Management Tools are admin-only. Deleting a group retains its users and Operations.
Changes affect subsequent requests, not already-running queries. Inactive Operations
or Targets cannot be executed even by admins. Admin access requires both a stored
admin role and inclusion in `admins.emails`; file changes require restart.

## Fixing or retiring a Tool

`update_operation` accepts `name` and changed `description`, `definition`, `input_schema`,
or `access`. Definitions/schemas are complete replacements, not nested patches.
Updates reload the Tool immediately and **reactivate disabled Operations**.

`disable_operation` hides the Tool and blocks new execution while preserving grants and
history. There is no hard-delete Tool. To change a name or Target, create a replacement
and disable the old Operation. Tool definitions refresh automatically on startup and
on creation, update, or disable. Clients may need to refresh their cached lists.
There is no manual reload tool or built-in Operation request workflow. Contact an
administrator outside Trolley if a needed Tool is missing.

Personal-data Operations must bind the authenticated caller's email on the server and
use it in the SQL row filter. Do not expose a target person's email as a public input.
Administrators can use `query_target` for cross-user investigation.

## Query results and large logs

| Need | Use |
|---|---|
| Aggregate or single result | `execute` or the named Tool |
| Explore a list | Pagination-enabled Operation via `execute` |
| Download approved query results | Call a [file-output Operation](exports.md); poll `get_execution` |

Reads return `result: {"rows": [...], "has_more": false, "next_cursor": null}` inside
an execution response. Dates use ISO strings and decimals use strings without rounding;
UUIDs are strings and binary values use `{"base64": "..."}`. Cast unsupported database
types to text. Writes return a command status instead of pages.

### Pagination

For a list query, set its definition's `pagination`:

```json
{
  "data_scope": "shared",
  "sql": "SELECT request_id, start_time, model FROM request_logs WHERE start_time >= $1::text::timestamptz AND start_time < $2::text::timestamptz",
  "parameters": ["start_time", "end_time"],
  "pagination": {"order_by": ["start_time", "request_id"]}
}
```

Also define required string inputs `start_time` and `end_time` in `input_schema`.
Use actual output columns and a unique final ordering column to break ties. Paginated
queries run read-only. The first page via `execute` omits `cursor`:

```json
{
  "name": "request_logs",
  "arguments": {"start_time": "2026-08-01T00:00:00Z", "end_time": "2026-09-01T00:00:00Z"},
  "page_size": 100
}
```

If `has_more` is true, repeat with unchanged arguments/page size and the returned
`next_cursor` as `cursor`. The default size is `min(100, max_rows)`; named Tools return
that first page. Cursors are caller/query-bound and expire 15 minutes after page one.
Do not claim completeness while `has_more` is true or fetch beyond the user's scope.

Continuation uses offsets, **not a snapshot**: concurrent inserts/deletes can cause
omissions or duplicates. Export uses a single snapshot instead; it is not automatically
selected when a query becomes large.

### Limits and history

Per-Target settings in `trolley.yaml`:

| Setting | Default |
|---|---|
| `timeout` — connection | 30 seconds for Operation connections |
| `query_timeout` — execution | 30 seconds |
| `max_rows` — maximum page/result rows | 1000 |
| `max_result_bytes` — serialized-result budget | 1000000 |

Paginated reads stop at the page/byte budget with a continuation cursor. Non-paginated
reads fail on overflow rather than returning a silent partial result. One oversized
row fails and must still be received before its size can be checked. These limits are
not a complete memory sandbox. For full database backups, use database backup tooling.

Execution arguments/results/errors are stored in the catalog; pagination metadata is
also recorded. Protect this potentially sensitive data. Automatic redaction and audit
retention are not implemented. An `audit_warning` means the query succeeded but audit
finalization failed: investigate logs, **do not rerun it**. Do not blindly retry writes
after timeout or lost connection; commit outcome or external side effects may be unknown.

## Caller-specific Operations

Personal-data Operations must declare `data_scope: "caller"`, an ownership column,
and a structured source/column/filter definition. The server resolves the API key's
owning account email and generates a mandatory owner filter; users cannot provide
or override it. Administrators invoking these Operations also see only their own
rows. Cross-user investigation uses `query_target`.

See [the personal data contract](caller-data.md) for complete definition/input-schema
examples, key-sharing semantics, and the administrator's responsibility to review
source ownership. Arbitrary SQL and legacy caller bindings are rejected in caller
scope. Other Operations must explicitly declare `data_scope: "shared"`.

## Email configuration

Add to `trolley.yaml`, for example for Google Workspace:

```yaml
smtp:
  host: smtp.gmail.com
  port: 587
  security: starttls
  username: trolley@example.com
  password: google-app-password
  from: Trolley <trolley@example.com>
  timeout: 10
```

Use an App Password. Omit SMTP to disable email invitations. Configured SMTP is checked
at startup (connection, TLS, authentication, NOOP); failure prevents startup.

## Troubleshooting

| Symptom | Check |
|---|---|
| `401` | Missing, invalid, or inactive Bearer key |
| Tool missing | Refresh capabilities/Operations; check active state, grants, memberships, access mode |
| Permission denied | Ask an admin to review effective access |
| Query timeout/limit | Narrow the range, paginate, or request an enabled export |
| Invitation failed | Fix SMTP/finalization error, then retry for a new key |
| Generic Tool error | Server logs; unexpected internal errors are hidden from callers |

Endpoints: `/health`, `/onboarding.md`, `/.well-known/trolley`, `/mcp/`.
Public onboarding/discovery does not issue keys. Use HTTPS for remote access.

## Backups and upgrades

Back up `trolley.yaml` and the catalog (`trolley.db` by default); keep both out of Git.
Dynamic Tools are catalog data, not source files. Export files are sensitive temporary
artifacts; see [export storage](exports.md#operator-configuration).

Group, cursor, page-audit, and export-job tables are created at startup. Schema generation
**does not migrate existing tables**. Back up before upgrading and explicitly migrate
incompatible development schemas. Check dynamic Tool names against new reserved system
names, then restart. Never delete an operational catalog to fix a schema error.

Use a single server process. Versioned migrations, automatic audit retention, key expiry,
key-revocation/user-deactivation management Tools, multi-process registry synchronization,
OAuth onboarding, and scheduled jobs are not implemented.

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
```

With Docker running, `./scripts/test-postgres-integration.sh` creates a disposable
PostgreSQL container, runs integration tests, and removes it. To choose the Python
interpreter: `PYTHON=venv/bin/python ./scripts/test-postgres-integration.sh`.

Alternatively set `TROLLEY_TEST_POSTGRES_URL` and run
`pytest tests/test_postgres_integration.py`. Use a disposable database, never an
operational Target; tests create/drop a unique schema and need schema/function privileges.
Without a test database, PostgreSQL tests are skipped; other tests use SQLite and mocks.
