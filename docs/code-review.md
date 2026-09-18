# Code review: reliability and maintenance

This review covers authentication/authorization paths, caller SQL compilation,
inline/file execution, pagination, input validation, email and deployment setup.
It is not a complete security audit or a production load test.

## Fixed in this review

- Inline and file execution now share input validation with JSON Schema format
  checking. Invalid date/date-time inputs fail before database execution. Validation
  errors do not echo rejected values or the complete schema to callers.
- Direct-query audit finalization no longer replaces a successful query result or
  masks the original query failure. Successful queries include an audit warning when
  persistence fails, avoiding misleading retry instructions.
- Pydantic configuration errors no longer interpolate raw configuration values
  (which can contain credentials) into the public configuration error message.

## Remaining work (not silently changed)

1. **Typed caller filters:** mapped aggregate date dimensions handle JSON strings,
   but single-relation and identity-transform filters still rely on driver-compatible
   types. Add an explicit, allowlisted type contract before claiming support for
   arbitrary timestamp/date/UUID filters. Avoid inferring SQL casts from untrusted text.
2. **SQL compiler boundaries:** caller_usage imports private helpers from caller while
   caller dispatches back via a local import. Move shared primitives to a neutral
   module when expanding the compiler; avoid growing a general SQL language.
3. **Diagnostics:** inline execution still persists raw database exception messages;
   direct queries and exports already sanitize diagnostics. Standardize safe error
   codes and logging without masking uncertain write outcomes.
4. **Scalability:** export cleanup scans historical jobs; inline queries lack global
   concurrency admission. Measure before broad rollout and add bounded retention and
   queue controls. Keep one worker until registry/job coordination is implemented.
5. **Operations:** versioned migrations and managed key revocation remain absent.
   PostgreSQL catalog setup uses a provisioning account; production environments
   should consider a dedicated catalog role. Do not grant catalog access as a Target.
6. **Email delivery:** SMTP success is not inbox confirmation. Delivery tracing and
   recipient-facing troubleshooting remain operational tasks, not guaranteed delivery.

## Verification

Run `pytest`, `ruff check .`, `ruff format --check .`, and
`PYTHON=venv/bin/python ./scripts/test-postgres-integration.sh`.
Integration tests use a disposable PostgreSQL instance, not operational Targets.
No production data, grants, keys or Operation definitions are modified by this review.
