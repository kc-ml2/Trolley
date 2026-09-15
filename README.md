# Trolley

**Use your team's data through your AI client—without database credentials.**

Ask your agent to run tools your administrator has shared with you:

> Show me my usage this week.
>
> Download my weekly data.

Developers can also explore databases and run read-only SQL when granted access.
Trolley is an MCP server, not a chat app; bring an MCP-compatible AI client.

## Connect and ask

If your administrator has given you access:

1. Give your agent the **onboarding URL** from your invitation and ask it to help
   connect to Trolley.
2. Enter your **API key privately** in the client's authentication settings, not in
   chat. Sharing a key shares your account's access.
3. Reconnect and ask: **“Trolley, what can you do for me right now?”**

Your agent discovers the tools available to you. Personal-data tools use your
account identity automatically—no email input needed. File tools provide an
authenticated download link when ready. If a tool is missing, contact your administrator.

[Connection help →](docs/guide.md#2-connect-your-mcp-client)

## Who can do what?

| Role | Inspect schema / run direct SQL | Create or modify Operations | Run Operations |
| --- | --- | --- | --- |
| `user` | No | No | Public or explicitly granted Operations* |
| `developer` | Only Targets granted to the user or their groups | No | Public or explicitly granted Operations* |
| `admin` | All active Targets | Yes; also manages access | All active Operations |

\* Users configured as `assigned_only` need explicit grants even for public Operations.

A database connection is a **Target**. An administrator-published tool is an
**Operation**, such as `my_usage`. These permissions are separate:

- **Target access** allows schema inspection and direct, read-only SQL through
  `query_target`. It does not grant permission to publish Operations, and exploration
  does not create Operations automatically.
- **Operation access** allows execution of an approved tool with declared inputs;
  it does not require Target access or let the caller change the SQL.
- **Data scope** controls whose data is returned. `caller` enforces authenticated
  ownership, including for administrators. `shared` has no automatic caller filter.
  `restricted` controls who may execute an Operation, not which rows it returns.

**Direct SQL does not inherit a caller Operation's personal-data filter.** Its reach
is determined by the Target's database credentials and database-side permissions.
Grant developer access only to people trusted to explore that data.

For example, a teammate who only needs personal usage reports should have the `user`
role and access to a `restricted`, `caller`-scoped `my_usage` Operation—**no Target
access is needed**. API keys inherit their owning user's permissions; sharing a key
shares that user's access.

## Run your own server

Requires Docker with Compose. From this repository:

```bash
cp -n trolley.docker.example.yaml trolley.yaml
# Configure catalog credentials, admins and Targets using docs/deployment.md.
# Create the private .trolley-postgres.env file described there.
docker compose up -d --build
docker compose exec trolley trolley admin issue-key admin@example.com
```

Use your configured administrator email. Enter the printed key in your client's
secret settings. MCP: `http://localhost:7500/mcp/` ·
Onboarding: `http://localhost:7500/onboarding.md`.

Compose includes PostgreSQL for the catalog; configure your existing query Targets
separately. Set a random catalog password before first startup and use HTTPS remotely. On Linux, the config must be readable by container UID/GID
`10001`. Do not run `docker compose down -v` unless you intend to delete stored data.

[Database defaults, deployment, and development →](docs/deployment.md)

## Learn more

- [Create tools and manage access](docs/guide.md#3-create-a-tool-and-share-it-with-a-group)
- [Personal data: identity, ownership, and guarantees](docs/caller-data.md)
- [Caller ownership mapping and usage aggregates](docs/caller-aggregates.md)
- [한국어 빠른 시작](docs/quickstart-ko.md)
- [File downloads](docs/exports.md)
- [Developer access](docs/target-query-design.md)
