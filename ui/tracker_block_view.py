"""Button the bot owner presses after solving a tracker.gg challenge."""

import discord

from deps.tracker_pacing import clear_tracker_block


class TrackerBlockView(discord.ui.View):
    """
    Not registered as a persistent view: a restart forgets the cooldown this button
    would clear, so a button that stops working after a restart loses nothing.
    """

    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(label="Solved, retry now", style=discord.ButtonStyle.success)
    async def solved(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        """End the cooldown so the queued work resumes on its next cycle."""
        clear_tracker_block()
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            "tracker.gg requests are back on and will resume within a few minutes. "
            "I will DM you again if it is still blocking."
        )
