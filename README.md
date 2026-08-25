# Pantry

Pantry is a small control plane for Trolleys.

It manages:

- Human and Trolley accounts
- API keys
- OpenAI-compatible Providers and their models
- Trolleys, Resource Groups, and Resources
- Agent placement through opaque allocation-mode matching
- Provider credentials referenced by environment variable

Pantry does not proxy LLM requests. Trolley Agents call their assigned Provider directly.

## Run Pantry

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn pantry.main:app --reload --port 8000
```

Create the first admin on an empty database:

```dotenv
PANTRY_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
PANTRY_BOOTSTRAP_ADMIN_API_KEY=sk-pantry-change-me
```

Admin MCP:

```text
http://localhost:8000/mcp/
```

Health check:

```text
GET /health
```

## Provider

A Provider is an OpenAI-compatible API base URL. LiteLLM can be the initial Provider while models are migrated gradually.

```text
Provider
  name: litellm
  base_url: http://litellm:4000/v1

Model
  alias: hulk
  upstream_model: hulk
  provider: litellm
```

Provider secrets stay outside the database. A Credential stores only an environment variable name.

```dotenv
LITELLM_API_KEY=sk-litellm-...
```

```text
Credential
  name: litellm-key
  secret_env: LITELLM_API_KEY
```

## Trolley and Resources

A Trolley is an Agent runtime connected to Pantry. It can manage one or more Resource Groups, and each Group contains Resources.

```text
Trolley
  └── ResourceGroup
        └── Resource
```

Create a Trolley through Admin MCP:

```text
create_trolley
  name: gpu-01
```

The response contains a Trolley API key once. Configure the target server:

```dotenv
PANTRY_URL=https://pantry.example.com
PANTRY_API_KEY=sk-pantry-...
TROLLEY_HEARTBEAT_INTERVAL=60
```

Install and run:

```bash
python -m venv .venv
source .venv/bin/activate
pip install .
trolley run
```

Trolley connects to Pantry over:

```text
WS /trolley/connect
```

Use `wss://` in production. The Trolley authenticates with its Pantry API key in the `Authorization` header.

## Resource Groups, Resources, and Agents

A Resource Group has one opaque `allocation_mode`. Pantry stores and compares this value but does not interpret it.

```text
create_resource_group
  trolley_name: gpu-01
  name: baremetal
  allocation_mode: time_window
  configuration:
    minimum_minutes: 30

create_resource
  resource_group: baremetal
  name: server-01
  kind: host
  attributes:
    location: lab-a
```

Resource `kind`, Group `configuration`, and Resource `attributes` are also opaque Agent-owned data. They are not restricted to Pantry enums.

Register an Agent with the mode it supports. Its model is optional.

```text
create_agent
  name: reservation
  allocation_mode: time_window
  model_alias: hulk
  configuration:
    interval: 60
```

A second initial Agent can be registered without changing Pantry Core:

```text
create_agent
  name: container_execution
  allocation_mode: task_lease
  configuration:
    runtime: docker
```

Pantry performs only generic matching:

```text
ResourceGroup.allocation_mode == Agent.allocation_mode
```

Pantry Core and Trolley do not implement reservation, lease, task, GPU, or container semantics. Those belong to the matched Agents. An Agent without a model receives configuration without a Provider secret; an Agent with a model receives only its required Provider configuration. Inactive Resource Groups and Resources remain stored but are omitted from Trolley configuration.

On connection:

1. Trolley sends `hello` with `runtime_info` and current Agent statuses.
2. Pantry loads active Resource Groups and Resources attached to that Trolley.
3. Pantry matches active Agents using the opaque `allocation_mode` string.
4. Pantry sends Group, Resource, and Agent data plus only required Provider keys.
5. Trolley keeps the configuration in memory only.
6. Trolley sends bounded `metrics` and opaque Agent status reports; Pantry revalidates the Trolley API key and replies with `heartbeat_ack`.

The reported Agent list is runtime status only and is not an Agent-matching condition. Configuration is currently sent once after `hello`; Pantry catalog changes take effect when the Trolley reconnects. Disabling the Trolley, its account, or the API key closes the connection on its next message.

The initial control protocol is intentionally small:

```text
Trolley -> hello
Pantry  -> configuration
Trolley -> heartbeat
Pantry  -> heartbeat_ack
```

Trolley messages are limited to 64 KiB and at most 100 Agent status entries. Trolley is intentionally lazy: it does not proactively publish Agent state or execute remote commands. A future command protocol will let Pantry persist a command and its delivery, processing, and response status before asking Trolley to act.

Logs, high-frequency time-series metrics, reservations, tasks, leases, and other authoritative Agent data remain Agent-owned. Agents may use their own database or external services; Pantry does not manage them.

Agent state storage, command execution, plugin execution, reservations, leases, containers, remote tasks, and one-line installation are not implemented in Pantry Core.

## Configuration

Pantry:

```dotenv
PANTRY_DATABASE_URL=sqlite://./pantry.db
PANTRY_PUBLIC_BASE_URL=http://localhost:8000
PANTRY_BOOTSTRAP_ADMIN_EMAIL=
PANTRY_BOOTSTRAP_ADMIN_API_KEY=
```

Trolley:

```dotenv
PANTRY_URL=http://localhost:8000
PANTRY_API_KEY=sk-pantry-replace-me
TROLLEY_HEARTBEAT_INTERVAL=60
```

## Development

```bash
pytest
ruff check .
ruff format --check .
```

The project currently creates its Tortoise schema at startup with `generate_schemas=True`. Use a fresh database after model changes; migrations will be introduced before deployment.
