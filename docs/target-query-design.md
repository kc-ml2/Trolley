# Target exploration and Operation publication

Access is User → Group → Target. No direct user grants or per-Operation permissions.

- Admins explore and publish within group Targets only.
- Developers explore group Targets but cannot publish.
- Users execute all active Operations on group Targets; no direct SQL/schema access.
- Local CLI operators manage identities, groups and Target assignment. There is no
  privileged MCP identity-management tool or global admin data bypass.

Exploration is read-only and does not create an Operation. Direct SQL uses the
Target database account; it has no automatic caller row filtering. Restrict database
roles/views for sensitive data and separate Targets for distinct access domains.

`query_target` accepts positional parameters and records SQL/status, not response
bodies. Four concurrent direct queries per process are allowed, with Target timeout
and result limits. Pagination/export for direct SQL is not implemented.

Operation publication exposes a tool to everyone with group access to its Target.
Caller definitions enforce authenticated ownership; shared definitions run approved
SQL. File output and pagination remain available for configured Operations.

See [usage](guide.md), [operator setup](operator-wizard.md), and
[personal-data guarantees](caller-data.md). Only one server worker is supported.
