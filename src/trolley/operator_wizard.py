"""Local interactive provisioning; no writes until final confirmation."""

from tortoise.transactions import in_transaction

from trolley.application.users import invite_user
from trolley.auth.roles import normalize_email
from trolley.domain.users import UserRole
from trolley.email import EmailService
from trolley.persistence.models import Group, GroupMembership, GroupTargetGrant, Target, User


async def add_user(settings, *, ask=input, tell=print):
    try:
        email = normalize_email(ask("1/5 Email: "))
        if email.count("@") != 1 or any(c.isspace() for c in email) or not all(email.split("@")):
            raise ValueError("Enter a valid email address")
        existing = await User.get_or_none(email=email)
        if existing:
            tell(f"Already registered: {email} ({existing.role}). No changes made.")
            tell("Use operator set-role / set-groups / invite explicitly.")
            return
        role = UserRole(ask("2/5 Role [user/developer/admin] (user): ").strip() or "user")
        available = await Group.all().order_by("name").values_list("name", flat=True)
        tell("Existing groups: " + (", ".join(available) or "none"))
        name = ask("3/5 Group name (existing or new): ").strip()
        if not name or len(name) > 255:
            raise ValueError("Group name must contain 1 to 255 characters")
        group = await Group.get_or_none(name=name)
        new_group = group is None
        if new_group:
            targets = await Target.filter(is_active=True).values_list("name", flat=True)
            tell("Available Targets: " + (", ".join(targets) or "none"))
            selected = sorted(
                set(ask("4/5 Targets for NEW group (comma-separated; blank = none): ").split(","))
            )
            selected = sorted({v.strip() for v in selected if v.strip()})
            if set(selected) - set(targets):
                raise ValueError("Unknown or inactive Target")
        else:
            selected = await GroupTargetGrant.filter(
                group=group, target__is_active=True
            ).values_list("target__name", flat=True)
            tell("4/5 Existing group Targets (unchanged): " + (", ".join(selected) or "none"))
        send_email = False
        if settings.smtp_host:
            send_email = ask("Send invitation email? [y/N]: ").strip().lower() == "y"
        else:
            tell(
                "SMTP unavailable; no key will be issued. "
                "Configure SMTP and use operator invite later."
            )
        tell(
            f"5/5 Email={email}; role={role}; group={name}; "
            f"Targets={list(selected)}; email={send_email}"
        )
        tell("Group members can execute ALL Operations on these Targets.")
        if ask("Save? [y/N]: ").strip().lower() != "y":
            tell("Cancelled; nothing saved.")
            return
    except (EOFError, KeyboardInterrupt):
        tell("Cancelled; nothing saved.")
        return

    async with in_transaction():
        # Create, not get_or_create: a concurrent operator must not silently change the plan.
        if new_group:
            group = await Group.create(name=name)
            for target_name in selected:
                target = await Target.get(name=target_name, is_active=True)
                await GroupTargetGrant.create(group=group, target=target)
        else:
            group = await Group.get(id=group.id)
            current = await GroupTargetGrant.filter(
                group=group, target__is_active=True
            ).values_list("target__name", flat=True)
            if set(current) != set(selected):
                raise ValueError("Group access changed; run the wizard again")
        user = await User.create(email=email, name=email, role=role)
        await GroupMembership.create(user=user, group=group)
    tell("User and group settings saved.")
    if send_email:
        try:
            await invite_user(
                email,
                email,
                "initial-access",
                EmailService(settings),
                settings.public_base_url.rstrip("/") + "/onboarding.md",
            )
        except Exception:
            tell(
                "Settings saved, but invitation failed. New key remains inactive. "
                "Retry: trolley operator invite " + email
            )
            return
        tell("Invitation accepted by SMTP; inbox delivery is not guaranteed.")
