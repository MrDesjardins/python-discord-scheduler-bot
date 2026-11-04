"""Unit tests for the slash command permission restrictions"""

import importlib
import inspect
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord import app_commands
from discord.ext import commands
import pytest

from deps.app_command_checks import admin_only
from deps.mybot import MyBot

COGS_DIRECTORY = Path(__file__).resolve().parents[1] / "cogs"
# Sample of each cog that declares admin commands, including both decorator orders in use.
ADMIN_COMMAND_CALLBACKS = (
    ("mod_basic", "reset_cache"),
    ("mod_basic", "tracker_status"),
    ("mod_channels", "set_voice_channels"),
    ("mod_channels", "see_ai_text_channel"),
    ("mod_analytics", "community_show_image"),
    ("mod_tournament", "create_tournament"),
    ("mod_onbehalf", "mod_stats"),
    ("user_schedule", "apply_schedule"),
)


def _commands_of_cog_module(module_name: str) -> Iterator[app_commands.Command]:
    module = importlib.import_module(f"cogs.{module_name}")
    for _, cog in inspect.getmembers(module, inspect.isclass):
        if issubclass(cog, commands.Cog) and cog.__module__ == module.__name__:
            yield from (c for c in cog.__cog_app_commands__ if isinstance(c, app_commands.Command))


def _all_cog_module_names() -> list[str]:
    return [path.stem for path in COGS_DIRECTORY.glob("*.py") if path.stem != "__init__"]


def _interaction(**permissions: Any) -> MagicMock:
    interaction = MagicMock(spec=discord.Interaction)
    interaction.permissions = discord.Permissions(**permissions)
    return interaction


def test_admin_only_rejects_a_member_and_accepts_an_administrator():
    async def callback(interaction: discord.Interaction) -> None:
        """Command under test"""

    command = app_commands.Command(name="x", description="d", callback=admin_only(callback))
    check = command.checks[0]

    with pytest.raises(app_commands.MissingPermissions):
        check(_interaction())
    assert check(_interaction(administrator=True)) is True
    assert command.default_permissions == discord.Permissions(administrator=True)


@pytest.mark.parametrize("module_name,callback_name", ADMIN_COMMAND_CALLBACKS)
def test_admin_commands_are_restricted(module_name, callback_name):
    command = next(c for c in _commands_of_cog_module(module_name) if c.callback.__name__ == callback_name)

    assert command.default_permissions == discord.Permissions(administrator=True)
    assert len(command.checks) >= 1


@pytest.mark.parametrize("module_name", _all_cog_module_names())
def test_no_slash_command_relies_on_the_ignored_prefix_command_check(module_name):
    for command in _commands_of_cog_module(module_name):
        assert not hasattr(command, "__commands_checks__"), command.name
        assert not hasattr(command.callback, "__commands_checks__"), command.name


@pytest.mark.asyncio
async def test_a_refused_member_gets_a_private_answer():
    bot = MyBot()
    interaction = _interaction()
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()

    await bot.tree.on_error(interaction, app_commands.MissingPermissions(["administrator"]))

    interaction.response.send_message.assert_awaited_once()
    assert interaction.response.send_message.call_args.kwargs["ephemeral"] is True


@pytest.mark.asyncio
async def test_other_command_errors_keep_the_default_handling():
    bot = MyBot()
    interaction = _interaction()
    error = app_commands.AppCommandError("boom")

    with patch.object(app_commands.CommandTree, "on_error", new=AsyncMock()) as default_handler:
        await bot.on_app_command_error(interaction, error)

    default_handler.assert_awaited_once_with(bot.tree, interaction, error)
