"""
Buttons to vote for schedule times
"""

import traceback
from typing import Dict
import discord
from deps.functions_schedule import adjust_reaction
from deps.values import SUPPORTED_TIMES_ARR
from deps.log import print_error_log


class ScheduleButtons(discord.ui.View):
    """Buttons for the schedule"""

    def __init__(self, guild_emoji: dict[str, Dict[str, str]]):
        super().__init__()
        self.guild_emoji = guild_emoji
        self.schedule_times = SUPPORTED_TIMES_ARR

        for time in self.schedule_times:
            button = discord.ui.Button(label=time, style=discord.ButtonStyle.primary, custom_id=time)
            button.callback = self.button_callback  # Bind button to callback function
            self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        """Handles button clicks"""
        try:
            await interaction.response.defer(ephemeral=True)  # Prevents "This interaction failed"
            custom_id = interaction.data["custom_id"]
            await adjust_reaction(self.guild_emoji, interaction, custom_id)
        except Exception as e:
            print_error_log(f"ScheduleButtons>An error occurred: {e}")
            traceback.print_exc()  # Logs full traceback
