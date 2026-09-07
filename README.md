# Trolley

Trolley lets people and agents use approved PostgreSQL operations as MCP Tools,
without receiving database credentials or SQL definitions.

An administrator creates a Tool once, shares it with a group, and invites people
to that group. Members can discover and run the group's Tools immediately.

```text
Configure a database → Create an Operation → Grant it to a group → Invite users
```

## Who uses Trolley?

| Who | What they do |
|---|---|
| Server operator | Installs Trolley, configures PostgreSQL connections, and protects credentials |
| Administrator | Creates Tools, manages groups, invites users, and assigns access |
| User or agent | Discovers and runs allowed Tools, or requests a missing Tool |

### Terms used in this guide

- **Target**: a PostgreSQL database configured by the server operator.
- **Operation**: a saved SQL statement, input schema, and access policy, exposed as a Tool.
- **Group**: a collection of users who receive a shared set of Operation grants.
- **Grant**: permission given to a group or an individual to use an Operation.
- **Execution**: a record of an Operation invocation and its outcome.

Trolley controls who can run an Operation, not which rows each group sees inside
that Operation. Use separate Operations or database-side policies for data isolation.
Administrators are trusted to approve SQL; Trolley does not certify SQL as safe.
The Target's PostgreSQL account remains the final security boundary. Use a read-only
account or read replica for reporting Tools.

## 1. Install and start Trolley

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp trolley.example.yaml trolley.yaml
```

Edit `trolley.yaml`:

```yaml
server:
  public_base_url: http://localhost:8000
catalog:
  database_url: sqlite://./trolley.db
admins:
  emails:
    - admin@example.com
targets:
  payments-db:
    kind: postgresql
    url: postgresql://reporting:password@127.0.0.1:5432/payments
    timeout: 10
    query_timeout: 30
    max_rows: 1000
    max_result_bytes: 1000000
