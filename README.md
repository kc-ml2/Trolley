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
```

Configure administrator emails and a PostgreSQL Target credential in `.env`:

```dotenv
TROLLEY_DATABASE_URL=sqlite://./trolley.db
TROLLEY_PUBLIC_BASE_URL=http://localhost:8000
TROLLEY_ADMIN_EMAILS=admin@example.com

PAYMENTS_DATABASE_URL=postgresql://user:password@localhost:5432/payments
```

Start Trolley once to initialize the database. When no active allowlisted admin exists, Trolley creates admin Users for the configured emails, but it never generates keys automatically.

```bash
trolley
```

In another terminal, issue a key locally for an allowlisted admin:

```bash
trolley admin issue-key admin@example.com --name local-admin
```

The command prints the API key once. Restarting Trolley or running the command again creates another key; it does not reveal an existing one.

Endpoints:

```text
MCP:    http://localhost:8000/mcp/
Health: http://localhost:8000/health
```

Connect an MCP client using the issued key as a Bearer token. A typical client configuration looks like:

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

The exact configuration format depends on the MCP client. The resulting HTTP header must be:

```http
Authorization: Bearer sk-trolley-issued-key
```

## First PostgreSQL Tool

### 1. Register a Target

Call the admin System Tool `create_target`:

```json
{
  "name": "payments-db",
  "kind": "postgresql",
  "configuration": {
    "timeout": 10
  },
  "secret_env": "PAYMENTS_DATABASE_URL"
}
```

Trolley stores the environment variable name, not the PostgreSQL connection string.

### 2. Test the connection

Call the admin System Tool `test_target_connection`:

```json
{
  "name": "payments-db"
}
```

Trolley opens a connection, runs `SELECT 1`, and closes it. A successful response contains no credential:

```json
{
  "target": "payments-db",
  "kind": "postgresql",
  "status": "connected",
  "latency_ms": 12.5,
  "server_version": "16.3"
}
```

Target registration and connection testing are separate, so a temporarily unavailable database can still be configured.

### 3. Create an Operation

Call the admin System Tool `create_operation`:

```json
{
  "name": "monthly_revenue",
  "target_name": "payments-db",
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
      "month": {
        "type": "string",
        "description": "First day of the month in YYYY-MM-DD format",
        "pattern": "^\\d{4}-\\d{2}-01$"
      }
    },
    "required": ["month"],
    "additionalProperties": false
  }
}
```

PostgreSQL SQL uses positional placeholders such as `$1`. The ordered `definition.parameters` list maps Tool arguments to those placeholders and must match `input_schema.required`.

### 4. Invoke the dynamic Tool

The active Operation is immediately exposed under its own MCP Tool name:

```text
monthly_revenue(month="2025-08-01")
```

No Trolley restart is required. A client may need to refresh `tools/list` before the new Tool appears.

The compatibility System Tool `execute` can also invoke it:

```json
{
  "name": "monthly_revenue",
  "arguments": {
    "month": "2025-08-01"
  }
}
```

Set `definition.fetch` to `false` for insert, update, and delete statements.

## Users, keys, and access

All API key secrets are stored as SHA-256 hashes and returned only once when issued.

### Roles

- `admin`: manages Users, API keys, Targets, and Operations, and invokes every Operation.
- `user`: lists and invokes only Operations with `access: "user"`.

Users never receive direct Target configuration or SQL definitions. An Operation with `access: "admin"` is hidden from a user's Tool list and checked again immediately before execution.

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

## System Tools

System Tools are fixed in code and cannot be used as Operation names.

### Admin-only

- `list_users`
- `create_user`
- `list_api_keys`
- `create_api_key`
- `list_targets`
- `create_target`
- `test_target_connection`
- `create_operation`
- `update_operation`
- `disable_operation`
- `reload_tools`

### Authenticated users

- `list_operations`: returns only Operations visible to the caller.
- `execute`: invokes a visible Operation by name.

Active Operations are additional dynamic Tools. `update_operation` reloads a Tool in-process, `disable_operation` removes it, and `reload_tools` synchronizes the full registry with the database.

## HTTP Targets

Register an HTTP Target:

```json
{
  "name": "orders-api",
  "kind": "http",
  "configuration": {
    "base_url": "https://api.example.com",
    "timeout": 30
  },
  "secret_env": "ORDERS_API_TOKEN"
}
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

HTTP credentials are currently sent as Bearer tokens. GET and DELETE arguments become query parameters; other methods receive a JSON body. `test_target_connection` currently supports PostgreSQL only.

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
→ current Operation and Target state
→ Operation access level
→ JSON Schema validation
→ connector execution
→ Execution audit record
```

Target credentials remain in environment variables. Tool responses do not include connection strings or credential values.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `TROLLEY_DATABASE_URL` | `sqlite://./trolley.db` | Trolley's catalog and execution-history database |
| `TROLLEY_PUBLIC_BASE_URL` | `http://localhost:8000` | Public base URL used by MCP authentication metadata |
| `TROLLEY_ADMIN_EMAILS` | empty | Comma-separated admin eligibility allowlist; also used to create admin Users when no active allowlisted admin exists |

Target secrets use administrator-selected environment variable names such as `PAYMENTS_DATABASE_URL` and `ORDERS_API_TOKEN`.

## Development

```bash
pytest
ruff check .
ruff format --check .
```

Trolley currently uses Tortoise's startup schema generation instead of migrations. During development, remove `trolley.db` after model changes. Migrations should be introduced before production deployment.

Email OTP, OAuth onboarding, scheduled watches, and multi-process registry synchronization are not implemented yet.
