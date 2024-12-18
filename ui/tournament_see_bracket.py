""" User interface for the bot"""

import io
from typing import List
import discord
from discord.ui import View
from deps.tournament_data_class import Tournament, TournamentGame
from deps.tournament_functions import build_tournament_tree
from deps.log import print_warning_log
from deps.tournament_data_access import fetch_tournament_games_by_tournament_id
from deps.tournament_visualizer import plot_tournament_bracket


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
            # Fetch tournament and related data
            tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
            if not tournament:
                await interaction.response.send_message("Tournament not found.", ephemeral=True)
                return

            tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
            tournament_tree = build_tournament_tree(tournament_games)
            if tournament_tree is None:
                print_warning_log(
                    f"TournamentSeeBracket: Failed to build tournament tree for tournament {tournament_id}. Skipping."
                )
                await interaction.response.send_message("Failed to build tournament tree.", ephemeral=False)
                return

            # Generate the tournament bracket image
            img_bytes = plot_tournament_bracket(tournament, tournament_tree, False)
            bytesio = io.BytesIO(img_bytes)
            bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
            file = discord.File(fp=bytesio, filename="plot.png")
            await interaction.response.send_message(file=file, ephemeral=False)

        return callback
