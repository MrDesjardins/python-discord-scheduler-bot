"""
Buttons to vote for schedule times
"""

from typing import Awaitable, Callable
import discord
from deps.values import SUPPORTED_TIMES_ARR

CallbackType = Callable[[dict[int, dict[str, str]], discord.Interaction, str], Awaitable[None]]


class TimeButton(discord.ui.Button):
    """A button that represent one hour of the day"""

    def __init__(self, label: str, callback, guild_emoji):
        super().__init__(label=label, style=discord.ButtonStyle.primary, custom_id=label)
        self.callback_func = callback
        self.guild_emoji = guild_emoji

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.callback_func(self.guild_emoji, interaction, self.custom_id)


class ScheduleButtons(discord.ui.View):
    """Represent the collection of buttons"""

    def __init__(self, guild_emoji: dict[int, dict[str, str]], callback: CallbackType) -> None:
        super().__init__(timeout=None)
        for time in SUPPORTED_TIMES_ARR:
            self.add_item(TimeButton(label=time, callback=callback, guild_emoji=guild_emoji))
