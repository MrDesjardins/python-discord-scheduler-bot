import discord
from discord.ext import commands
from discord import app_commands
from deps.bot_common_actions import send_session_stats, update_vote_message
from deps.data_access import (
    data_access_get_guild_text_channel_id,
    data_access_get_message,
    data_access_get_reaction_message,
    data_access_set_reaction_message,
    data_access_get_member,
)
from deps.analytic_data_access import data_access_set_ubisoft_username_active, data_access_set_ubisoft_username_max
from deps.values import (
    COMMAND_SCHEDULE_ADD_USER,
    COMMAND_SET_USER_TIME_ZONE_OTHER_USER,
    COMMAND_SET_USER_MAX_RANK_ACCOUNT_OTHER_USER,
    COMMAND_SET_USER_ACTIVE_ACCOUNT_OTHER_USER,
    COMMAND_STATS_MATCHES,
)
from ui.timezone_view import TimeZoneView
from deps.mybot import MyBot
from deps.models import SimpleUser
from deps.functions import get_empty_votes, get_last_schedule_message, get_time_choices
from deps.siege import get_user_rank_emoji


class ModeratorOnUserBehalf(commands.Cog):
    """Moderator commands that act on behalf of the user"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @commands.has_permissions(administrator=True)
    @app_commands.command(name=COMMAND_SET_USER_TIME_ZONE_OTHER_USER)
    async def set_user_time_zone_for_other_user(self, interaction: discord.Interaction, member: discord.Member):
        """Command to set the user timezone"""
        await interaction.response.defer(ephemeral=True)
        # Create a view with the timezone options
        view = TimeZoneView(member.id)
        # Send a message with the buttons
        await interaction.followup.send("Please select a timezone:", view=view)

    @commands.has_permissions(administrator=True)
    @app_commands.command(name=COMMAND_SET_USER_MAX_RANK_ACCOUNT_OTHER_USER)
    async def set_user_ubisoft_max_rank_for_other_user(
        self, interaction: discord.Interaction, member: discord.Member, ubisoft_username: str
    ):
        """Command to set the user Ubisoft username"""
        await interaction.response.defer(ephemeral=True)

        data_access_set_ubisoft_username_max(interaction.user.id, ubisoft_username)
        await interaction.followup.send(f"Max Account for {member.mention} -> `{ubisoft_username}`", ephemeral=True)

    @commands.has_permissions(administrator=True)
    @app_commands.command(name=COMMAND_SET_USER_ACTIVE_ACCOUNT_OTHER_USER)
    async def set_user_ubisoft_active_account_for_other_user(
        self, interaction: discord.Interaction, member: discord.Member, ubisoft_username: str
    ):
        """Command to set the user Ubisoft username"""
        await interaction.response.defer(ephemeral=True)

        data_access_set_ubisoft_username_active(interaction.user.id, ubisoft_username)
        await interaction.followup.send(f"Active Account for {member.mention} -> `{ubisoft_username}`", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_ADD_USER)
    @commands.has_permissions(administrator=True)
    @app_commands.choices(time_voted=get_time_choices())
    async def set_schedule_user_today(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        time_voted: app_commands.Choice[str],
    ):
        """
        An administrator can assign a user to a specific time for the current day
        """

        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel: discord.TextChannel = data_access_get_guild_text_channel_id(guild_id)
        channel_id = channel.id

        last_message = await get_last_schedule_message(self.bot, channel)
        if last_message is None:
            await interaction.followup.send("No messages found in this channel.", ephemeral=True)
            return
        message_id = last_message.id
        message: discord.Message = await data_access_get_message(guild_id, channel_id, message_id)
        message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
        if not message_votes:
            message_votes = get_empty_votes()

        simple_user = SimpleUser(
            member.id,
            member.display_name,
            get_user_rank_emoji(self.bot.guild_emoji.get(guild_id), member),
        )
        message_votes[time_voted.value].append(simple_user)

        # Always update the cache
        data_access_set_reaction_message(guild_id, channel_id, message_id, message_votes)

        await update_vote_message(message, message_votes)
        await interaction.followup.send("User added", ephemeral=True)

    @app_commands.command(name=COMMAND_STATS_MATCHES)
    @commands.has_permissions(administrator=True)
    async def mod_stats(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        """Show the statistics for the moderator"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        member = await data_access_get_member(guild_id, member.id)
        res = await send_session_stats(member, guild_id, mod_call_function=True)
        if res is None:
            await interaction.followup.send("No stats available", ephemeral=True)
        else:
            await interaction.delete_original_response()


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModeratorOnUserBehalf(bot))
