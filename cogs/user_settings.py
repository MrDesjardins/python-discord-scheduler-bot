import discord
from discord.ext import commands
from discord import app_commands
from deps.data_access import data_access_get_member
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.values import COMMAND_GET_USER_TIME_ZONE, COMMAND_INIT_USER, COMMAND_SET_USER_TIME_ZONE
from deps.log import print_error_log
from ui.setup_user_profile_view import SetupUserProfileView
from ui.timezone_view import TimeZoneView


class UserSettings(commands.Cog):
    """User Settings commands"""

    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name=COMMAND_INIT_USER)
    async def setup_user(self, interaction: discord.Interaction):
        """Setup user account with permissions, roles and timezone"""
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("setup_user: No guild", ephemeral=True)
            return
        guild_id = guild.id
        member = await data_access_get_member(guild_id, interaction.user.id)

        if member is None:
            print_error_log(f"User {interaction.user.id} is not a member of the guild.")
            await interaction.response.send_message("You are not a member of the guild.", ephemeral=True)
            return

        view = SetupUserProfileView(self.bot, guild, member)
        await interaction.response.send_message(
            "Future commands, roles and permissions will be based on your profile. Please setup your profile.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SET_USER_TIME_ZONE)
    async def set_user_time_zone(self, interaction: discord.Interaction):
        """Command to set the user timezone"""
        await interaction.response.defer(ephemeral=True)
        # Create a view with the timezone options
        view = TimeZoneView(interaction.user.id)
        # Send a message with the buttons
        await interaction.followup.send("Please select a timezone:", view=view)

    @app_commands.command(name=COMMAND_GET_USER_TIME_ZONE)
    async def get_user_time_zone(self, interaction: discord.Interaction, member: discord.Member):
        """Get the timezone of a single user"""
        await interaction.response.defer(ephemeral=True)
        if member.id is None:
            await interaction.followup.send("User not found.", ephemeral=True)
            return
        user_info = await fetch_user_info_by_user_id(member.id)
        if user_info is None:
            await interaction.followup.send(f"User {member.display_name} has no timezone set.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"User {member.display_name} has timezone {user_info.time_zone}", ephemeral=True
            )


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserSettings(bot))
