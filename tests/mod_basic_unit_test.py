"""Tests for basic moderator commands."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import discord

from cogs.mod_basic import ModBasic


def _role(name: str, position: int, *, managed: bool = False) -> Mock:
    role = Mock(spec=discord.Role)
    role.name = name
    role.position = position
    role.managed = managed
    return role


def _interaction(guild: Mock, member: Mock) -> Mock:
    interaction = Mock(spec=discord.Interaction)
    interaction.guild = guild
    interaction.user = member
    interaction.response = Mock()
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = Mock()
    interaction.followup.send = AsyncMock()
    return interaction


def _guild_with_bot(*roles: Mock) -> Mock:
    guild = Mock(spec=discord.Guild)
    guild.name = "Guild"
    guild.id = 123
    guild.owner_id = 999
    guild.default_role = _role("@everyone", 0)
    guild.roles = list(roles)
    bot_member = Mock(spec=discord.Member)
    bot_member.top_role = _role("Bot", 200)
    guild.me = bot_member
    return guild


async def test_reset_rank_roles_removes_rank_roles_and_adds_unranked() -> None:
    """Reset rank removes competitive roles and adds Unranked without replacing other roles."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    support = _role("Support", 10)
    diamond = _role("Diamond", 50)
    unranked = _role("Unranked", 20)
    guild = _guild_with_bot(support, diamond, unranked)

    member = Mock(spec=discord.Member)
    member.id = 456
    member.display_name = "Player"
    member.bot = False
    member.top_role = diamond
    member.roles = [support, diamond]
    member.remove_roles = AsyncMock()
    member.add_roles = AsyncMock()

    already_unranked = Mock(spec=discord.Member)
    already_unranked.id = 457
    already_unranked.display_name = "Idle"
    already_unranked.bot = False
    already_unranked.top_role = unranked
    already_unranked.roles = [support, unranked]
    already_unranked.remove_roles = AsyncMock()
    already_unranked.add_roles = AsyncMock()

    guild.members = [member, already_unranked]

    async def async_members():
        yield member
        yield already_unranked

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        Mock(
            spec=discord.Member,
            display_name="Admin",
            id=1,
            guild_permissions=SimpleNamespace(administrator=True),
            roles=[],
        ),
    )

    await cog.reset_rank_roles.callback(cog, interaction)

    member.remove_roles.assert_awaited_once_with(diamond, reason="Mod reset ranks for the start of a new season.")
    member.add_roles.assert_awaited_once_with(unranked, reason="Mod reset ranks for the start of a new season.")
    already_unranked.remove_roles.assert_not_called()
    already_unranked.add_roles.assert_not_called()
    interaction.followup.send.assert_awaited_once()


async def test_reset_rank_roles_skips_mod_above_bot() -> None:
    """Members whose top role is above the bot (e.g. Mod) are skipped instead of failing."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    mod_role = _role("Mod", 250)
    diamond = _role("Diamond", 50)
    unranked = _role("Unranked", 20)
    guild = _guild_with_bot(mod_role, diamond, unranked)

    moderator = Mock(spec=discord.Member)
    moderator.id = 456
    moderator.display_name = "joechoda"
    moderator.bot = False
    moderator.top_role = mod_role
    moderator.roles = [mod_role, diamond]
    moderator.remove_roles = AsyncMock()
    moderator.add_roles = AsyncMock()

    guild.members = [moderator]

    async def async_members():
        yield moderator

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        Mock(
            spec=discord.Member,
            display_name="Admin",
            id=1,
            guild_permissions=SimpleNamespace(administrator=True),
            roles=[],
        ),
    )

    await cog.reset_rank_roles.callback(cog, interaction)

    moderator.remove_roles.assert_not_called()
    moderator.add_roles.assert_not_called()
    followup_message = interaction.followup.send.await_args.args[0]
    assert "Skipped 1 member(s)" in followup_message
    assert "above the bot" in followup_message


async def test_reset_rank_roles_keeps_managed_booster_role() -> None:
    """Reset must not use member.edit(roles=...), which drops managed roles and causes Forbidden."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    booster = _role("Server Booster", 5, managed=True)
    diamond = _role("Diamond", 50)
    unranked = _role("Unranked", 20)
    guild = _guild_with_bot(booster, diamond, unranked)

    member = Mock(spec=discord.Member)
    member.id = 456
    member.display_name = "Booster"
    member.bot = False
    member.top_role = diamond
    member.roles = [booster, diamond]
    member.edit = AsyncMock()
    member.remove_roles = AsyncMock()
    member.add_roles = AsyncMock()

    guild.members = [member]

    async def async_members():
        yield member

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        Mock(
            spec=discord.Member,
            display_name="Admin",
            id=1,
            guild_permissions=SimpleNamespace(administrator=True),
            roles=[],
        ),
    )

    await cog.reset_rank_roles.callback(cog, interaction)

    member.edit.assert_not_called()
    member.remove_roles.assert_awaited_once_with(diamond, reason="Mod reset ranks for the start of a new season.")
    member.add_roles.assert_awaited_once_with(unranked, reason="Mod reset ranks for the start of a new season.")


async def test_reset_rank_roles_does_not_edit_bots() -> None:
    """Reset rank should only change roles on human accounts."""
    bot = Mock()
    bot.tree.add_command = Mock()
    cog = ModBasic(bot)

    diamond = _role("Diamond", 50)
    unranked = _role("Unranked", 20)
    guild = _guild_with_bot(diamond, unranked)

    human = Mock(spec=discord.Member)
    human.id = 1
    human.display_name = "Player"
    human.bot = False
    human.top_role = diamond
    human.roles = [diamond]
    human.remove_roles = AsyncMock()
    human.add_roles = AsyncMock()

    other_bot = Mock(spec=discord.Member)
    other_bot.id = 2
    other_bot.display_name = "HelperBot"
    other_bot.bot = True
    other_bot.roles = [diamond]

    guild.members = [human, other_bot]

    async def async_members():
        yield human
        yield other_bot

    guild.fetch_members = Mock(return_value=async_members())

    interaction = _interaction(
        guild,
        Mock(
            spec=discord.Member,
            display_name="Admin",
            id=99,
            guild_permissions=SimpleNamespace(administrator=True),
            roles=[],
        ),
    )

    await cog.reset_rank_roles.callback(cog, interaction)

    human.remove_roles.assert_awaited_once()
    followup_message = interaction.followup.send.await_args.args[0]
    assert "Ignored 1 bot(s)" in followup_message
