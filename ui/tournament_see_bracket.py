""" User interface for the bot"""

from typing import List
import discord
from discord.ui import View
from deps.tournament_data_class import Tournament
from deps.tournament_discord_actions import generate_bracket_file


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
            file = generate_bracket_file(tournament_id)
            await interaction.response.send_message(file=file, ephemeral=False)

        return callback
