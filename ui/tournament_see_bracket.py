""" User interface for the bot"""

from typing import List
import discord
from discord.ui import View
from deps.tournaments.tournament_data_class import Tournament
from deps.tournaments.tournament_discord_actions import generate_bracket_file
from deps.log import print_error_log


class TournamentSeeBracket(View):
    """
    A view that allows the user to select a tournament to see the bracket
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.list_tournaments = list_tournaments

        # Dynamically add buttons for each tournament
        for tournament in self.list_tournaments:
            button = discord.ui.Button(label=tournament.name, custom_id=f"tournament_{tournament.id}")
            button.callback = self.create_button_callback(tournament.id)
            self.add_item(button)

    def create_button_callback(self, tournament_id: int):
        async def callback(interaction: discord.Interaction):
            """Callback function to handle button presses."""
            try:
                # Defer the response immediately to prevent timeout errors
                await interaction.response.defer()

                file = generate_bracket_file(tournament_id)
                await interaction.followup.send(file=file, ephemeral=False)
            except Exception as e:
                print_error_log(f"TournamentSeeBracket: (user id {interaction.user.id}) create_button_callback: {e}")
                await interaction.followup.send("An error occurred while generating the bracket.", ephemeral=True)

        return callback
