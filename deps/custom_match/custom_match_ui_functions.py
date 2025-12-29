"""
Custom Discord UI components for handling command completion.
"""

from typing import Callable
import discord


class CompleteCommandView(discord.ui.View):
    def __init__(self, author_id: int, on_complete: Callable, timeout: int = 900):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.on_complete = on_complete

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the invoker of the command can use this button.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Complete", style=discord.ButtonStyle.success)
    async def complete(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        # Disable the button to prevent reuse
        button.disabled = True
        await interaction.response.edit_message(view=self)

        await self.on_complete()
        # Stop listening for interactions
        self.stop()
