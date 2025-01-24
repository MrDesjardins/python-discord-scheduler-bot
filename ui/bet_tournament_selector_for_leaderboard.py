""" User interface for the bot"""

from typing import List
import discord
from discord.ui import View
from bet.bet_functions import generate_msg_bet_leaderboard
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.bet.bet_data_access import (
    data_access_get_all_wallet_for_tournament,
)
from deps.bet.bet_data_class import BetGame, BetUserGame, BetUserTournament
from deps.tournament_data_class import Tournament
from deps.values import COMMAND_BET
from deps.tournament_data_access import fetch_tournament_games_by_tournament_id


class BetTournamentSelectorForLeaderboard(View):
    """
    A view that allows to see every active bet for the tournament
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.tournament_id = None
        self.list_tournaments = list_tournaments

        # Dynamically add buttons for each tournament
        if (len(self.list_tournaments)) == 1:
            self.tournament_id = self.list_tournaments[0].id
        else:
            for tournament in self.list_tournaments:
                button = discord.ui.Button(label=tournament.name, custom_id=f"tournament_{tournament.id}")
                button.callback = self.create_button_callback(tournament.id)
                self.add_item(button)

    def create_button_callback(self, tournament_id: int):
        async def callback(interaction: discord.Interaction):
            """Handles button press for selecting a tournament."""
            # Remove all buttons
            for item in self.children:
                self.remove_item(item)
            tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
            msg = generate_msg_bet_leaderboard(tournament)
            if msg == "":
                msg = f"No user who betted on this tournament. Use the command `/{COMMAND_BET}` to place a bet."
            else:
                msg = f'Top betters tournament "**{tournament.name}**":\n\n' + msg
            # Update the interaction message with the new view
            await interaction.response.edit_message(
                content=msg,
                view=self,
            )

        return callback
