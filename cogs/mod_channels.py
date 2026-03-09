"""
Moderator command to set specific channels for the bot to interact with
"""

import discord
from discord.ext import commands
from discord import app_commands
from deps.bot_common_actions import send_daily_question_to_a_guild
from deps.data_access import (
    data_access_get_ai_text_channel_id,
    data_access_get_gaming_session_text_channel_id,
    data_access_get_guild_private_channel_category_id,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_guild_username_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_main_text_channel_id,
    data_access_get_new_user_text_channel_id,
    data_access_set_ai_text_channel_id,
    data_access_set_custom_game_voice_channels,
    data_access_set_gaming_session_text_channel_id,
    data_access_set_guild_private_channel_category_id,
    data_access_set_guild_username_text_channel_id,
    data_access_set_main_text_channel_id,
    data_access_set_new_user_text_channel_id,
    data_access_set_guild_schedule_text_channel_id,
    data_access_set_guild_voice_channel_ids,
)
from deps.values import (
    COMMAND_CHANNEL_GET_MAIN_CHANNEL,
    COMMAND_CHANNEL_SET_MAIN_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION,
    COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION,
    COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL,
    COMMAND_SEE_CUSTOM_GAME_VOICE_CHANNELS,
    COMMAND_SEE_GAMING_SESSION_CHANNEL,
    COMMAND_SET_CUSTOM_GAME_VOICE_CHANNELS,
    COMMAND_SET_GAMING_SESSION_CHANNEL,
    COMMAND_SEE_NEW_USER_CHANNEL,
    COMMAND_SET_NEW_USER_CHANNEL,
    COMMAND_CHANNEL_SET_AI_CHANNEL,
    COMMAND_CHANNEL_GET_AI_CHANNEL,
    COMMAND_SET_PRIVATE_CHANNEL_CATEGORY,
    COMMAND_SEE_PRIVATE_CHANNEL_CATEGORY,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_warning_log


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
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_guild_username_text_channel_id(guild_id, channel.id)
        await interaction.followup.send(
            f"Confirmed to send a user name message into #{channel.name}.",
            ephemeral=True,
        )

    @commands.has_permissions(administrator=True)
    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL)
    async def see_username_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_guild_username_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No username text channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("Username Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The username text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_SET_GAMING_SESSION_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_gaming_session_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the user name is shown
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_gaming_session_text_channel_id(guild_id, channel.id)

        await interaction.followup.send(
            f"Confirmed to send user gaming session stats into #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SEE_GAMING_SESSION_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_gaming_session_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_gaming_session_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No gaming session stats channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("Gaming Session Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(
            f"The gaming session text channel is <#{channel_id}>",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SET_NEW_USER_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_new_user_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the user name is shown
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_new_user_text_channel_id(guild_id, channel.id)

        await interaction.followup.send(
            f"Confirmed to send new user message into #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SEE_NEW_USER_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_new_user_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_new_user_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No new user channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("New User Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The new user text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_voice_channels(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        """
        Set the voice channels to listen to the users in the voice channel
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_channel_ids is None:
            voice_channel_ids = []

        if channel.id not in voice_channel_ids:
            voice_channel_ids.append(channel.id)
        data_access_set_guild_voice_channel_ids(guild_id, voice_channel_ids)
        await interaction.followup.send(
            f"The bot will check the voice channel #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION)
    @commands.has_permissions(administrator=True)
    async def reset_voice_channels(self, interaction: discord.Interaction):
        """
        Set the voice channels to listen to the users in the voice channel
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_guild_voice_channel_ids(guild_id, None)

        await interaction.followup.send("Deleted all configuration for voice channels", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION)
    @commands.has_permissions(administrator=True)
    async def see_voice_channels(self, interaction: discord.Interaction):
        """
        Display the voice channels configured
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        voice_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_ids is None:
            print_warning_log(f"No voice channel in guild {guild.name}. Skipping.")
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
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_guild_schedule_text_channel_id(guild_id, channel.id)

        await interaction.followup.send(
            f"Confirmed to send a daily schedule message into #{channel.name}.",
            ephemeral=True,
        )
        await send_daily_question_to_a_guild(self.bot, guild)

    @app_commands.command(name=COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_schedule_text_channel(self, interaction: discord.Interaction):
        """
        Display the text channel configured
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No schedule text channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("Schedule text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The schedule text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_CHANNEL_SET_MAIN_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_main_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the daily schedule message will be sent
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_main_text_channel_id(guild_id, channel.id)

        await interaction.followup.send(
            f"Confirmed to send main interaction message into #{channel.name}.",
            ephemeral=True,
        )
        await send_daily_question_to_a_guild(self.bot, guild)

    @app_commands.command(name=COMMAND_CHANNEL_GET_MAIN_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_main_text_channel(self, interaction: discord.Interaction):
        """
        Display the text channel configured
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_main_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No main text channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("Main text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The main text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_CHANNEL_SET_AI_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_ai_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the daily schedule message will be sent
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("set_ai_text_channel: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_ai_text_channel_id(guild_id, channel.id)

        await interaction.followup.send(
            f"Confirmed to send main interaction message into #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_CHANNEL_GET_AI_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_ai_text_channel(self, interaction: discord.Interaction):
        """
        Display the text channel configured
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("see_ai_text_channel: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_ai_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No AI text channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("AI text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The AI text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_SET_CUSTOM_GAME_VOICE_CHANNELS)
    @commands.has_permissions(administrator=True)
    async def set_custom_game_voice_channels(
        self,
        interaction: discord.Interaction,
        lobby: discord.VoiceChannel,
        team1: discord.VoiceChannel,
        team2: discord.VoiceChannel,
    ):
        """
        An administrator can set the channel where custom game happen
        """
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("set_custom_game_voice_channels: Guild is None.")
            return
        guild_id = guild.id
        data_access_set_custom_game_voice_channels(guild_id, lobby.id, team1.id, team2.id)

        await interaction.followup.send(
            f"Confirmed that the lobby voice channel is #{lobby.name} and team channels are #{team1.name} and #{team2.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SEE_CUSTOM_GAME_VOICE_CHANNELS)
    @commands.has_permissions(administrator=True)
    async def see_custom_game_voice_channels(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_new_user_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No new user channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("New User Text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The new user text channel is <#{channel_id}>", ephemeral=True)


    @app_commands.command(name=COMMAND_SET_PRIVATE_CHANNEL_CATEGORY)
    @commands.has_permissions(administrator=True)
    async def set_private_channel_category(self, interaction: discord.Interaction, category: discord.CategoryChannel):
        """Set the category where private voice channels will be created"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("set_private_channel_category: Guild is None.")
            return
        data_access_set_guild_private_channel_category_id(guild.id, category.id)
        await interaction.followup.send(
            f"Private voice channels will be created under the **{category.name}** category.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SEE_PRIVATE_CHANNEL_CATEGORY)
    @commands.has_permissions(administrator=True)
    async def see_private_channel_category(self, interaction: discord.Interaction):
        """Display the category configured for private voice channels"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("see_private_channel_category: Guild is None.")
            return
        category_id = await data_access_get_guild_private_channel_category_id(guild.id)
        if category_id is None:
            print_warning_log(f"No private channel category in guild {guild.name}. Skipping.")
            await interaction.followup.send("Private channel category not set.", ephemeral=True)
            return

        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                f"Configured category <#{category_id}> no longer exists. Please reconfigure it.", ephemeral=True
            )
            return

        lines = [f"Private channels are created under **{category.name}** (<#{category_id}>).\n"]
        if guild.me is not None:
            perms = category.permissions_for(guild.me)
            def status(ok: bool) -> str:
                return "✅" if ok else "❌"
            lines.append("**Bot permissions in that category:**")
            lines.append(f"{status(perms.manage_channels)} Manage Channels (required to create channels)")
            lines.append(f"{status(perms.manage_roles)} Manage Roles (required to set per-member permissions)")
            lines.append(f"{status(perms.connect)} Connect")
            lines.append(f"{status(perms.move_members)} Move Members (required to auto-move the creator)")
            if not perms.manage_channels or not perms.manage_roles:
                lines.append(
                    "\n⚠️ One or more required permissions are missing. "
                    "Go to the category → Edit → Permissions → add the bot's role and grant the missing ones."
                )
        await interaction.followup.send("\n".join(lines), ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModChannels(bot))
