# Export approved Operations

Administrators enable exports on an Operation with `definition.export: true`.
The existing SQL, input schema, access policy, and server email bindings still apply.
No arbitrary SQL is accepted from the caller. Ordinary `execute` limits remain intact.

Example definition (adapt tables and columns to the actual schema):

```json
{
  "sql": "SELECT request_id, started_at, CASE WHEN $4::boolean THEN messages ELSE NULL END AS messages, CASE WHEN $4::boolean THEN response ELSE NULL END AS response FROM logs WHERE owner_email = $1 AND started_at >= $2::text::timestamp AND started_at < $3::text::timestamp ORDER BY started_at, request_id",
  "parameters": ["caller_email", "start_time", "end_time", "include_content"],
  "bindings": {"caller_email": "authenticated_user.email"},
  "fetch": true,
  "export": true
}
```

Define required public inputs `start_time`, `end_time` (strings) and `include_content`
(boolean) in `input_schema`; do not expose `caller_email`. Set `access` explicitly,
preferably `restricted`. Review the ownership relationship and omit API key columns,
HTTP headers, and other secrets. Content may itself contain secrets: export does not
redact them. User agreement on scope/content must precede the export call.

1. Call `start_export(name, arguments)` with fixed start/end times and content choice.
2. Poll `get_my_export(export_id)` for `running`, `succeeded`, `failed`, or `expired`.
3. Download the returned URL using the owner's active Bearer key in the Authorization
   header, never in a query string. A browser link alone is insufficient. Use a trusted
   local client with credentials configured privately; do not paste keys into chat.

The gzip file contains one JSON object per row. Dates/decimals use the same conversion
as normal Operation results. The file is only downloadable after successful completion;
a limit failure never yields a successful partial export. There is no row pagination
or continuation cursor: a read-only repeatable-read transaction streams the entire query
from one database snapshot. SQL LIMIT/OFFSET clauses still apply if the administrator
puts them in the query. JSONL line order follows the query; add ORDER BY when needed.

Download and status checks enforce job ownership, current key/user activation, current
Operation access, and unchanged definition/schema/caller binding fingerprint. Admins
cannot download other users' jobs. Revocation does not interrupt an already streaming
HTTP response or an already running query, but subsequent downloads are denied.

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
