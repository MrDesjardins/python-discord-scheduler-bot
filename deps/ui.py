""" User interface for the bot"""

import discord
from discord.ui import Select, View
from deps.data_access import data_access_set_users_auto_schedule
from deps.models import SimpleUser, SimpleUserHour
from deps.siege import get_user_rank_emoji
from deps.values import COMMAND_SCHEDULE_REMOVE, COMMAND_SCHEDULE_SEE, DAYS_OF_WEEK
from deps.functions import get_supported_time_time_label


class FormDayHours(View):
    """
    A view that combines two selects for the user to answer two questions
    """

    def __init__(self):
        super().__init__()

        # First question select menu
        self.first_select = Select(
            placeholder="Days of the weeks:",
            options=[
                discord.SelectOption(value="0", label=DAYS_OF_WEEK[0]),
                discord.SelectOption(value="1", label=DAYS_OF_WEEK[1]),
                discord.SelectOption(value="2", label=DAYS_OF_WEEK[2]),
                discord.SelectOption(value="3", label=DAYS_OF_WEEK[3]),
                discord.SelectOption(value="4", label=DAYS_OF_WEEK[4]),
                discord.SelectOption(value="5", label=DAYS_OF_WEEK[5]),
                discord.SelectOption(value="6", label=DAYS_OF_WEEK[6]),
            ],
            custom_id="in_days",
            min_values=1,
            max_values=7,
        )
        self.add_item(self.first_select)

        self.second_select = Select(
            placeholder="Time of the Day:",
            options=list(
                map(
                    lambda x: discord.SelectOption(value=x.value, label=x.label, description=x.description),
                    get_supported_time_time_label(),
                )
            ),
            custom_id="in_hours",
            min_values=1,
            max_values=12,
        )
        self.add_item(self.second_select)
        # Track if both selects have been answered
        self.first_response = None
        self.second_response = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Callback function to check if the interaction is valid"""
        # Capture the response for the fruit question
        if interaction.data["custom_id"] == "in_days":
            self.first_response = self.first_select.values
            await interaction.response.send_message("Days Saved", ephemeral=True)

        # Capture the response for the color question
        elif interaction.data["custom_id"] == "in_hours":
            self.second_response = self.second_select.values
            await interaction.response.send_message("Hours Saved", ephemeral=True)

        # If both responses are present, finalize the interaction
        if self.first_response and self.second_response:
            # Save user responses
            simple_user = SimpleUser(
                interaction.user.id, interaction.user.display_name, get_user_rank_emoji(interaction.user)
            )

            for day in self.first_response:
                list_users = []
                for hour in self.second_response:
                    list_users.append(SimpleUserHour(simple_user, hour))
                data_access_set_users_auto_schedule(interaction.guild_id, day, list_users)

            # Send final confirmation message with the saved data
            await interaction.followup.send(
                f"Your schedule has been saved. You can see your schedule with /{COMMAND_SCHEDULE_SEE} or remove it with /{COMMAND_SCHEDULE_REMOVE}",
                ephemeral=True,
            )
            return True

        return False
