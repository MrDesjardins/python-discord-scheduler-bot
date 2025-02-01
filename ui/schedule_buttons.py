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
            self.add_item(self.create_button(time))

    def create_button(self, label):
        """Creates a button with the given label and binds it to an interaction."""
        return discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=label)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Handles all button interactions."""
        try:
            await interaction.response.defer(ephemeral=True)
            custom_id = interaction.data["custom_id"]
            await adjust_reaction(self.guild_emoji, interaction, custom_id)
            # await interaction.response.send_message(f"You clicked {custom_id.upper()}!", ephemeral=True)
        except Exception as e:
            print_error_log(f"ScheduleButtons>An error occurred: {e}")
            traceback.print_exc()  # This prints the full error traceback
        return True
