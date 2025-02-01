from typing import List, Union
import discord
from discord.ext import commands
from discord import app_commands
from ui.schedule_day_hours_view import ScheduleDayHours
from deps.functions_schedule import auto_assign_user_to_daily_question
from deps.data_access import (
    data_access_get_channel,
    data_access_get_daily_message_id,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_message,
    data_access_get_users_auto_schedule,
    data_access_set_users_auto_schedule,
)
from deps.values import (
    COMMAND_SCHEDULE_ADD,
    COMMAND_SCHEDULE_APPLY,
    COMMAND_SCHEDULE_REMOVE,
    COMMAND_SCHEDULE_SEE,
    DAYS_OF_WEEK,
)
from deps.log import print_log, print_warning_log
from deps.models import DayOfWeek, SimpleUserHour
from deps.mybot import MyBot


class UserSchedule(commands.Cog):
    """User Settings commands"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_SCHEDULE_ADD)
    async def add_user_schedule(self, interaction: discord.Interaction):
        """
        Add a schedule for the active user who perform the command
        """
        view = ScheduleDayHours(self.bot.guild_emoji)

        await interaction.response.send_message(
            "Choose your day and hour. If you already have a schedule, this new one will add on top of the previous schedule with the new hours for the day choosen.",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_SCHEDULE_REMOVE)
    @app_commands.describe(day="The day of the week")
    async def remove_user_schedule(self, interaction: discord.Interaction, day: DayOfWeek):
        """
        Remove the schedule for the active user who perform the command
        """
        guild_id = interaction.guild_id
        day_str = day.value
        list_users: Union[List[SimpleUserHour] | None] = await data_access_get_users_auto_schedule(guild_id, day_str)
        if list_users is None:
            list_users = []
        my_list = list(filter(lambda x: x.simple_user.user_id != interaction.user.id, list_users))
        data_access_set_users_auto_schedule(guild_id, day_str, my_list)
        await interaction.response.send_message(f"Remove for {DAYS_OF_WEEK[day_str]}", ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_SEE)
    async def see_user_own_schedule(self, interaction: discord.Interaction):
        """
        Show the current schedule for the user
        """
        response = ""
        guild_id = interaction.guild_id
        for day, day_display in enumerate(DAYS_OF_WEEK):
            list_users: Union[List[SimpleUserHour] | None] = await data_access_get_users_auto_schedule(guild_id, day)
            print_log(list_users)
            if list_users is not None:
                for user_hour in list_users:
                    if user_hour.simple_user.user_id == interaction.user.id:
                        response += f"{day_display}: {user_hour.hour}\n"
        if response == "":
            response = f"No schedule found, uses the command /{COMMAND_SCHEDULE_ADD} to configure a recurrent schedule."

        await interaction.response.send_message(response, ephemeral=True)

    @app_commands.command(name=COMMAND_SCHEDULE_APPLY)
    @commands.has_permissions(administrator=True)
    async def apply_schedule(self, interaction: discord.Interaction):
        """
        Apply the schedule for user who scheduled using the /addschedule command
        Should not have to use it, but admin can trigger the sync
        """
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No text channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Text channel not set.", ephemeral=True)
            return

        channel: discord.TextChannel = await data_access_get_channel(channel_id)
        last_message_id = await data_access_get_daily_message_id(guild_id)
        if last_message_id is None:
            print_warning_log(f"No message found in the channel {channel.name}. Skipping.")
            await interaction.followup.send(f"Cannot find a schedule message #{channel.name}.", ephemeral=True)
        last_message = await data_access_get_message(guild_id, channel_id, last_message_id)
        if last_message is None:
            print_warning_log(f"Cannot find a message id {last_message_id} in the channel {channel.name}. Skipping.")
            await interaction.followup.send(f"Cannot find a schedule message in #{channel.name}.", ephemeral=True)
            return
        await auto_assign_user_to_daily_question(guild_id, channel_id, last_message)

        await interaction.followup.send(f"Update message in #{channel.name}.", ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserSchedule(bot))
