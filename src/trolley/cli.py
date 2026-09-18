import argparse
import asyncio

import uvicorn
from tortoise import Tortoise

from trolley.application import groups, target_access, targets, users
from trolley.application.users import invite_user
from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email
from trolley.config import ConfigurationError, Settings, get_settings, validate_runtime_settings
from trolley.domain.users import UserRole
from trolley.email import EmailService
from trolley.persistence.database import tortoise_config
from trolley.persistence.models import User


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(prog="trolley")
    commands = command_parser.add_subparsers(dest="command")

    setup = commands.add_parser("setup", help="Email a new key to existing accounts")
    setup.add_argument("emails", nargs="+", help="Existing account emails")
    setup.add_argument("--name", default="setup-access", help="Name of the new API key")

    admin = commands.add_parser("admin", help="Manage local administrator access")
    admin_commands = admin.add_subparsers(dest="admin_command", required=True)
    issue_key = admin_commands.add_parser("issue-key", help="Issue an admin API key")
    issue_key.add_argument("email")
    issue_key.add_argument("--name", default="local-admin")

    target = commands.add_parser("target", help="Inspect file-configured targets")
    target_commands = target.add_subparsers(dest="target_command", required=True)
    target_commands.add_parser("list", help="List configured targets")
    target_commands.add_parser("check", help="Validate and test configured targets")
    test_target = target_commands.add_parser("test", help="Test a configured target")
    test_target.add_argument("name")
    operator = commands.add_parser(
        "operator", help="Local-only identity and group Target management"
    )
    ops = operator.add_subparsers(dest="action", required=True)
    ops.add_parser("add-user", help="Interactive user/group/Target wizard")
    op = ops.add_parser("create-user")
    op.add_argument("email")
    op.add_argument("--role", choices=[str(r) for r in UserRole], default="user")
    op = ops.add_parser("create-group")
    op.add_argument("name")
    op = ops.add_parser("set-groups")
    op.add_argument("email")
    op.add_argument("groups", nargs="*")
    op = ops.add_parser("target-access")
    op.add_argument("target")
    op.add_argument("group")
    op.add_argument("--revoke", action="store_true")
    op = ops.add_parser("set-role")
    op.add_argument("email")
    op.add_argument("role", choices=[str(r) for r in UserRole])
    op = ops.add_parser("invite")
    op.add_argument("email")
    op.add_argument("--name", default="initial-access")
    ops.add_parser("list-access")
    return command_parser


async def issue_admin_key(settings: Settings, email: str, name: str) -> str:
    validate_runtime_settings(settings)
    email = normalize_email(email)

    await Tortoise.init(config=tortoise_config(settings))
    try:
        await Tortoise.generate_schemas()
        user = await User.get_or_none(email=email)
        if user is None or user.role != UserRole.ADMIN or not user.is_active:
            raise PermissionError("Create an active admin with operator create-user first")
        _, secret = await create_api_key(user, name.strip())
        return secret
    finally:
        await Tortoise.close_connections()


async def setup_admins(settings: Settings, emails: list[str], key_name: str) -> None:
    """Issue emailed keys without changing account roles or memberships."""
    validate_runtime_settings(settings)
    selected = sorted({normalize_email(email) for email in emails})
    service = EmailService(settings)
    if not await service.check():
        raise ConfigurationError("SMTP must be configured for setup")

    await Tortoise.init(config=tortoise_config(settings))
    try:
        await Tortoise.generate_schemas()
        for email in selected:
            await invite_user(
                email,
                email,
                key_name,
                service,
                settings.public_base_url.rstrip("/") + "/onboarding.md",
            )
            print(f"Invitation sent: {email}")
    finally:
        await Tortoise.close_connections()
    print(f"MCP endpoint: {settings.public_base_url.rstrip('/')}/mcp/")
    print("Enter the emailed key in your MCP client's secret settings.")


async def manage_local(settings, args):
    await Tortoise.init(config=tortoise_config(settings))
    try:
        await Tortoise.generate_schemas()
        await targets.sync_targets(settings)
        if args.action == "add-user":
            from trolley.operator_wizard import add_user

            await add_user(settings)
            return "Wizard finished"
        if args.action == "create-user":
            return await users.create_user(args.email, args.email, UserRole(args.role))
        if args.action == "create-group":
            return await groups.create_group(args.name)
        if args.action == "set-groups":
            return await groups.set_user_groups(args.email, args.groups)
        if args.action == "target-access":
            return await target_access.set_target_access(
                args.target, not args.revoke, group_name=args.group
            )
        if args.action == "set-role":
            return await users.set_user_role(args.email, UserRole(args.role))
        if args.action == "invite":
            return await users.invite_user(
                args.email,
                args.email,
                args.name,
                EmailService(settings),
                settings.public_base_url.rstrip("/") + "/onboarding.md",
            )
        return {
            "users": await users.list_users(),
            "groups": await groups.list_groups(),
            "memberships": await groups.list_group_memberships(),
            "targets": await target_access.list_target_grants(),
        }
    finally:
        await Tortoise.close_connections()


def main() -> None:
    command_parser = parser()
    args = command_parser.parse_args()
    try:
        settings = validate_runtime_settings(get_settings())
    except ConfigurationError as error:
        command_parser.error(str(error))

    if args.command == "operator":
        print(asyncio.run(manage_local(settings, args)))
        return

    if args.command == "setup":
        print("Setup issues a NEW key for each email; existing keys remain valid.")
        asyncio.run(setup_admins(settings, args.emails, args.name))
        return

    if args.command == "target":
        if args.target_command == "list":
            definitions = targets.configured_targets(settings)
            for definition in sorted(definitions.values(), key=lambda item: item.name):
                print(f"{definition.name}\t{definition.kind}")
            return
        if args.target_command == "test":
            result = asyncio.run(targets.test_target_connection(settings, args.name))
            print(f"{result['target']}\t{result['kind']}\t{result['status']}")
            return
        if args.target_command == "check":
            definitions = targets.configured_targets(settings)
            for definition in sorted(definitions.values(), key=lambda item: item.name):
                result = asyncio.run(targets.test_target_connection(settings, definition.name))
                print(f"{definition.name}\t{definition.kind}\t{result['status']}")
            return

    if args.command is None:
        uvicorn.run(
            "trolley.main:app_factory",
            host="0.0.0.0",
            port=8000,
            factory=True,
        )
        return

    if args.command == "admin" and args.admin_command == "issue-key":
        secret = asyncio.run(issue_admin_key(settings, args.email, args.name))
        print(f"Admin: {normalize_email(args.email)}")
        print(f"Key name: {args.name}")
        print(f"API key: {secret}")
        print("This key will not be shown again.")


if __name__ == "__main__":
    main()
