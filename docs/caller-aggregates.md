# Caller usage aggregates without a database view

Administrators can create a `caller` Operation with an ownership mapping and
structured aggregation. This does not enable arbitrary SQL, general JOINs, or
writes. Existing single-relation caller Operations remain supported.

Example `definition` for Heimdall (validate the actual key/log relationship first):

```json
{
  "data_scope": "caller",
  "source": {"schema": "public", "relation": "LiteLLM_SpendLogs"},
  "ownership": {
    "source": {"schema": "public", "relation": "LiteLLM_VerificationToken"},
    "source_column": "api_key",
    "match_column": "token",
    "column": "metadata",
    "json_key": "owner_email",
    "identity": "authenticated_user.email"
  },
  "dimensions": [
    {"column": "startTime", "transform": "date", "as": "usage_date"},
    {"column": "model", "transform": "identity", "as": "model"}
  ],
  "metrics": [
    {"function": "count", "as": "request_count"},
    {"function": "sum", "column": "prompt_tokens", "as": "input_tokens"},
    {"function": "sum", "column": "completion_tokens", "as": "output_tokens"},
    {"function": "sum", "column": "spend", "as": "cost"}
  ],
  "filters": [
    {"dimension": "usage_date", "operator": "gte", "parameter": "start_date"},
    {"dimension": "usage_date", "operator": "lte", "parameter": "end_date"}
  ],
  "pagination": {"order_by": ["usage_date", "model"]}
}
```

All group members with Target access may run the Operation. Use this `input_schema`:

```json
{
  "type": "object",
  "properties": {
    "start_date": {"type": "string", "format": "date"},
    "end_date": {"type": "string", "format": "date"}
  },
  "required": ["start_date", "end_date"],
  "additionalProperties": false
}
```

The compiler uses a correlated `EXISTS` to authorize source rows **before**
aggregation. Duplicate mapping rows do not multiply usage. Only JSON strings
are accepted as owner emails, trimmed and lowercased to match Trolley's normalized
email. Missing, null, non-string and unmatched mappings do not authorize rows.
Clients cannot supply or override the authenticated email.

Dimensions support `identity` and `date`; metrics support `count` (all matching
rows) and `sum` (null totals become zero). Filters refer to dimension aliases and
support eq/gte/gt/lte/lt. Every filter parameter must be declared and required.
Raw SQL, bindings, expressions and arbitrary functions are rejected.

## Administrator responsibilities

- Verify the mapping column really identifies ownership and is writable only by
  trusted administrators. A shared key grants all its usage to its current owner.
- Reassignment changes access to historical usage; deleted keys no longer match.
- Review every dimension/metric: do not expose key identifiers or sensitive data.
- A date cast of `timestamp without time zone` uses the stored calendar date;
  confirm whether Heimdall stores UTC. This version does not convert timezones.
- Counts include all matching logs, not just successful requests. Review cost and
  token semantics, missing logs and retention before treating them as billing data.
- Inspect query plans and indexes for large logs. Existing row/byte/time limits
  still apply, and bounded date filters are recommended.
- Pagination must order by a unique combination of grouping dimensions. Queries
  without dimensions return a single aggregate row (zero counts when no match).

Creating the Operation does not modify the Target schema. Review group Target membership, the definition and owner isolation before publication.
