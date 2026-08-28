import argparse
import asyncio

import uvicorn
from tortoise import Tortoise

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
