"""Permission decorators for slash commands."""

from typing import TypeVar

from discord import app_commands

T = TypeVar("T")


def admin_only(command: T) -> T:
    """
    Restrict a slash command to administrators.

    commands.has_permissions only works on prefix commands: on a slash command it is silently
    ignored. default_permissions hides the command from other members once synced, and the check
    enforces it on the bot's side, whatever the permission overrides configured in the server.
    """
    restricted = app_commands.checks.has_permissions(administrator=True)(command)
    return app_commands.default_permissions(administrator=True)(restricted)
