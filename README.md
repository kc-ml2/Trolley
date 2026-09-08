# Trolley

**Turn approved database queries into tools your team can use through an AI client.**

With Trolley, an administrator creates a tool, shares it with a group, and invites
people by email. Users can then ask their agent to run it—without receiving database
credentials or writing SQL.

For example, once the corresponding tools have been created:

> Show me my LLM usage this month.
>
> Get revenue for August 2026.

```text
User → AI client → Trolley → Approved query → PostgreSQL
```

Trolley is an MCP server, not a chat application. Bring an MCP-compatible AI client;
Trolley provides the tools and controls who can run them. It currently supports
PostgreSQL databases.

## Invited to Trolley? Start here

You do not need to install the server.

1. **Open your invitation email.** It contains an onboarding URL and an API key.
2. **Give your agent the onboarding URL**, using the address from your invitation:

   > Read this page and help me connect to Trolley:
   > https://trolley.example.com/onboarding.md
   > I'll enter my API key directly in the client's settings when needed.

3. **Enter your key privately** in your MCP client's secret or authentication settings.
   Do not paste it into an AI conversation. Your client may require manual MCP setup.
4. **Reconnect your client and ask:**

   > Trolley, what can you do for me right now?
   > Explain my available capabilities and help me get started.

The agent calls `get_my_capabilities` to learn your role and suggest next steps.
Then ask it to perform an available task. If a suitable tool is missing, it can ask
for your approval before submitting a request to an administrator.

[Connection details and manual setup →](docs/guide.md#2-connect-your-mcp-client)

## Administrators: create once, share with your team

A saved SQL statement, inputs, and access policy form an **Operation**, exposed as an
MCP tool. A configured PostgreSQL database is called a **Target**.

After connecting as an administrator, you can ask your agent:

> List the configured Targets and inspect the schema of the database I choose.
> Help me create a monthly revenue Operation. Propose the SQL and inputs for review,
> make it restricted, and share it with the finance group.

The workflow is:

```text
Inspect schema → Review SQL and access → Create Operation → Grant to group → Invite users
```

You can do this through MCP without generating code or restarting the server.
An empty `list_operations` result just means no accessible active Operations are listed;
it does not mean you lack administrator access. Use `get_my_capabilities` to get started.

### Tools that show only the caller's data

An Operation can receive the authenticated user's email from Trolley rather than
from client input. This lets an administrator build a shared “my usage” tool that
filters by an email column or a trusted key tag.

The administrator must approve the mapping and SQL. Email injection does not add
row filtering automatically, and group membership alone does not isolate rows.

[Create and share an Operation →](docs/guide.md#3-create-a-tool-and-share-it-with-a-group)
· [Caller email binding →](docs/guide.md#caller-specific-operations)

## Run your own server

Python **3.11+** and a PostgreSQL database to query are required. From a checkout of
this repository:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
cp trolley.example.yaml trolley.yaml
```

Edit `trolley.yaml` with your server URL, administrator emails, and database connection:

```yaml
server:
  public_base_url: http://localhost:8000
catalog:
  database_url: sqlite://./trolley.db
admins:
  emails:
    - admin@example.com
targets:
  reporting-db:
    kind: postgresql
    url: postgresql://reporting:password@127.0.0.1:5432/my_database
```

The **catalog** stores Trolley accounts, permissions, Operations, and execution history.
The **Target** is the database those Operations query.

Check the connection and start Trolley:

```bash
trolley target check
trolley
```

In another terminal, using the same environment and working directory, issue the
first administrator's key:

```bash
trolley admin issue-key admin@example.com --name initial-admin
```

Store the printed key in your MCP client's secret settings. Connect using
`http://localhost:8000/onboarding.md` and ask the first question above.

With [SMTP configured](docs/guide.md#email-configuration), you can instead email the
key and onboarding link:

```bash
trolley setup admin@example.com
```

`setup` sends invitations; it does not install a service. Each run issues a new key
and leaves existing keys valid.

## Before sharing access

- **Use HTTPS for remote access.** The CLI listens on `0.0.0.0:8000`;
  `public_base_url` sets public links, not the bind address. Run one server process.
- **Approve SQL and set access explicitly.** The default is `public` for standard
  signed-in users. Use `restricted` for granted users/groups or `admin` for admins only.
- **Limit database privileges.** Use a read-only PostgreSQL account for reporting.
  Trolley trusts administrators to approve queries; it does not certify SQL as safe.
- **Protect keys and backups.** Keep `trolley.yaml` and the catalog private. Execution
  arguments and results are stored in the catalog and may contain sensitive data.
- **Plan for current limitations.** Keys have no expiry or built-in revocation command.
  Catalog schema changes have no versioned migrations; back up before upgrading.

## Documentation

| Need | Guide |
|---|---|
| Connect an MCP client | [Onboarding and manual setup](docs/guide.md#2-connect-your-mcp-client) |
| Create tools and invite users | [Administrator walkthrough](docs/guide.md#3-create-a-tool-and-share-it-with-a-group) |
| Manage groups and permissions | [Access policies](docs/guide.md#managing-access) |
| Filter by caller email | [Caller-specific Operations](docs/guide.md#caller-specific-operations) |
| Handle large results | [Limits and pagination](docs/guide.md#query-results-and-large-logs) |
| Send invitations | [SMTP configuration](docs/guide.md#email-configuration) |
| Troubleshoot or upgrade | [Troubleshooting](docs/guide.md#troubleshooting) · [Backups](docs/guide.md#backups-and-upgrades) |

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
```

With Docker running, test against a disposable PostgreSQL instance:

```bash
./scripts/test-postgres-integration.sh
```

Without an explicitly configured test database, ordinary `pytest` runs skip the
PostgreSQL integration test. See the [testing guide](docs/guide.md#development).
