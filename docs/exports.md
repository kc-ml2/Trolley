# Download query results

[← README](../README.md) · [Usage guide](guide.md)

Administrators create file-output Operations such as `get_my_weekly_data` to deliver
approved query results as a **JSONL.gz file**. Calling that Operation generates a file;
callers do not select an export option. The output mode is fixed by the administrator.
Large inline queries never automatically switch to file output.

## Get a file

1. Ask your agent to find a file-output Operation and confirm the date range and
   whether sensitive content is needed (`list_operations` includes `output`).
2. It calls the Operation directly, or `execute(name, arguments)`. The response contains
   `output: "file"`, `execution_id`, and `status`. Poll `get_execution(execution_id)`;
   do not invoke the Operation again just to check progress.
3. When status is `succeeded`, download the returned URL with a trusted local client
   using your active Bearer key in the Authorization header. A browser link alone is
   insufficient. Never put keys in URLs or chat.

Statuses are `running`, `succeeded`, `failed`, and `expired`. Only the owner can access
a job—even administrators cannot download another user's export. Current access and
unchanged query/binding checks still apply. Revocation blocks subsequent downloads,
not an already-running query or streaming response.

## Create a file Operation as an administrator

Set `definition.output: "file"` when creating a purpose-specific Operation, for example
`get_my_weekly_data`. The default is `"inline"`. Input schemas and access policies
still apply. Caller scope generates an owner-filtered query; shared scope uses
administrator-approved SQL. Neither accepts SQL from the executing caller.
Both the named tool and `execute` start file generation. File Operations cannot
configure pagination. Shared SQL requires `fetch: true` (the default); caller scope
sets it internally and forbids an explicit `fetch` field. If you also need inline results,
publish a separate inline Operation. Only administrators can create/change output modes.
Use complete replacement definitions with `update_operation`. The old `export` boolean
is rejected; there are no `start_export` or `get_my_export` system tools.

For a personal file such as `get_my_weekly_data`, use `data_scope: "caller"` and
`output: "file"` with a structured source, ownership column, projected columns,
and optional date filters. See the complete [personal data example](caller-data.md).
Do not expose email as an input. Shared file Operations instead explicitly declare
`data_scope: "shared"` and administrator-approved SQL/parameters.

Review source ownership and omit secret-bearing columns. Confirm scope/content
before invocation; file generation does not redact sensitive records.

The gzip file contains one JSON object per row. Dates/decimals use the same conversion
as normal Operation results. The file is only downloadable after successful completion;
a limit failure never yields a successful partial export. There is no row pagination
or continuation cursor: a read-only repeatable-read transaction streams the entire query
from one database snapshot. SQL LIMIT/OFFSET clauses still apply if the administrator
puts them in the query. JSONL line order follows the query; add ORDER BY when needed.

## Operator configuration

Optional `trolley.yaml` settings:

```yaml
exports:
  directory: /var/lib/trolley/exports
  max_rows: 100000
  max_bytes: 100000000
  timeout_seconds: 300
  ttl_seconds: 3600
  max_jobs: 10
```

Defaults use `./trolley-exports`. Use a dedicated private directory, not a shared data
folder. Give the service write access (including any systemd ReadWritePaths restriction).
The directory is mode 0700 and generated files are 0600. Never serve it as static files.
Local same-user/root access remains possible. Do not commit or casually back up exports.

Only one export runs at a time globally. `max_jobs` limits retained successful/running
jobs; each file is bounded by `max_bytes` for both uncompressed and compressed sizes.
TTL starts at successful completion. Cleanup runs on startup and roughly every 30
seconds while the server is running. Files may remain on disk while the server is down.
Metadata remains in the catalog without automatic audit retention. `ExportJob` is a new
table created through existing startup schema generation; back up the catalog first.

Only job conditions, counts, timestamps, and status are stored in the catalog, not
exported bodies or raw database error messages. Arguments can still contain sensitive
values. A job interrupted by server restart is marked failed, not resumed. Single
process only; no Redis, worker cluster, or shared export directory support.

A single oversized PostgreSQL field must still be received and serialized before its
size can be rejected. Compression/file writes run locally in the server process and
may briefly block other requests; this is a bounded first version, not a large-scale
ETL pipeline. Test realistic weekly data sizes before production use. Original data
retention and shared-key ownership rules still determine what “my full logs” means.
