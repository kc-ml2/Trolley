# Deployment and local development

[← README](../README.md)

## Quick start

Requires Docker with Compose. From this repository:

```bash
cp -n trolley.docker.example.yaml trolley.yaml
# Generate a password, e.g. openssl rand -hex 32; store it privately.
# Create .trolley-postgres.env as below, then edit trolley.yaml.
docker compose up -d --build
docker compose exec trolley trolley admin issue-key admin@example.com
```

Before starting, create `.trolley-postgres.env` (mode `0600`):

```dotenv
POSTGRES_DB=trolley
POSTGRES_USER=trolley
POSTGRES_PASSWORD=REPLACE_WITH_RANDOM_PASSWORD
```

Set the same password in `trolley.yaml`'s `catalog.database_url`:
`postgres://trolley:REPLACE_WITH_RANDOM_PASSWORD@postgres:5432/trolley`.
Use a URL-safe password (hex is suitable); YAML does not interpolate environment
variables. Set `admins.emails` and your actual PostgreSQL `targets`. No sample
query Target is provisioned. An empty `targets: {}` is allowed.

The config must be readable by container UID/GID `10001`. On Linux, set group
10001 and mode 0640, or add a trusted supplementary group via an ignored
`compose.override.yaml` and give that group read access. Do not make it world-readable.
The config is mounted read-only at `/etc/trolley/trolley.yaml`.

Use an allowlisted administrator email to issue the key. Enter the printed key
privately in the client's authentication settings, never in chat. Alternatively,
with SMTP configured, run `docker compose exec trolley trolley setup admin@example.com`
to email it. Every issuance creates a new key; previous keys remain valid.

- MCP: `http://localhost:7500/mcp/`
- Onboarding: `http://localhost:7500/onboarding.md`
- Authentication: `Authorization: Bearer <your-api-key>`

Reconnect and ask: **“Trolley, what can you do for me right now?”**

## Catalog versus query Targets

Compose's PostgreSQL stores accounts, permissions, Operations and execution history.
Its service hostname is `postgres`; no PostgreSQL port is exposed on the host.
The simple setup uses the provisioning account for the catalog. For stricter
production separation, provision a dedicated catalog role and update its URL.
Never configure catalog credentials as an end-user query Target.

Targets connect to your existing databases with least-privilege credentials.
Inside a container, `127.0.0.1` refers to that container, not the host. For other
Compose databases, attach Trolley to their external networks using a local override
and use unique DB service/container names. Host-only loopback bindings are not
reachable merely by substituting `host.docker.internal`.

Example local `compose.override.yaml` (excluded from Git):

```yaml
services:
  trolley:
    networks: [default, reporting]
networks:
  reporting:
    external: true
    name: your-existing-reporting-network
```

PostgreSQL initialization only applies to an empty volume. Changing the env file
alone does not rotate an existing password; use `ALTER ROLE` and update the catalog
URL. Legacy `docker/postgres/init.sql` is not mounted by the current Compose setup.

## Personal data and files

Every Operation declares `data_scope`: `caller` compiles structured ownership
filters, including [mapped aggregates](caller-aggregates.md); `shared` runs approved
SQL without automatic caller isolation. Administrators also get only their own data
through caller Operations. Review ownership mappings; sharing a key shares access.
See [the personal data contract](caller-data.md).

Fixed `output` is `inline` or `file`. File Operations generate JSONL.gz; poll
`get_execution(execution_id)`. Direct developer SQL requires Target grants and is
read-only, but has no automatic caller filter.

## Operate

```bash
docker compose logs --tail=100 -f trolley
docker compose exec trolley trolley target check
docker compose restart trolley                 # Reload config
docker compose up -d --build --no-deps trolley  # Deploy code, preserve DB
docker compose down                            # Stop, preserve volumes
```

- Docker runs one Uvicorn worker on `0.0.0.0:7500`, published only at
  `127.0.0.1:7500`. Use an HTTPS reverse proxy to that port for remote access and
  set `server.public_base_url` to the public HTTPS URL.
- The image entrypoint runs Uvicorn; use `docker compose exec trolley trolley ...`
  for CLI actions, not arguments appended to the image entrypoint.
- Config is read-only, Trolley is non-root, and data persists in `postgres-data`
  and `trolley-data`. Never use `docker compose down -v` unless deleting data is intended.
- Keep `.env`, `.trolley-postgres.env`, `trolley.yaml`, overrides and backups private.
  Back up PostgreSQL and config separately. Schema generation does not migrate
  existing tables; review changes before upgrading. Multiple workers are unsupported.

## Local development

Python 3.11+ and a PostgreSQL Target are required without Docker:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp -n trolley.example.yaml trolley.yaml
# Configure local paths/DB addresses; this differs from Docker configuration.
trolley
```

The standalone CLI still listens on port **8000** and defaults to a SQLite catalog;
Docker uses port **7500** and PostgreSQL. Run CLI commands with the same config and
working directory as the intended server.

Run `pytest`, `ruff check .`, and `ruff format --check .`. PostgreSQL integration
tests require a disposable database; see `scripts/test-postgres-integration.sh`.
