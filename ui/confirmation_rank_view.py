import discord


class ConfirmCancelView(discord.ui.View):
    """
    Confirmation view with Confirm and Cancel buttons.

    Usage:
    view = ConfirmCancelView()
    await view.wait()
    if view.result is None:
        # Nothing happened
    elif view.result:
        # User confirmed and value io True or False
    """

    def __init__(self):
        super().__init__()
        self.result = None  # This will store the user's response

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm button action"""
        self.result = True
        self.disable_all_buttons()  # Disable all buttons
        await interaction.response.edit_message(view=self)  # Update the message to reflect disabled buttons
        self.stop()  # Stop the view to proceed

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel button action"""
        self.result = False
        self.disable_all_buttons()  # Disable all buttons
        await interaction.response.edit_message(view=self)  # Update the message to reflect disabled buttons
        self.stop()  # Stop the view to end interaction

    def disable_all_buttons(self):
        """Helper method to disable all buttons in the view."""
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
