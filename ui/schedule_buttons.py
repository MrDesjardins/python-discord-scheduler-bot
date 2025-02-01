"""
Buttons to vote for schedule times
"""

from typing import Dict
import discord
from deps.functions_schedule import adjust_reaction
from deps.values import SUPPORTED_TIMES_ARR


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
        await interaction.response.defer()
        custom_id = interaction.data["custom_id"]
        await adjust_reaction(self.guild_emoji, interaction, custom_id)
        # await interaction.response.send_message(f"You clicked {custom_id.upper()}!", ephemeral=True)
        return True
