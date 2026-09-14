# Deployment and local development

[← README](../README.md)

## Quick start

Requires Docker with Compose. From this repository:

```bash
cp -n trolley.docker.example.yaml trolley.yaml
# Edit admins.emails if needed. If trolley.yaml already exists, update it manually.
docker compose up -d --build
docker compose exec trolley trolley admin issue-key admin@example.com
```

Use an email listed in `admins.emails`. Enter the printed key **privately in your
MCP client's authentication settings**, never in chat. Each issuance creates a new key.

- **MCP:** `http://localhost:8000/mcp/`
- **Authentication:** `Authorization: Bearer <your-api-key>`
- **Agent onboarding:** `http://localhost:8000/onboarding.md`

Then ask: **“Trolley, what can you do for me right now?”**

The config file must be readable by container UID/GID `10001`; on Linux, provision
appropriate group access (for example, GID 10001 and mode 0640).

## Included PostgreSQL

Compose starts PostgreSQL and configures these **local-development defaults**:

| Purpose | Database | Account | Password |
| --- | --- | --- | --- |
| PostgreSQL provisioning | `trolley` | `trolley` | `trolley_local_password` |
| Trolley catalog | `trolley` | `trolley_catalog` | `trolley_catalog_password` |
| Default query Target | `trolley_data` | `trolley_reader` | `trolley_reader_password` |

The catalog stores accounts, permissions, Operations, and history. The default
Target uses a separate, initially empty database and a read-only account that
cannot connect to the catalog. PostgreSQL is not exposed on a host port.

Create/load data using the provisioning account:

```bash
docker compose exec postgres psql -U trolley -d trolley_data
```

Tables created by `trolley` in the `public` schema automatically grant SELECT to
`trolley_reader`. Additional owners/schemas require explicit grants. Add other DB
connections under `targets` in `trolley.yaml`; the Compose DB hostname is `postgres`.

**Change all default passwords before remote deployment.** Initial credentials are
in `compose.yaml`, `docker/postgres/init.sql`, and `trolley.yaml`. Initialization runs
only on an empty PostgreSQL volume: editing these files does not rotate passwords
in an existing DB. Use `ALTER ROLE` and update configuration for existing deployments.
YAML configuration does not interpolate `${VARIABLE}` placeholders.

## Personal data and files

Every Operation must declare its data scope:

- **`caller`:** structured source + ownership column. Trolley generates a mandatory
  filter using the API key owner's account email. Callers cannot supply another
  identity; administrators also see their own rows through this Operation.
- **`shared`:** administrator-approved SQL whose results are shared with authorized
  Operation callers. It does not provide per-user row isolation.

The administrator must verify source ownership and account-to-data email mappings.
Sharing a key shares that account's access. See [the personal data contract](docs/caller-data.md).

An Operation's fixed `output` is either `inline` or `file`. A file Operation creates
a JSONL.gz download when called; poll `get_execution(execution_id)` for completion.
Only administrators publish Operations. Developer SQL is read-only and requires
Target grants; it does not automatically isolate data by caller.

## Operate

```bash
docker compose logs --tail=100 -f trolley
docker compose exec trolley trolley target check
docker compose restart trolley       # Reload configuration
docker compose up -d --build         # Rebuild after code changes
docker compose down                  # Stop without deleting volumes
```

- Trolley runs non-root; configuration is read-only. PostgreSQL data and generated
  files persist in `postgres-data` and `trolley-data` volumes.
- **Do not use `docker compose down -v` unless you intend to delete stored data.**
- For remote use, put an HTTPS reverse proxy in front of the localhost-bound port
  and set `server.public_base_url` accordingly. Run one Trolley instance.
- Protect configuration, keys, audit data, and backups. Back up PostgreSQL with its
  supported backup tools, and preserve configuration separately. Catalog migrations
  are not versioned; review schema changes before upgrading.

## Local development

Python 3.11+ and a PostgreSQL Target are required without Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp -n trolley.example.yaml trolley.yaml
# Configure trolley.yaml for your local environment.
trolley
```

Run `pytest`, `ruff check .`, and `ruff format --check .`. PostgreSQL integration
tests require a disposable database; see `scripts/test-postgres-integration.sh`.

