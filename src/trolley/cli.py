import argparse
import asyncio

import uvicorn
from tortoise import Tortoise

from trolley.application import targets
from trolley.application.admins import ensure_admin_users
from trolley.auth.api_keys import create_api_key
from trolley.auth.roles import normalize_email
from trolley.config import ConfigurationError, Settings, validate_runtime_settings
from trolley.domain.users import UserRole
from trolley.persistence.database import tortoise_config
from trolley.persistence.models import User


def parser() -> argparse.ArgumentParser:
    command_parser = argparse.ArgumentParser(prog="trolley")
    commands = command_parser.add_subparsers(dest="command")

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
    return command_parser


async def issue_admin_key(settings: Settings, email: str, name: str) -> str:
    validate_runtime_settings(settings)
    email = normalize_email(email)
    if email not in settings.admin_emails:
        raise PermissionError("Email is not in TROLLEY_ADMIN_EMAILS")

    await Tortoise.init(config=tortoise_config(settings))
    try:
        await Tortoise.generate_schemas()
        await ensure_admin_users(settings.admin_emails)
        user = await User.get_or_none(email=email)
        if user is None:
            user = await User.create(email=email, name=email, role=UserRole.ADMIN)
        else:
            user.role = UserRole.ADMIN
            user.is_active = True
            await user.save()
        _, secret = await create_api_key(user, name.strip())
        return secret
    finally:
        await Tortoise.close_connections()


def main() -> None:
    command_parser = parser()
    args = command_parser.parse_args()
    try:
        settings = validate_runtime_settings(Settings())
    except ConfigurationError as error:
        command_parser.error(str(error))

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
                if definition.kind == "postgresql":
                    result = asyncio.run(targets.test_target_connection(settings, definition.name))
                    print(f"{definition.name}\t{definition.kind}\t{result['status']}")
                else:
                    print(f"{definition.name}\t{definition.kind}\tconfigured")
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
