from datetime import datetime, timezone
from typing import List, Union
import discord
from discord.ext import commands
from discord import app_commands

from deps.custom_match.custom_match_functions import create_team_by_win_percentage
from deps.data_access import data_access_get_custom_game_voice_channels, data_access_get_member
from deps.custom_match.custom_match_data_access import fetch_user_subscription_for_guild, subscribe_custom_game

from deps.values import (
    COMMAND_CUSTOM_GAME_LFG,
    COMMAND_CUSTOM_GAME_MAKE_TEAM,
    COMMAND_CUSTOM_GAME_SUBSCRIBE,
    COMMAND_CUSTOM_GAME_UNSUBSCRIBE,
    COMMAND_CUSTOM_GAME_SEE_SUBSCRIPTIONS,
)
from deps.mybot import MyBot
from deps.log import print_warning_log, print_error_log


class UserCustomGameFeatures(commands.Cog):
    """User command for the custom game that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_CUSTOM_GAME_SUBSCRIBE)
    async def register_custom_game(self, interaction: discord.Interaction):
        """
        Register to a custom game
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        if interaction.guild is None:
            print_error_log(
                f"register_custom_game: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        current_datetime = datetime.now(timezone.utc)
        subscribe_custom_game(user_id, guild_id, current_datetime)
        await interaction.followup.send(content=f"{display_name} subscribed to future 10-man notifications using the /{COMMAND_CUSTOM_GAME_SUBSCRIBE}. To unsubscribe use /{COMMAND_CUSTOM_GAME_UNSUBSCRIBE}", ephemeral=False)

    @app_commands.command(name=COMMAND_CUSTOM_GAME_UNSUBSCRIBE)
    async def unsubscribe_custom_game(self, interaction: discord.Interaction):
        """
        Unsubscribe from custom game notifications
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        if interaction.guild is None:
            print_error_log(
                f"see_custom_game_subscriptions: No guild available for user {display_name}({user_id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        user_ids: List[int] = fetch_user_subscription_for_guild(guild_id)
        if not user_ids:
            await interaction.followup.send(content="You are not currently subscribed to custom game notifications in this server.", ephemeral=True)
            return

        await interaction.followup.send(content=f"{display_name} unsubscribed to 10-man notifications", ephemeral=False)

    @app_commands.command(name=COMMAND_CUSTOM_GAME_SEE_SUBSCRIPTIONS)
    async def see_custom_game_subscriptions(self, interaction: discord.Interaction):
        """
        See all users subscribed to custom game notifications
        """
        await interaction.response.defer()
        if interaction.guild is None:
            print_error_log(
                f"see_custom_game_subscriptions: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        user_ids: List[int] = fetch_user_subscription_for_guild(guild_id)
        if not user_ids:
            await interaction.followup.send(content="No users are currently subscribed to custom game notifications in this server.", ephemeral=True)
            return

        member_mentions = []
        for user_id in user_ids:
            member: Union[discord.Member, None] = await data_access_get_member(user_id)
            if member:
                member_mentions.append(member.display_name)
            else:
                member_mentions.append(f"User ID {user_id} (not found in guild)")

        mentions_text = ", ".join(member_mentions)
        await interaction.followup.send(content=f"Users subscribed to custom game notifications: {mentions_text}", ephemeral=True)

    @app_commands.command(name=COMMAND_CUSTOM_GAME_LFG)
    async def custom_game_lfg(self, interaction: discord.Interaction):
        """
        Look for a custom game
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        if interaction.guild is None:
            print_error_log(
                f"custom_game_lfg: No guild available for user {display_name}({user_id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        user_ids: List[int] = fetch_user_subscription_for_guild(guild_id)
        if not user_ids:
            await interaction.followup.send(content="No users are currently subscribed to custom game notifications in this server.", ephemeral=True)
            return

        member_mentions = []
        for user_id in user_ids:
            member: Union[discord.Member, None] = await data_access_get_member(user_id)
            if member:
                member_mentions.append(member.mention)
            else:
                member_mentions.append(f"User ID {user_id} (not found in guild)")

        mentions_text = ", ".join(member_mentions)
        await interaction.followup.send(content=f"{mentions_text} are you available for a 10-man?", ephemeral=True)
    
    @app_commands.command(name=COMMAND_CUSTOM_GAME_MAKE_TEAM)
    async def custom_game_make_team(self, interaction: discord.Interaction):
        """
        Get all the users from the custom game voice channels and make two teams depending of a selected algorithm
        """
        await interaction.response.defer()
        if interaction.guild is None:
            print_error_log(
                f"custom_game_make_team: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id

        lobby_channel_id, team1_channel_id, team2_channel_id = data_access_get_custom_game_voice_channels(guild_id)
        if not lobby_channel_id or not team1_channel_id or not team2_channel_id:
            await interaction.followup.send(content="Custom game voice channels are not properly configured. Please contact an administrator.", ephemeral=True)
            return
        users_lobby_voice_channel: List[discord.Member] = []
        lobby_channel = guild.get_channel(lobby_channel_id)
        if isinstance(lobby_channel, discord.VoiceChannel):
            users_lobby_voice_channel = lobby_channel.members
            create_team_by_win_percentage_result = await create_team_by_win_percentage(users_lobby_voice_channel)
            await interaction.followup.send(content=f"Teams created using logic: {create_team_by_win_percentage_result.logic}\n\n{create_team_by_win_percentage_result.explanation}", ephemeral=False)
        else:
            print_warning_log(f"custom_game_make_team: Lobby channel ID {lobby_channel_id} is not a voice channel.")
            await interaction.followup.send(content="Lobby voice channel is not found or not a voice channel. Please contact an administrator.", ephemeral=True)
            return
        

async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserCustomGameFeatures(bot))
