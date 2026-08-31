# Trolley

Trolley is an MCP execution gateway that gives AI agents controlled access to PostgreSQL databases and HTTP APIs.

```text
MCP client → Trolley → registered Operation → PostgreSQL / HTTP API
```

Trolley does not run or manage agents, install processes on target servers, or manage resource groups, schedules, and watches.

## Core concepts

- **User**: a human or agent identity authenticated with a Bearer API key.
- **Target**: a PostgreSQL database or HTTP API. Only admins can access Target configuration.
- **Operation**: an allowed SQL statement or HTTP request exposed as a dynamic MCP Tool.
- **Execution**: an Operation invocation, including caller, arguments, result, status, and timestamps.

## Quick start

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
cp targets.example.yaml targets.yaml
chmod 600 targets.yaml
```

Configure Trolley itself in `.env`:

```dotenv
TROLLEY_DATABASE_URL=sqlite://./trolley.db
TROLLEY_PUBLIC_BASE_URL=http://localhost:8000
TROLLEY_ADMIN_EMAILS=admin@example.com
TROLLEY_TARGETS_FILE=./targets.yaml
```

`TROLLEY_ADMIN_EMAILS` is required. Target connections are configured only by the
server operator in `targets.yaml`, not through MCP:

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

Keep this file readable only by the Trolley service account:

```bash
chmod 600 targets.yaml
```

Validate the file and test PostgreSQL connections locally:

```bash
trolley target list
trolley target check
trolley target test litellm-db-replica
```

Start Trolley once to initialize the database. Trolley synchronizes target names
and kinds from the YAML file into its catalog; credentials remain only in the file.

```bash
trolley
```

In another terminal, issue a key locally for an allowlisted admin:

```bash
trolley admin issue-key admin@example.com --name local-admin
```

Endpoints:

```text
MCP:    http://localhost:8000/mcp/
Health: http://localhost:8000/health
```

Connect an MCP client with the issued Bearer key. Administrators can call
`list_targets`, inspect a complete live PostgreSQL schema with `get_target_schema`,
and create Operations. Target creation, deletion, credentials, and connectivity
testing are deliberately not exposed through MCP.

## First PostgreSQL Tool

### 1. Inspect the Target schema

Call the admin System Tool `get_target_schema`:

```json
{"name": "litellm-db-replica"}
```

It returns the complete live schema, including tables, views, columns, primary
keys, and foreign keys. Trolley does not cache or paginate schema results.

### 2. Create an Operation

Call the admin System Tool `create_operation`:

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

The active Operation is immediately exposed under its own MCP Tool name. No
Trolley restart is required.

## Users, keys, and access

All API key secrets are stored as SHA-256 hashes and returned only once when issued.

### Roles and Operation access

- `admin`: manages Users, API keys, Targets, Operations, and grants, and invokes every Operation.
- `user`: accesses Operations according to the Operation visibility, User access mode, and explicit grants.

An Operation has one access level:

- `user`: available to users in `standard` mode.
- `restricted`: available only to explicitly granted users.
- `admin`: available only to admins; a grant cannot override this restriction.

A User has one Operation access mode:

- `standard`: receives `user` Operations plus explicitly granted `restricted` Operations.
- `assigned_only`: receives only explicitly granted non-admin Operations, including a specifically granted `user` Operation.

Admins always see every active Operation. Other users never receive direct Target configuration or SQL definitions. Tool visibility and execution are both checked against the current database state.

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

### Create a user and issue a key

An admin can call `create_user`:

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

The `secret` in the response is shown once. Configure that secret as the user's MCP Bearer token.

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

## System Tools

System Tools are fixed in code and cannot be used as Operation names.

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

## HTTP Targets

Configure an HTTP Target in `targets.yaml`:

```yaml
targets:
  orders-api:
    kind: http
    base_url: https://api.example.com
    timeout: 30
    bearer_token: replace-me
```

Register an Operation:

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

HTTP `bearer_token` credentials are sent as Bearer tokens. GET and DELETE arguments become query parameters; other methods receive a JSON body. HTTP schema inspection and connectivity testing are not currently implemented.

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
→ connector execution
→ Execution audit record
```

Target credentials remain in the server-owned targets YAML file. MCP Tool responses do not include connection strings, tokens, headers, or other target configuration.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TROLLEY_DATABASE_URL` | `sqlite://./trolley.db` | Trolley's catalog and execution-history database |
| `TROLLEY_PUBLIC_BASE_URL` | `http://localhost:8000` | Public base URL used by MCP authentication metadata |
| `TROLLEY_TARGETS_FILE` | `targets.yaml` | Server-owned YAML file containing Target configuration and credentials |
| `TROLLEY_ADMIN_EMAILS` | **required** | Comma-separated admin eligibility allowlist; also used to create admin Users when no active allowlisted admin exists |

Target configuration is changed by editing `TROLLEY_TARGETS_FILE` and restarting Trolley. Protect the file with operating-system permissions such as mode `0600`.

Both `trolley` and `trolley admin issue-key ...` fail before creating or opening the database when `TROLLEY_ADMIN_EMAILS` is missing. The CLI currently listens on `0.0.0.0:8000`; `TROLLEY_PUBLIC_BASE_URL` controls MCP authentication metadata, not the bind port.

## Development

```bash
pytest
ruff check .
ruff format --check .
```

Trolley currently uses Tortoise's startup schema generation instead of migrations. During development, remove `trolley.db` after model changes, including this release's `User.operation_access` and `OperationGrant` additions. Migrations should be introduced before production deployment.

Email OTP, OAuth onboarding, scheduled watches, and multi-process registry synchronization are not implemented yet.
