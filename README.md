# Trolley

Trolley lets an MCP client use selected PostgreSQL queries and HTTP requests as tools without giving the client unrestricted access to the underlying service.

```text
MCP client → Trolley Tool → approved Operation → PostgreSQL / HTTP API
```

A server operator connects infrastructure once. An MCP administrator then creates narrowly scoped Operations at runtime. Regular users only see and invoke the Operations they are allowed to use.

For example, an administrator can turn a SQL report into a Tool named `monthly_revenue`. An agent can then call:

```text
monthly_revenue(month="2026-08-01")
```

The agent does not receive the database URL, credentials, or SQL definition.

## Who does what?

| Role | What they do |
|---|---|
| Server operator | Installs Trolley, edits `targets.yaml`, protects credentials, and runs local connection checks |
| MCP administrator | Inspects Target schemas and dynamically creates, updates, disables, and grants Operations through MCP |
| MCP user or agent | Discovers and invokes only the dynamic Tools allowed for its Trolley identity |

This separation is intentional: MCP administrators can build useful database and API tools, but they cannot add or change infrastructure credentials through MCP.

## Core concepts

- **Target**: a PostgreSQL database or HTTP API configured by the server operator in `targets.yaml`.
- **Operation**: an approved SQL statement or HTTP request stored in Trolley and exposed as a dynamic MCP Tool.
- **User**: a human or agent identity authenticated with a Trolley Bearer API key.
- **Execution**: an audited Operation invocation, including its caller, arguments, result, status, and timestamps.

Trolley does not run agents or manage processes on Target servers.

## Quick start

Python 3.11 or newer is required.

### 1. Install Trolley

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
cp targets.example.yaml targets.yaml
chmod 600 targets.yaml
```

### 2. Configure the Trolley server

Configure Trolley itself in `.env`:

```dotenv
TROLLEY_DATABASE_URL=sqlite://./trolley.db
TROLLEY_PUBLIC_BASE_URL=http://localhost:8000
TROLLEY_ADMIN_EMAILS=admin@example.com
TROLLEY_TARGETS_FILE=./targets.yaml
```

`TROLLEY_ADMIN_EMAILS` is the allowlist of identities that may receive MCP administrator privileges. It is required even for a local installation.

### 3. Register infrastructure Targets

The server operator—not an MCP client—configures Target connections in `targets.yaml`:

```yaml
targets:
  litellm-db-replica:
    kind: postgresql
    url: postgresql://user:password@127.0.0.1:5433/litellm
    timeout: 10

  orders-api:
    kind: http
    base_url: https://api.example.com
    timeout: 30
    headers:
      Accept: application/json
    bearer_token: replace-me
