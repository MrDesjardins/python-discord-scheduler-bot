"""
Custom Discord UI components for handling command completion.
"""

from typing import Callable
import discord


class CompleteCommandView(discord.ui.View):
    def __init__(self, author_id: int, on_move_into_team_channels: Callable, on_move_back_lobby:Callable, timeout: int = 900):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.on_move_into_team_channels = on_move_into_team_channels
        self.on_move_back_lobby = on_move_back_lobby
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the invoker of the command can use this button.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Move to team channels", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Disable the button to prevent reuse
        button.disabled = True
        await interaction.response.edit_message(view=self)

        await self.on_move_into_team_channels()

    @discord.ui.button(label="Move back to lobby", style=discord.ButtonStyle.success)
    async def move_back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Disable the button to prevent reuse
        button.disabled = True
        await interaction.response.edit_message(view=self)

        await self.on_move_back_lobby()
        # Stop listening for interactions
        self.stop()