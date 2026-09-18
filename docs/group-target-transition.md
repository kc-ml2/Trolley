# Fresh catalog and group-only access

[Operator wizard](operator-wizard.md) · [Deployment](deployment.md)

The current source uses User → Group → Target → all active Operations on that Target.
No global admin bypass, per-user Target grants or per-Operation permissions exist.
The old catalog schema is not automatically migrated. Review the deployed image
version before upgrading; source documentation does not imply it is already deployed.

## Fresh start

1. Build and test the new image before stopping the existing service.
2. Explicitly reset only the Trolley catalog if losing accounts, keys, groups,
   Operations, Target notes and execution history is intended. Never reset source DBs.
3. Start Trolley with the private catalog/Target settings. No users, groups, keys or
   sample Operations are created automatically.
4. Run `docker compose exec trolley trolley operator add-user` interactively to
   provision the first account, role, group and Target associations.
5. Enter the emailed key privately in a client and reconnect. Confirm capabilities.

Old keys are invalid after a catalog reset. An empty catalog is a valid startup
state; there is no bootstrap email allowlist or preconfigured operators group.
Creating an account or issuing a key alone does not grant Target access.

Operation publication exposes a tool to all members of groups using its Target.
Split Targets/DB roles when boundaries differ. Caller/shared controls result scope,
not execution permission. Direct SQL does not inherit caller filters.