```

`targets.yaml` contains real credentials. Keep it readable only by the Trolley service account and do not commit it to Git:

```bash
chmod 600 targets.yaml
```

The repository ignores `.env`, `targets.yaml`, and `trolley.db` by default.

Validate the configuration and test PostgreSQL connections locally:

```bash
trolley target list
trolley target check
trolley target test litellm-db-replica
```

### 4. Start the server

Start Trolley to initialize its catalog and serve MCP:

```bash
trolley
```

Trolley synchronizes Target names and kinds into its catalog, while credentials remain only in `targets.yaml`.

### 5. Issue an administrator key

In another terminal, issue a key locally for an allowlisted administrator:

```bash
trolley admin issue-key admin@example.com --name local-admin
```

The secret is printed once. Treat it like a password.

Endpoints:

```text
MCP:        http://localhost:8000/mcp/
Onboarding: http://localhost:8000/onboarding.md
Discovery:  http://localhost:8000/.well-known/trolley
Health:     http://localhost:8000/health
```

### 6. Connect an MCP client

An agent can read the public onboarding document before Trolley is registered:

```text
http://localhost:8000/onboarding.md
```

The document tells the agent how to prepare the MCP configuration without receiving the secret. The user remains responsible for obtaining an API key from an administrator and entering it directly into the MCP client's secret settings or a local `TROLLEY_API_KEY` environment variable. API keys should never be pasted into an agent conversation.

After connecting, the agent should call `list_operations` to discover the latest Operations available to the authenticated user, then call `execute` with arguments matching the selected Operation's `input_schema`. Calling `list_operations` again handles runtime Operation and permission changes without relying on a cached MCP Tool list. If no Operation meets the user's need, the agent may ask for confirmation and record a non-sensitive request with `request_operation`; `list_my_operation_requests` shows its status.

Use the issued key as an HTTP Bearer token. A typical MCP client configuration is:

```json
{
  "mcpServers": {
    "trolley": {
      "url": "http://localhost:8000/mcp/",
      "headers": {
        "Authorization": "Bearer sk-trolley-issued-key"
      }
    }
  }
}
```

The exact configuration file depends on the client, but the resulting request must contain:

```http
Authorization: Bearer sk-trolley-issued-key
```

After connecting, an administrator can list configured Targets, inspect a PostgreSQL schema, and create dynamic Operations. Target creation, deletion, credentials, and connectivity testing are deliberately unavailable through MCP.

## Create your first dynamic PostgreSQL Tool

The following workflow happens entirely through an administrator MCP connection. You do not edit Python code, commit generated Tool files, or restart Trolley.

### 1. Discover available Targets

Ask your MCP client to call `list_targets`, or simply prompt it with:

```text
List the Targets available in Trolley.
```

The response contains safe identity information only:

```json
[
  {
    "name": "litellm-db-replica",
    "kind": "postgresql"
  }
]
```

Connection strings, credentials, HTTP headers, and other Target settings are never included.

### 2. Inspect the live Target schema

An administrator can call `get_target_schema`:

```json
{"name": "litellm-db-replica"}
```

It returns the complete live PostgreSQL schema, including tables, views, columns, primary keys, and foreign keys. This gives the administrator—or an AI agent acting as the administrator—the context needed to write a valid, narrowly scoped query.

Trolley currently reads the schema live and returns it in one response. It does not cache, snapshot, search, or paginate schema results.

### 3. Create an Operation dynamically through MCP

An MCP administrator calls `create_operation` with an approved SQL statement, its parameters, an input schema, and an access level:

```json
{
  "name": "monthly_revenue",
  "target_name": "litellm-db-replica",
  "description": "Return revenue for a calendar month",
  "access": "user",
  "definition": {
    "sql": "select coalesce(sum(amount), 0) as revenue from payments where paid_at >= $1::date and paid_at < ($1::date + interval '1 month')",
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

`definition.parameters` maps Tool arguments to PostgreSQL placeholders in order: `month` becomes `$1`. The parameter names must match `input_schema.required`. `fetch: true` returns rows; use `fetch: false` for statements that only return a PostgreSQL status.

### 4. Use the new Tool immediately

The Operation is stored in Trolley's catalog database and immediately exposed under its own MCP Tool name:

```text
monthly_revenue(month="2026-08-01")
```

No Python file, Git commit, deployment, or Trolley restart is required. Some MCP clients may need to refresh their Tool list before the new Tool appears.

A caller can also use the compatibility `execute` System Tool:

```json
{
  "name": "monthly_revenue",
  "arguments": {
    "month": "2026-08-01"
  }
}
```

### 5. Update or remove the Tool at runtime

An administrator can change its SQL, schema, description, or access policy with `update_operation`. Trolley reloads the Tool in-process. Calling `disable_operation` marks it inactive and removes it from the MCP Tool list.

### Where dynamic Tools are stored

Dynamic Tools are data, not source files:

```text
create_operation
→ Operation row in trolley.db
→ DynamicToolRegistry
→ live MCP Tool
→ shared Trolley executor
→ configured Target
```

By default, `trolley.db` stores:

- Operation definitions and access policies
- Trolley Users and hashed API keys
- explicit Operation grants
- Execution audit records and results

`trolley.db` is ignored by Git. Back it up as runtime state if you need to preserve dynamic Tools across server replacement. On ordinary Trolley restarts, active Operations are loaded from the database and registered again automatically.

## Users, keys, and access

All API key secrets are stored as SHA-256 hashes and returned only once when issued.

### Roles and Operation access

- `admin`: manages Trolley Users, API keys, Operations, and grants; lists Targets; inspects PostgreSQL schemas; and invokes every Operation. It cannot change Target credentials through MCP.
- `user`: discovers and invokes Operations according to the Operation visibility, User access mode, and explicit grants.

An Operation has one access level:

- `user`: available to users in `standard` mode.
- `restricted`: available only to explicitly granted users.
- `admin`: available only to admins; a grant cannot override this restriction.

A User has one Operation access mode:

- `standard`: receives `user` Operations plus explicitly granted `restricted` Operations.
- `assigned_only`: receives only explicitly granted non-admin Operations, including a specifically granted `user` Operation.

Admins always see every active Operation. Other users receive the Tool's name, description, and input schema, but never its SQL/HTTP definition or direct Target configuration. Tool visibility and execution permission are both checked against current catalog state, so revoking access takes effect without restarting Trolley.

### Request a missing Operation

After checking `list_operations`, an authenticated user can call `request_operation` with a title, description, and reason. The agent should obtain the user's confirmation first and must not include credentials or sensitive data. Users can track their own requests with `list_my_operation_requests`.

Administrators review requests with `list_operation_requests`. After creating the corresponding Operation, an administrator calls `resolve_operation_request` with status `fulfilled` and the active Operation name, or rejects it with status `rejected` and an explanatory note. Request states are `pending`, `fulfilled`, and `rejected`.

### Admin lock

`TROLLEY_ADMIN_EMAILS` is the authoritative allowlist for administrator eligibility:

```dotenv
TROLLEY_ADMIN_EMAILS=admin@example.com,ops@example.com
```

Admin access requires both conditions:

```text
stored User.role == admin
AND
normalized User.email is in TROLLEY_ADMIN_EMAILS
```

Consequences:

- An admin cannot assign the admin role to an email outside the allowlist.
- Adding an email to the allowlist does not automatically promote an existing user.
- Removing an email from the allowlist removes admin scope from its existing keys after Trolley restarts.
- When no active allowlisted admin exists, startup creates or promotes Users for the configured emails; it does not issue keys.

### Give an agent access to Trolley

An administrator can create a separate Trolley identity for a person, service, or AI agent by calling `create_user`:

```json
{
  "email": "agent@example.com",
  "name": "Reporting Agent",
  "role": "user"
}
```

Then call `create_api_key`:

```json
{
  "email": "agent@example.com",
  "name": "reporting-client"
}
```

The `secret` in the response is shown once. Configure it as that user's MCP Bearer token. API key secrets are stored only as SHA-256 hashes, so Trolley cannot display an existing secret later; issue a new key if one is lost.

When SMTP is configured, an administrator can instead call `invite_user`. It creates a normal user when needed (or reuses an existing active non-admin user), issues an API key, and emails the key with the onboarding URL. The secret is not returned through MCP. If delivery fails, the newly issued key is immediately disabled while the User remains available for a retry.

### Restrict a user to assigned Operations

Set a User to `assigned_only` with `update_user_access`:

```json
{
  "email": "agent@example.com",
  "operation_access": "assigned_only"
}
```

Assign one Operation with `grant_operation`:

```json
{
  "email": "agent@example.com",
  "operation_name": "monthly_revenue"
}
```

That user now sees and invokes `monthly_revenue`, but does not receive other public Operations. Use `revoke_operation` to remove access:

```json
{
  "email": "agent@example.com",
  "operation_name": "monthly_revenue"
}
```

Use `list_operation_grants` with optional `email` and `operation_name` filters to inspect assignments. Grants to `admin` Operations are rejected.

## Built-in System Tools

System Tools are fixed administrative and compatibility functions shipped with Trolley. Their names are reserved and cannot be reused by a dynamic Operation.

### Admin-only

- `list_users`
- `create_user`
- `update_user_access`
- `list_api_keys`
- `create_api_key`
- `list_targets`
- `get_target_schema`
- `create_operation`
- `update_operation`
- `disable_operation`
- `grant_operation`
- `revoke_operation`
- `list_operation_grants`
- `reload_tools`

### Authenticated users

- `list_operations`: returns only Operations visible to the caller.
- `execute`: invokes a visible Operation by name.

Active Operations are additional dynamic Tools. `update_operation` reloads a Tool in-process, `disable_operation` removes it, and `reload_tools` synchronizes the full registry with the database.

## Create a dynamic HTTP Tool

As with databases, the server operator first configures the HTTP Target in `targets.yaml`:

```yaml
targets:
  orders-api:
    kind: http
    base_url: https://api.example.com
    timeout: 30
    bearer_token: replace-me
```

After restarting Trolley, an MCP administrator dynamically registers an HTTP Operation:

```json
{
  "name": "get_orders",
  "target_name": "orders-api",
  "description": "List orders",
  "access": "user",
  "definition": {
    "method": "GET",
    "path": "/orders"
  },
  "input_schema": {
    "type": "object",
    "properties": {
      "status": {"type": "string"}
    },
    "additionalProperties": false
  }
}
```

The Operation immediately appears as `get_orders(status=...)`. HTTP `bearer_token` credentials are sent as Bearer tokens. GET and DELETE arguments become query parameters; other methods receive a JSON body. HTTP schema inspection and connectivity testing are not currently implemented, so the administrator must know the API contract when creating the Operation.

## Runtime state and backups

A typical installation separates runtime state from safe configuration templates:

| Path | Purpose | Commit to Git? |
|---|---|---|
| `.env` | Trolley process configuration | No |
| `targets.yaml` | Target URLs, credentials, and headers | No |
| `trolley.db` | Users, hashed keys, dynamic Operations, grants, and Execution history | No |
| `.env.example`, `targets.example.yaml` | Safe configuration templates | Yes |

Back up `targets.yaml` and `trolley.db` together when moving a Trolley installation. Protect both with operating-system permissions. A catalog backup without `targets.yaml` preserves Operation definitions but cannot connect them to infrastructure; a Target file without the catalog loses dynamic Tools and Trolley identities.

## Security model

Every System Tool passes through a shared pipeline:

```text
Bearer token
→ active API key
→ active User
→ effective role and scopes
→ System Tool policy
→ basic input validation
→ use case
```

Every dynamic Tool is checked again at execution time:

```text
authenticated caller
→ current User access mode and Operation grants
→ current Operation and Target state
→ Operation access level
→ JSON Schema validation
→ shared SQL or HTTP executor
→ Execution audit record
```

For PostgreSQL, argument values are passed through asyncpg parameter binding rather than interpolated into SQL. The database account configured in `targets.yaml` remains the final authority: use a read-only account or a physical read replica when Operations should only query data.

Target credentials remain in the server-owned Target YAML file. MCP Tool responses do not include connection strings, tokens, headers, or other Target configuration. Dynamic Operations cannot execute Python or shell code; they are limited to the SQL or HTTP capabilities provided by their Target connector.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TROLLEY_DATABASE_URL` | `sqlite://./trolley.db` | Trolley's catalog and execution-history database |
| `TROLLEY_PUBLIC_BASE_URL` | `http://localhost:8000` | Public base URL used by MCP authentication metadata |
| `TROLLEY_TARGETS_FILE` | `targets.yaml` | Server-owned YAML file containing Target configuration and credentials |
| `TROLLEY_ADMIN_EMAILS` | **required** | Comma-separated admin eligibility allowlist; also used to create admin Users when no active allowlisted admin exists |
| `TROLLEY_EMAIL_FROM` | — | Sender address used for invitations; required with `TROLLEY_SMTP_HOST` |
| `TROLLEY_SMTP_HOST` | — | SMTP server hostname; omit it to disable email delivery |
| `TROLLEY_SMTP_PORT` | `587` | SMTP server port |
| `TROLLEY_SMTP_USERNAME` | — | Optional SMTP username; requires a password |
| `TROLLEY_SMTP_PASSWORD` | — | Optional SMTP password, stored as a secret setting |
| `TROLLEY_SMTP_SECURITY` | `starttls` | SMTP transport security: `plain`, `starttls`, or `tls` |
| `TROLLEY_SMTP_TIMEOUT` | `10` | SMTP connection timeout in seconds |

When `TROLLEY_SMTP_HOST` is configured, startup performs an SMTP connection, TLS, authentication, and `NOOP` check without sending a message. A failed check prevents startup, ensuring `invite_user` is not exposed with unavailable email delivery. When the host is omitted, email is disabled and `/health` reports it as such.

`GET /onboarding.md` provides public, agent-readable connection instructions, and `GET /.well-known/trolley` exposes the MCP URL and authentication metadata as JSON. Neither endpoint issues, accepts, or stores API keys.

Target configuration is changed by editing `TROLLEY_TARGETS_FILE` and restarting Trolley. Protect the file with operating-system permissions such as mode `0600`.

Both `trolley` and `trolley admin issue-key ...` fail before creating or opening the database when `TROLLEY_ADMIN_EMAILS` is missing. The CLI currently listens on `0.0.0.0:8000`; `TROLLEY_PUBLIC_BASE_URL` controls MCP authentication metadata, not the bind port.

## Development

```bash
pytest
ruff check .
ruff format --check .
```

Trolley currently uses Tortoise's startup schema generation instead of migrations. During development, remove `trolley.db` after model changes. Migrations should be introduced before production deployment. Do not remove an operational `trolley.db` without a backup: it contains dynamic Operations and Trolley identity state.

Email OTP, OAuth onboarding, scheduled watches, and multi-process registry synchronization are not implemented yet.