```

`admins.emails` is required and lists identities eligible for administrator access.
Keep this file private: it contains credentials. Never commit it to Git.
Use `TROLLEY_CONFIG_FILE=/etc/trolley/trolley.yaml` to select another file.

Check the Target and start the server:

```bash
trolley target list
trolley target check
trolley target test payments-db
trolley
```

In another terminal, issue the first administrator's key:

```bash
trolley admin issue-key admin@example.com --name local-admin
```

The key is printed once. Store it in your MCP client's secret settings, not in an
agent conversation. Trolley stores API key hashes, not recoverable secrets.

The CLI listens on `0.0.0.0:8000`. `server.public_base_url` controls public links,
not the bind address or port. For remote access, put Trolley behind HTTPS and
appropriate network access controls; do not send Bearer tokens over public HTTP.

## 2. Connect your MCP client

Your server's onboarding document provides connection instructions:

```text
http://localhost:8000/onboarding.md
```

A typical client configuration is:

```json
{
  "mcpServers": {
    "trolley": {
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer <enter-your-key-in-client-secret-settings>"
      }
    }
  }
}
```

Adapt this to your client's secret-management mechanism. Do not paste a real key
into a prompt or commit it to a configuration repository.

After connecting, ask:

> List the Operations I can use in Trolley.

The client calls `list_operations`. To run one, it can call the named Tool or
`execute` with the Operation name and inputs. Refresh discovery when permissions
or Tools change; a client's cached Tool list can be stale.

## 3. Create a Tool and share it with a group

The following calls require an administrator connection. No code generation or
server restart is needed.

### Find the database and inspect its tables

Call `list_targets`, then `get_target_schema`:

```json
{"name": "payments-db"}
```

Schema discovery returns the live schema in one response. Use the actual table
and column names from your database; the `payments` table below is an example.
Target credentials cannot be viewed or changed through these management Tools.

### Create a restricted Operation

Call `create_operation`:

```json
{
  "name": "monthly_revenue",
  "target_name": "payments-db",
  "description": "Return revenue for a calendar month",
  "access": "restricted",
  "definition": {
    "sql": "select coalesce(sum(amount), 0) as revenue from payments where paid_at >= $1::text::date and paid_at < ($1::text::date + interval '1 month')",
    "parameters": ["month"],
    "fetch": true
  },
  "input_schema": {
    "type": "object",
    "properties": {
      "month": {"type": "string", "pattern": "^\\d{4}-\\d{2}-01$"}
    },
    "required": ["month"],
    "additionalProperties": false
  }
}
```

`parameters` maps inputs to PostgreSQL placeholders in order; its names must match
`input_schema.required`. Date inputs arrive as strings, so the example casts through
`text`. `fetch: true` returns rows; `fetch: false` returns a PostgreSQL command status.
Use single statements suitable for a transaction.

**Set `access` explicitly.** The current default is `public`, which makes the Tool
available to ordinary users in `standard` mode. A group grant does not make a public
Operation private.

### Create the group and assign the Tool

Call `create_group`:

```json
{"name": "finance", "description": "Finance team"}
```

Call `grant_group_operation`:

```json
{"group_name": "finance", "operation_name": "monthly_revenue"}
```

### Invite a member

With SMTP configured, call `invite_user`:

```json
{
  "email": "analyst@example.com",
  "name": "Analyst",
  "group_names": ["finance"]
}
```

The user receives an API key and onboarding link by email. The key is not returned
to the agent. Groups must already exist. Reinviting a user adds the requested groups
without removing existing memberships.

Emails in `admins.emails` receive the admin role on successful invitation. Other
emails receive the user role. Until delivery and database finalization succeed,
the new key is inactive and no new role or group privileges are applied. If an
invitation fails after delivery, the emailed key remains inactive; retry the invitation.
A failed attempt may leave a user record and an inactive key, but does not revoke
existing keys or memberships.

Without SMTP, use `create_user` with `email`, `name`, and `group_names`, then
`create_api_key` with `email` and `name`. The latter returns a secret once; deliver it
through a secure channel. Unlike `invite_user`, this response exposes the secret to
the calling client, so use a trusted administrator client.

### Run the Tool

The invited user can now ask:

> Get revenue for August 2026.

Or call `execute`:

```json
{"name": "monthly_revenue", "arguments": {"month": "2026-08-01"}}
```

Every read response has the same result shape. This aggregate Operation returns one
page with `has_more: false`:

```json
{"rows": [{"revenue": "1234.50"}], "has_more": false, "next_cursor": null}
```

List Operations can opt into pagination with `definition.pagination`, as shown in the
large-log example below. A named dynamic Tool returns the first page; use `execute` to
choose a page size or continue subsequent pages. The default page size is 100, or the
Target's `max_rows` if smaller. After creating the paginated `request_logs` Operation
shown below, request the first page without a cursor:

```json
{
  "name": "request_logs",
  "arguments": {
    "start_time": "2026-08-01T00:00:00Z",
    "end_time": "2026-09-01T00:00:00Z"
  },
  "page_size": 100
}
```

A paginated response can look like this:

```json
{"rows": [{"request_id": "example-id"}], "has_more": true, "next_cursor": "opaque-cursor"}
```

When `has_more` is true, call `execute` again with the same Operation name,
`arguments`, and `page_size`, adding the returned cursor:

```json
{
  "name": "request_logs",
  "arguments": {
    "start_time": "2026-08-01T00:00:00Z",
    "end_time": "2026-09-01T00:00:00Z"
  },
  "page_size": 100,
  "cursor": "opaque-cursor"
}
```

Do not alter or interpret the cursor. It is bound to the caller, Operation, arguments,
and page size, and expires 15 minutes after the first page. Continue only when the user
needs more rows. Do not describe a partial page as the complete result.

## Managing access

User roles and Operation visibility are separate:

| Operation access | Who can run it |
|---|---|
| `admin` | Administrators only; grants never override this |
| `restricted` | Administrators plus users granted access individually or through a group |
| `public` | Administrators and signed-in users in `standard` mode, plus explicitly granted users |

The legacy value `user` means `public` and remains supported for existing catalogs
and clients. `public` never means unauthenticated access. Restricted Operations
with no grants remain admin-only.

A user can belong to multiple groups. Effective access combines all group grants
and individual grants. Removing one grant does not remove access provided elsewhere.
Inactive Operations or Targets cannot be executed, including by administrators.

To restrict a user to assigned Tools only, call `update_user_access`:

```json
{"email": "analyst@example.com", "operation_access": "assigned_only"}
```

`assigned_only` includes group and individual grants, but excludes automatic public
access. The default user access mode is `standard`.

### Common administration tasks

| Task | Tool |
|---|---|
| List groups / change a description | `list_groups` / `update_group` |
| Replace a user's complete group membership | `set_user_groups(email, group_names)` |
| Remove all group membership | `set_user_groups` with `group_names: []` |
| Inspect memberships | `list_group_memberships` (optional `email`, `group_name`) |
| Grant / revoke a group's Tool | `grant_group_operation` / `revoke_group_operation` |
| Inspect group grants | `list_group_operation_grants` (optional `group_name`, `operation_name`) |
| Give / remove an individual exception | `grant_operation` / `revoke_operation` |
| Inspect individual grants | `list_operation_grants` |
| Delete a group and its memberships/grants | `delete_group` (users and Operations are retained) |
| List users / keys | `list_users` / `list_api_keys` |

All these management Tools require admin access. Changes affect subsequent discovery
and execution without reissuing API keys; they do not cancel already-running queries.
Administrator access requires both a stored admin role and inclusion in `admins.emails`.
Removing an email from that file removes admin eligibility after server restart.

## Fixing or retiring a Tool

Use `update_operation` with its `name` and the fields to change: `description`,
`definition`, `input_schema`, or `access`. Supply the complete replacement definition
or schema, not a partial nested patch. The Tool is reloaded immediately.

Use `disable_operation` to hide a Tool and prevent further execution while preserving
its definition, grants, and history. **Updating a disabled Operation reactivates it.**
There is no hard-delete Tool. Names and Targets cannot be changed by update; create
a replacement Operation and disable the old one if either needs to change.

`reload_tools` refreshes active Tool definitions from the catalog, including existing
Tools' descriptions and schemas. Clients may still need to refresh their Tool lists.

## Requesting a missing Tool

Users should check `list_operations` first, then confirm before calling
`request_operation` with a title, description, and reason. Do not include credentials,
private prompts, or sensitive records in the request.

- Users check progress with `list_my_operation_requests`.
- Administrators review with `list_operation_requests`.
- Administrators use `resolve_operation_request` to mark a request `fulfilled` and
  link an Operation, or `rejected` with a note.

Creating or fulfilling a request does not itself grant access: the administrator
must also assign the resulting Operation when it is restricted.

## Query results and large logs

Per-Target limits are controlled by the server operator, not Tool callers:

| Setting | Default | Meaning |
|---|---|---|
| `timeout` | 30 seconds for Operation connections | Connection timeout |
| `query_timeout` | 30 seconds | Execution transaction timeout |
| `max_rows` | 1000 | Maximum rows returned |
| `max_result_bytes` | 1000000 | Conservative serialized-result byte budget |

Paginated Operations return `has_more` and a cursor when a page reaches its requested
size or byte budget. A single row larger than the byte budget fails. Non-paginated
Operations fail rather than silently returning an incomplete report when they exceed a
limit. Queries run in a transaction; ordinary database changes roll back on failures.
This does not undo external side effects or guarantee the outcome of a timed-out commit.
Rows are read incrementally, but a single oversized field still has to be received
before its serialized size can be checked. Limits are not a complete memory sandbox.

For logs, create a Tool with a date range and a pagination definition such as:

```json
{
  "sql": "select request_id, start_time, model, status from request_logs where start_time >= $1::text::timestamptz and start_time < $2::text::timestamptz",
  "parameters": ["start_time", "end_time"],
  "fetch": true,
  "pagination": {"order_by": ["start_time", "request_id"]}
}
```

The order names must be unique output-column identifiers; include a unique final column
to break ties. Trolley wraps the SQL and applies that order and page bounds. Trolley currently
uses offset continuation, so inserts or deletes before the next offset can still cause
duplicates or omissions. Cursors provide continuation and validation, not snapshot
isolation. Select necessary columns; do not expose key secrets
or raw prompts by default. Use a database export/ETL process for full backups instead
of returning the entire log through MCP.

Result dates/times use ISO strings, decimal amounts use strings to preserve precision,
UUIDs use strings, and binary values use `{"base64": "..."}`. Intervals use day/second/
microsecond components; non-finite floats use strings. Unsupported result types fail
with an explicit error; cast unusual PostgreSQL types to text in your SQL.

Execution arguments, results, and errors are saved in the catalog. This may duplicate
sensitive data. Protect and back up the catalog; automatic redaction and history
retention are not implemented. If a successful query returns `audit_warning`, it ran
but its audit finalization failed: investigate server logs, **do not rerun the query**.
Likewise, do not blindly retry writes after a timeout or lost connection.

## Email configuration

Add an SMTP section to `trolley.yaml`, for example for Google Workspace:

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

Use an App Password, not the account password. Omit SMTP to disable invitations by
email. When configured, startup checks SMTP connectivity, TLS, authentication, and
NOOP without sending mail; a failed check prevents startup.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `401` | Missing, invalid, or inactive Bearer key |
| Tool missing | Refresh `list_operations`; check active status, memberships, grants, and user access mode |
| Permission denied | Ask an administrator to check the Operation access and effective grants |
| Query timeout / result limit | Narrow the date range, paginate, or ask the operator to review limits |
| Invitation failed | Check SMTP and server logs; retry for a new key after fixing the cause |
| Generic Tool error | Check server logs; unexpected internal errors are not exposed to callers |

Useful endpoints: `/health`, `/onboarding.md`, `/.well-known/trolley`, and `/mcp/`.
Public onboarding and discovery endpoints do not issue keys.

## Backups and upgrades

Keep both `trolley.yaml` (configuration and credentials) and `trolley.db` (users,
hashed keys, groups, grants, Operations, requests, and execution history). Neither
belongs in Git. Dynamic Tools are catalog data, not Python files or Git commits.

Back up the catalog before upgrading. This release adds three group tables,
`PageCursor` for expiring continuation tokens, and `ExecutionPage` for page audit
context through existing startup schema generation. Existing Execution rows and
access values are preserved: no columns are added to the existing Execution table.
For each paginated execution, the page audit records offset, page size, input cursor,
and query fingerprint; the returned cursor remains in the Execution result.
If a development build already created pagination tables with a different schema,
startup generation will not migrate those tables; plan an explicit migration before
upgrading that catalog.
Check for dynamic Operations whose names collide with new System Tools before an
upgrade; recreate/disable conflicting Operations first. Restart with the new code.
Do not delete an operational catalog to resolve a schema problem.

Current limitations include no versioned migrations, automatic audit retention,
API key revocation/user deactivation management Tools, or multi-process registry
synchronization. Use a single server process and plan database migrations before
production schema changes. Email OTP, OAuth onboarding, and scheduled jobs are not
implemented.

## Development

```bash
pytest
ruff check .
ruff format --check .
```

PostgreSQL integration tests are opt-in. Use a **disposable test database**, never an
operational Target. The role needs schema/table/function creation privileges. Tests
create and remove a uniquely named schema; no other schemas are modified.

```bash
TROLLEY_TEST_POSTGRES_URL=postgresql://test:test@127.0.0.1:5432/trolley_test \
  pytest -q tests/test_postgres_integration.py
```

Without this variable, PostgreSQL integration tests are reported as skipped; the other
tests use an isolated SQLite catalog and mocked PostgreSQL connections. Integration
coverage includes real SQL wrapping/binding, page and byte boundaries, trailing SQL
comments, read-only write rejection, and query timeout.
