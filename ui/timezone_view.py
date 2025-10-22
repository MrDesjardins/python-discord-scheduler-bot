"""UI for the user to pick a timezone"""

import discord
from deps.analytic_data_access import data_access_set_usertimezone
from deps.values import valid_time_zone_options


class TimeZoneButton(discord.ui.Button):
    """Button to select a single timezone"""

    def __init__(self, label: str, custom_id: str, user_id: int):
        """Button to select a timezone"""
        super().__init__(label=label, custom_id=custom_id)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        """Action for the timezone button"""
        await interaction.response.send_message(f"You selected: {self.custom_id}", ephemeral=True)
        # Call your data access function here
        if self.custom_id is not None:
            data_access_set_usertimezone(self.user_id, self.custom_id)


class TimeZoneView(discord.ui.View):
    """View for the user to pick a timezone"""

    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id

        # Add a button for each timezone
        for option in valid_time_zone_options:
            self.add_item(TimeZoneButton(label=option, custom_id=option, user_id=self.user_id))
