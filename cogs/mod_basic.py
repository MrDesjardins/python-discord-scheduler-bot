"""
Basic moderator commands
"""

import io
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
    COMMAND_MOD_BOT_PERMISSION,
    COMMAND_TEST_JOIN,
    COMMAND_VERSION,
    COMMAND_RESET_CACHE,
    COMMAND_GUILD_ENABLE_BOT_VOICE,
    COMMAND_TEST_MATCH_START_GIF,
    MATCH_START_GIF_DELETE_AFTER_SECONDS,
)
from deps.functions import (
    get_sha,
)
from deps.data_access import (
    data_access_get_channel,
    data_access_get_custom_game_voice_channels,
    data_access_get_guild_voice_channel_ids,
    data_access_get_main_text_channel_id,
    data_access_reset_guild_cache,
    data_access_set_bot_voice_first_user,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_warning_log
from deps.siege import get_any_siege_activity
from deps.functions_stats import send_daily_stats_to_a_guild
from deps.match_start_gif import generate_match_start_gif
from deps.ai.ai_functions import BotAISingleton


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
                activity = get_any_siege_activity(member)
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

        msg = await BotAISingleton().generate_message_summary_matches_async(hours)
        if msg == "":
            await interaction.followup.send("Error while generating the summary", ephemeral=True)
            return
        # Split the message into chunks of 2000 characters
        chunks = [msg[i : i + 2000] for i in range(0, len(msg), 2000)]
        # Send each chunk as a separate message
        for chunk in chunks:
            await channel.send(content=chunk)
        await interaction.followup.send("Done", ephemeral=True)

    @app_commands.command(name=COMMAND_MOD_BOT_PERMISSION)
    @commands.has_permissions(administrator=True)
    async def mod_bot_permission(self, interaction: discord.Interaction):
        """
        Check the bot permissions in the server.
        """
        if interaction.guild is None:
            print_error_log(
                f"""mod_bot_permission: No guild available for user {interaction.user.display_name}({interaction.user.id})."""
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)
        bot_member = guild.me
        if bot_member is None:
            print_error_log(f"mod_bot_permission: Bot member not found in guild {guild.name}.")
            await interaction.followup.send("Bot member not found in this guild.", ephemeral=True)
            return
        permissions = bot_member.guild_permissions
        perm_list = [perm for perm, value in permissions if value]
        perm_str = "\n".join(perm_list)
        await interaction.followup.send(f"Bot permissions in this guild:\n{perm_str}", ephemeral=True)
        # Check for the 10-man custom game required permissions
        guild = interaction.guild
        guild_id = guild.id
        lobby_channel_id, team1_channel_id, team2_channel_id = await data_access_get_custom_game_voice_channels(
            guild_id
        )
        lobby_channel = await data_access_get_channel(lobby_channel_id)
        team1_channel = await data_access_get_channel(team1_channel_id)
        team2_channel = await data_access_get_channel(team2_channel_id)
        permissions_lobby = lobby_channel.permissions_for(bot_member)
        permissions_team1 = team1_channel.permissions_for(bot_member)
        permissions_team2 = team2_channel.permissions_for(bot_member)
        perm_list_lobby = [perm for perm, value in permissions_lobby if value]
        perm_list_team1 = [perm for perm, value in permissions_team1 if value]
        perm_list_team2 = [perm for perm, value in permissions_team2 if value]
        key = "move_members"
        await interaction.followup.send(
            f"Bot permissions to move members voice channels:\n"
            f"Lobby: {key in perm_list_lobby}\n"
            f"Team 1: {key in perm_list_team1}\n"
            f"Team 2: {key in perm_list_team2}",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_TEST_MATCH_START_GIF)
    @app_commands.describe(
        member1="First member",
        member2="Second member (optional)",
        member3="Third member (optional)",
        member4="Fourth member (optional)",
        member5="Fifth member (optional)",
    )
    @commands.has_permissions(administrator=True)
    async def test_match_start_gif(
        self,
        interaction: discord.Interaction,
        member1: discord.Member,
        member2: discord.Member = None,
        member3: discord.Member = None,
        member4: discord.Member = None,
        member5: discord.Member = None,
    ):
        """Test the match start GIF generation with specified members"""
        await interaction.response.defer(ephemeral=True)

        # Collect all provided members
        members = [m for m in [member1, member2, member3, member4, member5] if m is not None]

        if not members:
            await interaction.followup.send("❌ You must specify at least one member!", ephemeral=True)
            return

        try:
            # Get main text channel
            guild_id = interaction.guild_id
            text_channel_id = await data_access_get_main_text_channel_id(guild_id)
            text_channel = await data_access_get_channel(text_channel_id)

            if not text_channel:
                await interaction.followup.send(
                    "❌ Main text channel not configured! Use /modtextmainchannel first.", ephemeral=True
                )
                return

            # Generate GIF
            await interaction.followup.send(
                f"🎨 Generating match start GIF for {len(members)} member(s)...", ephemeral=True
            )

            gif_bytes = await generate_match_start_gif(members, guild_id, self.bot.guild_emoji.get(guild_id, {}))

            if not gif_bytes:
                await interaction.followup.send("❌ Failed to generate GIF!", ephemeral=True)
                return

            # Send to Discord with automatic deletion
            file = discord.File(fp=io.BytesIO(gif_bytes), filename="match_start_test.gif")
            await text_channel.send(
                f"🎮 **Test Match Start GIF** (triggered by {interaction.user.mention})\n"
                f"Players: {', '.join([m.mention for m in members])}",
                file=file,
                delete_after=MATCH_START_GIF_DELETE_AFTER_SECONDS,
            )

            await interaction.followup.send(
                f"✅ Match start GIF posted to {text_channel.mention}!\n"
                f"Generated for {len(members)} member(s). "
                f"(Auto-deletes after {MATCH_START_GIF_DELETE_AFTER_SECONDS // 60} minutes)",
                ephemeral=True,
            )

        except Exception as e:
            print_error_log(f"test_match_start_gif: Error: {e}")
            await interaction.followup.send(f"❌ Error generating GIF: {str(e)}", ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModBasic(bot))
