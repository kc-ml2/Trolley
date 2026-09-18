# Trolley

**Share your team's data tools through an AI client, without sharing database credentials.**

Trolley is an MCP server for PostgreSQL exploration and administrator-published
Operations. Bring an MCP-compatible AI client; Trolley authenticates users, checks
access, and runs approved queries with bounded results.

## Access model

```text
User → Group → Target → all active Operations on that Target
```

A **Target** is a configured database connection. An **Operation** is a query
or structured caller-scoped definition published as a tool.

| Role | Run Operations | Inspect schema / read-only SQL | Publish Operations |
| --- | --- | --- | --- |
| `user` | Group Targets | No | No |
| `developer` | Group Targets | Group Targets | No |
| `admin` | Group Targets | Group Targets | Group Targets |

There is no global administrator bypass, direct user Target grant, or per-Operation
permission. Creating an Operation exposes it to all members of all groups using
that Target. Split Targets and DB roles/views when access boundaries differ.

`caller` enforces authenticated ownership; `shared` executes administrator-approved
SQL without automatic personal filtering. Direct SQL does not inherit caller filters.
Administrators must verify ownership mappings and safe database privileges.

## Server operators

Docker Compose runs Trolley on **127.0.0.1:7500** and PostgreSQL for its private
catalog. Configure credentials and database Targets using the
[deployment guide](docs/deployment.md), then:

```bash
docker compose up -d --build
docker compose exec trolley trolley operator add-user
```

The interactive wizard asks for email, role, group, new-group Targets, and final
confirmation. No initial users or groups are created automatically. Identity,
group access and key issuance are CLI-only responsibilities, not MCP tools.
See [operator commands and wizard](docs/operator-wizard.md).

Two private configuration files are required: `.trolley-postgres.env` initializes
Compose's catalog PostgreSQL; `trolley.yaml` configures Trolley's DB connections,
public URL and optional SMTP. They use the same catalog password. Neither belongs
in Git. See [configuration files](docs/deployment.md#configuration-files).

## Invited users

1. Give your agent the onboarding URL from the invitation.
2. Enter the emailed API key privately in the client's authentication settings.
3. Reconnect and ask: **“Trolley, what can you do for me right now?”**

The onboarding guide explains what to do if your client has no MCP integration.
Sharing an API key shares its owner's access. File-output Operations provide
an authenticated JSONL.gz download rather than inline rows.

## Documentation

- [Usage and publishing](docs/guide.md)
- [Personal-data guarantees](docs/caller-data.md)
- [Structured caller aggregates](docs/caller-aggregates.md)
- [Target data notes](docs/data-notes.md)
- [File downloads](docs/exports.md)
- [한국어 빠른 시작](docs/quickstart-ko.md)

## Development

```bash
pip install -e '.[dev]'
pytest
ruff check .
ruff format --check .
```

Use a disposable PostgreSQL instance for integration tests:
`PYTHON=venv/bin/python ./scripts/test-postgres-integration.sh`.
Single worker only. There are no versioned catalog migrations, automatic audit
retention or key-revocation management commands yet. Back up before upgrades.
