""" User interface for the bot"""

from typing import List
import discord
from discord.ui import View
from deps.tournament_data_class import Tournament
from deps.tournament_functions import register_for_tournament
from deps.log import print_error_log


class TournamentRegistration(View):
    """
    A view that allows the user to register to a tournament
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.list_tournaments = list_tournaments

        for t in self.list_tournaments:
            self.add_item(discord.ui.Button(label=t.name, custom_id=str(t.id)))

        self.first_response = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Callback function to check if the interaction is valid"""

        # Save user responses
        tournament_id = int(interaction.data["custom_id"])
        register_for_tournament(tournament_id, interaction.user.id)

        # Find the tournament from the id variable in the list of tournament to get the starting date
        tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
        if not tournament:
            print_error_log(f"Tournament not found for id {self.list_tournaments}")
            return False

        date_start = tournament.start_date.strftime("%Y-%m-%d")
        # Send final confirmation message with the saved data
        await interaction.followup.send(
            f"You are registered. Please be patient and a new message will tag you when the tournament start ({date_start}).",
            ephemeral=True,
        )
        return True
