# Developer exploration and administrator-published Operations

## Product model

Trolley provides two interfaces over configured PostgreSQL connections:

- Developers explore granted Targets by inspecting schemas and executing SQL.
- Users execute administrator-published Operations with declared inputs.

Only system administrators create, modify, disable, and share Operations.
Developer exploration never automatically creates an Operation or an MCP tool.
Treat this as a new service design: legacy migrations are not a requirement.
Existing local or deployed databases must not be deleted implicitly.

| Role | Capabilities |
| --- | --- |
| Administrator | Manage users/groups, configure Target connections, grant Target access, explore all active Targets, publish/share Operations |
| Developer | Inspect/query explicitly granted Targets; run accessible Operations |
| User | Run accessible Operations; no direct schema or SQL access |

A developer role is not a grant to every Target. A Target grant does not confer a
developer role or permission to publish Operations. Group Target grants only
become usable by developer members. Administrators have access to all active,
configured Targets. Existing Operation access rules remain independent.

## Workflow

```text
Administrator → Configure restricted DB connection → Assign developer role
              → Grant Target access to developer or group
Developer     → List Targets → Inspect schema → Execute ad-hoc SQL
              → Send useful SQL and its purpose to administrator if needed
Administrator → Review SQL, inputs and access → Publish/share Operation
User          → Discover Operation → Execute with declared inputs
```

Operation publication is curation of official tools, not a side effect of query
execution. No developer draft/approval subsystem is required initially. Existing
Contact administrators outside Trolley for missing tools. There is no built-in
Operation request workflow or manual reload tool; tool updates refresh automatically.

## Security boundaries

Database administrators provision appropriate roles, views, or separate databases.
The DB enforces data privileges; Trolley does not implement table/column/row ACLs
for free SQL. Users sharing a Target share its DB identity and privileges. Caller
identity is not automatically propagated to DB RLS policies.

Trolley checks Target access on listing, schema inspection, and query execution.
Only active developers with direct/group grants, or active admins, can explore.
Credentials stay on the server. Role/Target grants never grant Operation creation
or sharing. Ordinary users need Operation access, not Target access, to run an
approved query. Caller Operations require structured ownership definitions and server-generated filters;
they do not imply isolation for developer SQL. Personal-data Operations should use
structured caller ownership, not a public input selecting another person's email.
Administrators use direct Target queries for cross-user access.

Free SQL is initially read-only: use restricted database credentials plus read-only
transactions. SELECT/function privileges must also be provisioned appropriately;
SQL text inspection alone is not a security boundary. Agents must not receive
superuser connections. There is no persistent agent-controlled database session.

## Implemented interface

- `list_targets()` — accessible active, configured Targets.
- `get_target_schema(name)` — live schema using that Target's DB identity.
- `query_target(name, sql, params?)` — one read-only statement; positional PostgreSQL
  `$1`, `$2`, ... placeholders map to the params list.
- `set_user_role(email, role)` — administrator-only role assignment. Existing admin
  accounts are protected from modification by this tool; admin assignment still
  requires the configured admin email allowlist.
- `set_target_access(name, allowed, email? , group_name?)` — administrator-only
  direct/group grant or revocation; exactly one principal required.
- `list_target_grants()` — administrator-only grant discovery.

Query execution uses existing connection/query timeouts and row/byte limits, adds
read-only transactions and a statement timeout, and caps simultaneous ad-hoc
queries at four per process. Prepared cursors accept a single statement. Limit
violations fail the call rather than returning silent partial results. Narrow the
query; direct-query pagination and export are not implemented.

`QueryExecution` records caller/key IDs, Target, SQL, status, and timestamps without
storing result bodies or parameter values. SQL literals may contain sensitive data:
protect the catalog and establish an appropriate retention policy before deployment.
Client-facing direct-query/schema errors omit DB diagnostics and credentials.

## Existing features retained

Operation models, permissions, dynamic tools, caller bindings, pagination,
and file generation remain. Operation management and grants remain administrator-only.
Administrators set `definition.output` to `inline` (default) or `file`. File Operations
such as `get_my_weekly_data` start file generation when invoked; callers cannot choose
the output mode. There is no separate `start_export` tool. `get_execution` checks the
owner's Operation status and supplies authenticated file download links when ready.
File Operations cannot use pagination. Developer direct queries do not reuse Operation
cursors or file artifacts.

## Follow-up work

- Progressive schema discovery (schema/table filters) for large databases.
- Configurable concurrency and bounded queue admission.
- Explicit audit retention/redaction settings and richer safe query diagnostics.
- Direct-query pagination/export only if needed, with caller/Target binding and
  current access checks on continuation and retrieval.
- Deployment-specific database privilege review and real PostgreSQL integration
  verification, including timeouts, function privileges, and read-only behavior.

## Acceptance criteria

Developers query granted Targets without creating Operations. Ungranted developers
cannot inspect/query them. Ordinary users cannot use free SQL even with a Target
grant. Developers cannot publish or share Operations, but can execute accessible
ones. Direct/group revocation and inactive accounts/Targets deny further exploration.
Only administrators curate the shared Operation catalog.
