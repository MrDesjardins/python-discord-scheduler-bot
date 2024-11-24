import discord
from discord.ext import commands
from discord import app_commands
from deps.bot_common_actions import send_daily_question_to_a_guild
from deps.data_access import (
    data_access_get_gaming_session_text_channel_id,
    data_access_get_guild_text_channel_id,
    data_access_get_guild_username_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_new_user_text_channel_id,
    data_access_set_gaming_session_text_channel_id,
    data_access_set_guild_username_text_channel_id,
    data_access_set_new_user_text_channel_id,
    data_access_set_guild_text_channel_id,
    data_access_set_guild_voice_channel_ids,
)
from deps.values import (
    COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION,
    COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION,
    COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL,
    COMMAND_SEE_GAMING_SESSION_CHANNEL,
    COMMAND_SET_GAMING_SESSION_CHANNEL,
    COMMAND_SEE_NEW_USER_CHANNEL,
    COMMAND_SET_NEW_USER_CHANNEL,
)
from deps.mybot import MyBot
from deps.log import print_warning_log


class ModChannels(commands.Cog):
    """Moderator commands for settings the channels that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL)
    async def set_username_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the user name is shown
        """
        guild_id = interaction.guild.id
        data_access_set_guild_username_text_channel_id(guild_id, channel.id)

        await interaction.response.send_message(
            f"Confirmed to send a user name message into #{channel.name}.",
            ephemeral=True,
        )

    @commands.has_permissions(administrator=True)
    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL)
    async def see_username_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_guild_username_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No username text channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Username Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The username text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_SET_GAMING_SESSION_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_gaming_session_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the user name is shown
        """
        guild_id = interaction.guild.id
        data_access_set_gaming_session_text_channel_id(guild_id, channel.id)

        await interaction.response.send_message(
            f"Confirmed to send user gaming session stats into #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SEE_GAMING_SESSION_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_gaming_session_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_gaming_session_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No gaming session stats channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Gaming Session Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The gaming session text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_SET_NEW_USER_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_new_user_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the user name is shown
        """
        guild_id = interaction.guild.id
        data_access_set_new_user_text_channel_id(guild_id, channel.id)

        await interaction.response.send_message(
            f"Confirmed to send new user message into #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SEE_NEW_USER_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_new_user_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_new_user_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No new user channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("New User Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The new user text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_voice_channels(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        """
        Set the voice channels to listen to the users in the voice channel
        """
        guild_id = interaction.guild.id
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_channel_ids is None:
            voice_channel_ids = []

        if channel.id not in voice_channel_ids:
            voice_channel_ids.append(channel.id)
        data_access_set_guild_voice_channel_ids(guild_id, voice_channel_ids)
        await interaction.response.send_message(
            f"The bot will check the voice channel #{channel.name}.", ephemeral=True
        )

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION)
    @commands.has_permissions(administrator=True)
    async def reset_voice_channels(self, interaction: discord.Interaction):
        """
        Set the voice channels to listen to the users in the voice channel
        """
        guild_id = interaction.guild.id
        data_access_set_guild_voice_channel_ids(guild_id, None)

        await interaction.response.send_message("Deleted all configuration for voice channels", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION)
    @commands.has_permissions(administrator=True)
    async def see_voice_channels(self, interaction: discord.Interaction):
        """Display the voice channels configured"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        voice_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_ids is None:
            print_warning_log(f"No voice channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Voice channel not set.", ephemeral=True)
            return
        names = []
        for voice_id in voice_ids:
            names.append(voice_id)

        names_txt = ", ".join(map(lambda x: "<#" + str(x) + ">", voice_ids))
        await interaction.followup.send(f"The voice channels are: {names_txt} ", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_schedule_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the daily schedule message will be sent
        """
        guild_id = interaction.guild.id
        data_access_set_guild_text_channel_id(guild_id, channel.id)

        await interaction.response.send_message(
            f"Confirmed to send a daily schedule message into #{channel.name}.",
            ephemeral=True,
        )
        await send_daily_question_to_a_guild(self.bot, interaction.guild)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_schedule_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_guild_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No schedule text channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Schedule text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The schedule text channel is <#{channel_id}>", ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModChannels(bot))
