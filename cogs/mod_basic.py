"""
Basic moderator commands
"""

import discord
from discord.ext import commands
from discord import app_commands
from cogs.events import MyEventsCog
from deps.bot_common_actions import send_daily_question_to_a_guild
from deps.values import (
    COMMAND_DAILY_STATS,
    COMMAND_FORCE_SEND,
    COMMAND_GENERATE_AI_SUMMARY,
    COMMAND_GUILD_VOICE_CHANNEL_CURRENT_ACTIVITY,
    COMMAND_TEST_JOIN,
    COMMAND_VERSION,
    COMMAND_RESET_CACHE,
    COMMAND_GUILD_ENABLE_BOT_VOICE,
)
from deps.functions import (
    get_sha,
)
from deps.data_access import (
    data_access_get_channel,
    data_access_get_guild_voice_channel_ids,
    data_access_get_main_text_channel_id,
    data_access_reset_guild_cache,
    data_access_set_bot_voice_first_user,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_warning_log
from deps.siege import get_siege_activity
from deps.functions_stats import send_daily_stats_to_a_guild
from deps.ai.ai_functions import generate_message_summary_matches


class ModBasic(commands.Cog):
    """Basic moderator commands"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_VERSION)
    @commands.has_permissions(administrator=True)
    async def show_version(self, interaction: discord.Interaction):
        """Show the version of the bot"""
        await interaction.response.defer(ephemeral=True)
        sha = get_sha()
        await interaction.followup.send(f"Version: {sha}", ephemeral=True)

    @app_commands.command(name=COMMAND_RESET_CACHE)
    @commands.has_permissions(administrator=True)
    async def reset_cache(self, interaction: discord.Interaction):
        """
        An administrator can reset the cache for the guild
        """
        if interaction.guild is None:
            print_error_log(
                f"reset_cache: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        if interaction.user.id == guild.owner_id:
            data_access_reset_guild_cache(guild_id)
            await interaction.response.send_message("Cached flushed", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Only the owner of the guild can reset the cache",
                ephemeral=True,
            )

    @app_commands.command(name=COMMAND_GUILD_ENABLE_BOT_VOICE)
    @commands.has_permissions(administrator=True)
    async def enable_voice_bot(self, interaction: discord.Interaction, enable: bool):
        """Activate or deactivate the bot voice message"""
        if interaction.guild is None:
            print_error_log(
                f"enable_voice_bot: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        data_access_set_bot_voice_first_user(guild.id, enable)
        await interaction.response.send_message(f"The bot status to voice is {enable}", ephemeral=True)

    @app_commands.command(name=COMMAND_FORCE_SEND)
    @commands.has_permissions(administrator=True)
    async def force_send_daily(self, interaction: discord.Interaction):
        """Apply the schedule for user who scheduled using the /addschedule command"""
        if interaction.guild is None:
            print_error_log(
                f"force_send_daily: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)
        await send_daily_question_to_a_guild(self.bot, guild)
        await interaction.followup.send("Force sending", ephemeral=True)

    @app_commands.command(name=COMMAND_TEST_JOIN)
    @commands.has_permissions(administrator=True)
    async def test_join(self, interaction: discord.Interaction):
        """
        Simulate a member joining the server for local testing.
        """
        if interaction.guild is None:
            print_error_log(
                f"test_join: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        if interaction.user.id == guild.owner_id:
            fake_member = interaction.user  # Use the command invoker as the fake member
            cog = self.bot.cogs.get("MyEventsCog")
            if cog is None or not isinstance(cog, MyEventsCog) or not isinstance(fake_member, discord.Member):
                print_error_log("test_join: MyEventsCog not found. Skipping.")
                await interaction.response.send_message("MyEventsCog not found. Skipping.", ephemeral=True)
                return
            await cog.on_member_join(fake_member)

    @app_commands.command(name=COMMAND_GUILD_VOICE_CHANNEL_CURRENT_ACTIVITY)
    @commands.has_permissions(administrator=True)
    async def check_activity(self, interaction: discord.Interaction):
        """Apply the schedule for user who scheduled using the /addschedule command"""
        if interaction.guild is None:
            print_error_log(
                f"check_activity: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(interaction.guild.id)
        if voice_channel_ids is None:
            print_warning_log(f"check_activity:`Voice channel not set for guild {guild.name}. Skipping.")
            await interaction.followup.send("No voice channel found", ephemeral=True)
            return

        msg = []
        for voice_channel_id in voice_channel_ids:
            voice_channel = await data_access_get_channel(voice_channel_id)
            # voice_channel = discord.utils.get(interaction.guild.voice_channels, id=voice_channel_id)
            if voice_channel is None:
                print_warning_log(
                    f"check_activity: Voice channel configured but not found in the guild {guild.name}. Skipping."
                )
                continue
            for member in voice_channel.members:
                activity = get_siege_activity(member)
                if activity is not None:
                    msg.append(
                        f"{voice_channel.name} has {member.display_name} playing {activity.name} and {activity.details}"
                    )
        if len(msg) == 0:
            await interaction.followup.send("No activity found", ephemeral=True)
        else:
            msg_str = "\n".join(msg)
            await interaction.followup.send(msg_str, ephemeral=True)

    @app_commands.command(name=COMMAND_DAILY_STATS)
    @commands.has_permissions(administrator=True)
    async def send_stats_to_server(self, interaction: discord.Interaction, stats_id: int):
        """
        Send a specific stats to the server
        """
        if interaction.guild is None:
            print_error_log(
                f"""send_stats_to_server: No guild available for user {interaction.user.display_name}({interaction.user.id})."""
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)
        await send_daily_stats_to_a_guild(guild, stats_id)
        await interaction.followup.send(f"Generating stats for id {stats_id} completed!", ephemeral=True)

    @app_commands.command(name=COMMAND_GENERATE_AI_SUMMARY)
    async def generate_ai_summary(self, interaction: discord.Interaction, hours: int = 24):
        """
        Generate an AI summary of the matches.
        """
        if interaction.guild is None:
            print_error_log(
                f"""generate_ai_summary: No guild available for user {interaction.user.display_name}({interaction.user.id})."""
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            print_error_log("generate_ai_summary: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_main_text_channel_id(guild_id)
        if channel_id is None:
            print_error_log(
                f"\t⚠️ generate_ai_summary: Channel id (main text) not found for guild {guild.name}. Skipping."
            )
            return
        channel = await data_access_get_channel(channel_id)
        if channel is None:
            print_error_log(f"\t⚠️ generate_ai_summary: Channel not found for guild {guild.name}. Skipping.")
            return

        msg = generate_message_summary_matches(hours)
        if msg == "":
            await interaction.followup.send("Error while generating the summary", ephemeral=True)
            return
        # Split the message into chunks of 2000 characters
        chunks = [msg[i : i + 2000] for i in range(0, len(msg), 2000)]
        # Send each chunk as a separate message
        for chunk in chunks:
            await channel.send(content=chunk)
        await interaction.followup.send("Done", ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModBasic(bot))
