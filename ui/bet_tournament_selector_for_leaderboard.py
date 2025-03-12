""" User interface for the bot"""

import traceback
from typing import List
import discord
from discord.ui import View
from deps.bet.bet_functions import generate_msg_bet_leaderboard
from deps.tournaments.tournament_data_class import Tournament
from deps.values import COMMAND_BET
from deps.log import print_error_log


class BetTournamentSelectorForLeaderboard(View):
    """
    A view that allows to see every active bet for the tournament
    """

    def __init__(self, list_tournaments: List[Tournament]) -> None:
        super().__init__()
        self.tournament_id = None
        self.list_tournaments = list_tournaments

        # Dynamically add buttons for each tournament
        for tournament in self.list_tournaments:
            if tournament.id is not None:
                button: discord.ui.Button = discord.ui.Button(
                    label=tournament.name, custom_id=f"tournament_{tournament.id}"
                )
                # Use partial to create a callback with the tournament_id argument fixed
                button.callback = lambda interaction, tid=tournament.id: self.create_button_callback(tid)(interaction)
                self.add_item(button)

    def create_button_callback(self, tournament_id: int):
        """
        Create a new button for each tournament
        """

        async def callback(interaction: discord.Interaction):
            """Handles button press for selecting a tournament."""
            try:
                await interaction.response.defer()
                if interaction.message is None:
                    print_error_log(
                        "BetTournamentSelectorForLeaderboard>callback: The interaction must be done on a message."
                    )
                    return
                # Remove all buttons
                for item in self.children:
                    self.remove_item(item)
                tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
                if tournament is None:
                    msg = "Tournament not found."
                else:
                    msg = await generate_msg_bet_leaderboard(tournament)
                    if msg == "":
                        msg = f"No user who betted on this tournament. Use the command `/{COMMAND_BET}` to place a bet."
                    else:
                        msg = f'Top betters tournament "**{tournament.name}**":\n\n' + msg
                        # Update the interaction message with the new view
                        await interaction.followup.edit_message(
                            message_id=interaction.message.id,
                            content=msg,
                            view=self,
                        )
            except Exception as e:
                print_error_log(f"BetTournamentSelectorForLeaderboard>An error occurred: {e}")
                traceback.print_exc()  # This prints the full error traceback
                await interaction.followup.send(
                    "An unexpected error occurred. Please contact a moderator.", ephemeral=True
                )

        return callback
