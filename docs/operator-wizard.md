# Local operator: add a user interactively

Start an empty server, then run in an interactive terminal (do not use `exec -T`):

```bash
docker compose exec trolley trolley operator add-user
```

1. Enter the user's email.
2. Choose `user`, `developer`, or `admin` (default: user).
3. Select an existing group by name or type a new group name.
4. For a new group, select configured active Targets by comma-separated names.
   Existing groups show their current Targets without changing them.
5. Choose whether to send an invitation (SMTP required), review, and confirm.

Before the final confirmation, no user, group, membership or Target grant is saved.
Cancellation or EOF leaves no account changes. After confirmation these records are
saved in one transaction. Email is sent afterwards: delivery failure preserves the
account settings and leaves the newly issued key inactive. Retry only invitation:

```bash
docker compose exec trolley trolley operator invite user@example.com
```

An existing email is never overwritten. The wizard displays the current role and
points to explicit edit commands. It does not issue a new key automatically.

For automation, use:

```bash
trolley operator create-user user@example.com --role user
trolley operator create-group engineering
trolley operator set-groups user@example.com engineering
trolley operator target-access reporting-db engineering
trolley operator invite user@example.com
```

`set-groups` replaces memberships. Role changes, including admin promotion/demotion,
are local CLI operations. Invitation requires an existing user and never changes
role or group. Users without group Target access cannot access any Operations.
All members sharing a Target can execute all of its active Operations.

Startup does not create accounts or groups. There is no administrator email allowlist
in authorization: the stored account role is authoritative. The old admin_emails
configuration and function arguments have been removed. Existing records are not
deleted by startup; resetting a deployed catalog is a separate explicit operator
action. Source databases must not be reset.

The CLI is the privileged management boundary: restrict SSH, Docker and configuration
access. Do not expose these commands as MCP tools. Never paste API keys into chat.
