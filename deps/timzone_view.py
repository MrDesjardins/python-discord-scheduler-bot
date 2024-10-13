import discord
from discord.ext import commands

from deps.analytic_data_access import data_access_set_usertimezone


class TimeZoneButton(discord.ui.Button):
    def __init__(self, label, custom_id, user_id):
        super().__init__(label=label, custom_id=custom_id)
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"You selected: {self.custom_id}", ephemeral=True)
        # Call your data access function here
        data_access_set_usertimezone(self.user_id, self.custom_id)


class TimeZoneView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__()
        self.user_id = user_id
        valid_time_zone_options = [
            "US/Pacific",
            "US/Central",
            "US/Eastern",
        ]
        for option in valid_time_zone_options:
            self.add_item(TimeZoneButton(label=option, custom_id=option, user_id=self.user_id))
