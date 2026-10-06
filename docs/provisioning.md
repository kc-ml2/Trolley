# Master-service key provisioning

This optional HTTP endpoint supplements the local CLI; it is not an MCP tool.
Enable it in private `trolley.yaml` and restart:

```yaml
provisioning:
  key: "<random master secret, e.g. openssl rand -hex 32>"
```

Absent or empty key disables it (404). Keep the key in the trusted backend's
secret storage, never browser code, chat, Git or request logs. Use HTTPS. This key
can issue credentials for existing admins as well as regular users: it is a master
credential, not a user-scoped API key. It does not authenticate to MCP.

```http
POST /provision/user
Authorization: Bearer <provisioning key>
Content-Type: application/json

{"email":"member@example.com","targets":["heimdall-db","scenesense-db"]}
```

Response: HTTP 201, `Cache-Control: no-store`:

```json
{"email":"member@example.com","targets":["heimdall-db","scenesense-db"],"api_key":"<new secret>"}
```

- The trusted backend must derive email from its verified session, not an arbitrary
  browser-supplied email. Trolley does not independently verify the email.
- `targets` must be a non-empty array (up to 100 entries). Names are trimmed,
  deduplicated and returned sorted. The old singular `target` field is not accepted.
- ALL Targets must be configured and active; otherwise 404 without creating an account
  or adding any permissions. A successful request issues exactly one key.
- New users get role `user`. Existing roles, names and memberships are preserved.
- Inactive accounts return 409 and are not reactivated.
- If Target access is missing, a stable `provisioning-target-<target UUID>` group is
  created/reused and membership added. Existing groups are never expanded to new
  Targets. If the managed group was repurposed to other Targets, provisioning fails.
- Creation, access assignment and key issuance are transactional. Failure rolls back.
- No email is sent. The raw key is returned once; only its hash is stored.
- Every successful call creates a new key; old keys remain valid. No idempotency or
  automatic retry support: a lost response may leave a valid key without its secret.
- The key inherits ALL account permissions, not only the requested Targets. Provisioning
  an existing admin therefore issues an admin key. Do not expose this API to users.

Wrong/missing provisioning credentials return 401; invalid request bodies return 422.
Do not log response bodies or Authorization headers in either service or reverse
proxy. Rotate the provisioning key by changing both backend settings and Trolley's
configuration, then restarting. Rotation does not revoke already issued user keys.
