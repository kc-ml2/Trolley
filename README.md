# Trolley

Trolley lets an MCP client use approved PostgreSQL queries as Tools, without giving it direct access to the database.

```text
MCP client → Trolley Tool → approved Operation → PostgreSQL
```

A server operator connects a PostgreSQL database once. An MCP administrator then creates safe, focused Operations as needed. Regular users only see and run the Operations they are allowed to use.

For example, an administrator can turn a SQL report into a Tool named `monthly_revenue`. An agent can then call:

```text
monthly_revenue(month="2026-08-01")
```

The agent does not receive the database URL, credentials, or SQL definition.

## Why Trolley?

Trolley helps teams turn internal database work into safe Tools for agents. Users can get their work done without database access, while administrators decide what each user can do.

- Let agents do useful work without direct access to databases.
- Turn common internal tasks into safe, reusable Tools.
- Let users ask for new Tools while they work.

## Who does what?

| Role | What they do |
|---|---|
| Server operator | Installs Trolley, edits `trolley.yaml`, protects credentials, and runs local connection checks |
| MCP administrator | Reviews Target schemas and creates, updates, disables, and shares Operations through MCP |
| MCP user or agent | Finds and runs only the Tools allowed for its Trolley account |

This keeps access simple and safe: MCP administrators can build useful database Tools, but they cannot add or change connection credentials through MCP.

## Core concepts

- **Target**: a PostgreSQL database configured by the server operator in `trolley.yaml`.
- **Operation**: an approved SQL statement stored in Trolley and exposed as a dynamic MCP Tool.
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
```

### 2. Configure Trolley

Copy the example and edit `trolley.yaml`:

```bash
cp trolley.example.yaml trolley.yaml
```

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
    url: postgresql://user:password@127.0.0.1:5432/payments
    timeout: 10
```

The `admins.emails` list is required. Target connection details also live in this file, so do not commit `trolley.yaml` to Git.

You can keep the file elsewhere by setting its path:

```bash
TROLLEY_CONFIG_FILE=/etc/trolley/trolley.yaml trolley
```

### 3. Check the PostgreSQL Target

```bash
trolley target list
trolley target check
trolley target test payments-db
```

### 4. Start the server

Start Trolley to initialize its catalog and serve MCP:

```bash
trolley
```

Trolley synchronizes Target names and kinds into its catalog, while credentials remain only in `trolley.yaml`.

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

The document helps the agent prepare the MCP settings without seeing the API key. The user gets a key from an administrator and enters it directly in the MCP client's secret settings or a local `TROLLEY_API_KEY` environment variable. Never paste an API key into an agent conversation.

After connecting, the agent calls `list_operations` to find the Operations available to the user. It then calls `execute` with inputs that match the selected Operation's `input_schema`. The agent can call `list_operations` again when Tools or permissions change.

If no Operation meets the user's need, the agent can ask for permission to save a request with `request_operation`. The request must not contain secrets or sensitive data. The user can check its status with `list_my_operation_requests`.

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

Connection strings, credentials, and other Target settings are never included.

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

Admins always see every active Operation. Other users receive the Tool's name, description, and input schema, but never its SQL definition or direct Target configuration. Tool visibility and execution permission are both checked against current catalog state, so revoking access takes effect without restarting Trolley.

### Request a missing Operation

After checking `list_operations`, a signed-in user can call `request_operation` with a title, description, and reason. The agent must ask the user first and must not include secrets or sensitive data. Users can check their requests with `list_my_operation_requests`.

Administrators review requests with `list_operation_requests`. After creating the requested Operation, an administrator marks the request as `fulfilled` and links the new Operation. They can also mark it as `rejected` and add a note. Request states are `pending`, `fulfilled`, and `rejected`.

### Admin lock

`admins.emails` in `trolley.yaml` is the list of emails allowed to be administrators:

```yaml
admins:
  emails:
    - admin@example.com
    - ops@example.com
```

Admin access requires both conditions:

```text
stored User.role == admin
AND
normalized User.email is in `admins.emails`
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

When SMTP is configured, an administrator can call `invite_user` instead. It creates or reuses an active user, makes an API key, and emails the key with the onboarding URL. An email in `admins.emails` is invited as an admin; any other email is invited as a regular user. The key is not returned through MCP. If the email fails, Trolley disables the new key so the administrator can safely try again.

The first admin still needs a local key from `trolley admin issue-key`. After connecting, that admin can use `invite_user` to email keys to other allowlisted admins.

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

## Runtime state and backups

A typical installation separates runtime state from safe configuration templates:

| Path | Purpose | Commit to Git? |
|---|---|---|
| `trolley.yaml` | Trolley, SMTP, and PostgreSQL Target settings | No |
| `trolley.db` | Users, hashed keys, dynamic Operations, grants, and Execution history | No |
| `trolley.example.yaml` | Safe configuration template | Yes |

Back up `trolley.yaml` and `trolley.db` together when moving a Trolley installation. A catalog backup without `trolley.yaml` preserves Operation definitions but cannot connect them to PostgreSQL; a configuration file without the catalog loses dynamic Tools and Trolley accounts.

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
→ shared PostgreSQL executor
→ Execution audit record
```

For PostgreSQL, argument values are passed through asyncpg parameter binding rather than interpolated into SQL. The database account configured in `trolley.yaml` remains the final authority: use a read-only account or a physical read replica when Operations should only query data.

Target credentials remain in the server-owned Target YAML file. MCP Tool responses do not include connection strings or other Target configuration. Dynamic Operations cannot execute Python or shell code; they are limited to approved PostgreSQL statements.

## Configuration

Trolley reads `trolley.yaml` from the current directory. Set `TROLLEY_CONFIG_FILE` to use a different path.

| Section | Purpose |
|---|---|
| `server.public_base_url` | Public URL used for MCP authentication metadata and onboarding links |
| `catalog.database_url` | Trolley's catalog and execution-history database |
| `admins.emails` | Required list of emails allowed to receive the admin role |
| `targets` | PostgreSQL connections available to Trolley |
| `smtp` | Optional email delivery settings for `invite_user` |

For Google Workspace, add:

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

Use a Google App Password, not the account password. Omit the `smtp` section to disable email delivery. When SMTP is configured, startup checks the connection, TLS, authentication, and `NOOP` without sending a message. A failed check prevents startup.

`GET /onboarding.md` provides public, agent-readable connection instructions, and `GET /.well-known/trolley` provides the MCP URL and authentication details as JSON. Neither endpoint issues, accepts, or stores API keys.

Both `trolley` and `trolley admin issue-key ...` fail before creating or opening the database when `admins.emails` is empty. The CLI listens on `0.0.0.0:8000`; `server.public_base_url` controls public links, not the bind port.

## Development

```bash
pytest
ruff check .
ruff format --check .
```

Trolley currently uses Tortoise's startup schema generation instead of migrations. During development, remove `trolley.db` after model changes. Migrations should be introduced before production deployment. Do not remove an operational `trolley.db` without a backup: it contains dynamic Operations and Trolley identity state.

Email OTP, OAuth onboarding, scheduled watches, and multi-process registry synchronization are not implemented yet.
