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

| Role | Access |
| --- | --- |
| User | Run tools shared with them |
| Developer | Also inspect and query explicitly granted databases |
| Administrator | Manage access and create/share tools |

A database connection is a **Target**. An administrator-published tool is an
**Operation**, such as `get_my_weekly_data`. Developer exploration does not create
new Operations automatically.

## Run your own server

Requires Docker with Compose. From this repository:

```bash
cp -n trolley.docker.example.yaml trolley.yaml
# Set admins.emails in trolley.yaml; update an existing config manually.
docker compose up -d --build
docker compose exec trolley trolley admin issue-key admin@example.com
```

Use your configured administrator email. Enter the printed key in your client's
secret settings. MCP: `http://localhost:8000/mcp/` ·
Onboarding: `http://localhost:8000/onboarding.md`.

Compose includes PostgreSQL and an initially empty, read-only query Target.
**Default passwords are for local development only.** Use HTTPS and change passwords
before remote deployment. On Linux, the config must be readable by container UID/GID
`10001`. Do not run `docker compose down -v` unless you intend to delete stored data.

[Database defaults, deployment, and development →](docs/deployment.md)

## Learn more

- [Create tools and manage access](docs/guide.md#3-create-a-tool-and-share-it-with-a-group)
- [Personal data: identity, ownership, and guarantees](docs/caller-data.md)
- [File downloads](docs/exports.md)
- [Developer access](docs/target-query-design.md)
