import discord
from discord.ext import commands
from discord import app_commands
from deps.bot_common_actions import send_daily_question_to_a_guild
from deps.values import (
    COMMAND_FORCE_SEND,
    COMMAND_TEST_JOIN,
    COMMAND_VERSION,
    COMMAND_RESET_CACHE,
    COMMAND_GUILD_ENABLE_BOT_VOICE,
)
from deps.functions import (
    get_sha,
)
from deps.data_access import (
    data_access_reset_guild_cache,
    data_access_set_bot_voice_first_user,
)
from deps.mybot import MyBot


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
        # perms = interaction.channel.permissions_for(interaction.user)
        # print_log(f"User {interaction.author.id} has permissions {perms}")
        if interaction.user.id == interaction.guild.owner_id:
            guild_id = interaction.guild.id
            data_access_reset_guild_cache(guild_id)
            await interaction.response.send_message("Cached flushed", ephemeral=True)
        else:
            await interaction.response.send_message("Only the owner of the guild can reset the cache", ephemeral=True)

    @app_commands.command(name=COMMAND_GUILD_ENABLE_BOT_VOICE)
    @commands.has_permissions(administrator=True)
    async def enable_voice_bot(self, interaction: discord.Interaction, enable: bool):
        """Activate or deactivate the bot voice message"""
        data_access_set_bot_voice_first_user(interaction.guild.id, enable)
        await interaction.response.send_message(f"The bot status to voice is {enable}", ephemeral=True)

    @app_commands.command(name=COMMAND_FORCE_SEND)
    @commands.has_permissions(administrator=True)
    async def force_send_daily(self, interaction: discord.Interaction):
        """Apply the schedule for user who scheduled using the /addschedule command"""
        await interaction.response.defer(ephemeral=True)
        await send_daily_question_to_a_guild(self.bot, interaction.guild, True)
        await interaction.followup.send("Force sending", ephemeral=True)

    @app_commands.command(name=COMMAND_TEST_JOIN)
    @commands.has_permissions(administrator=True)
    async def test_join(self, interaction: discord.Interaction):
        """
        Simulate a member joining the server for local testing.
        """
        if interaction.user.id == interaction.guild.owner_id:
            fake_member = interaction.user  # Use the command invoker as the fake member
            await self.bot.cogs.get("MyEventsCog").on_member_join(fake_member)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModBasic(bot))
