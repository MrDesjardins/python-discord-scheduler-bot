""" User interface for the bot"""

import traceback
from typing import List
import discord
from discord.ui import View
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.bet.bet_data_access import (
    data_access_fetch_bet_games_by_tournament_id,
    data_access_fetch_bet_user_game_by_tournament_id,
)
from deps.bet.bet_data_class import BetGame, BetUserGame
from deps.tournaments.tournament_data_class import Tournament
from deps.values import COMMAND_BET
from deps.tournaments.tournament_data_access import fetch_tournament_games_by_tournament_id
from deps.log import print_error_log


class BetTournamentSelectorForActiveMarket(View):
    """
    A view that allows to see every active bet for the tournament
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.tournament_id = None
        self.list_tournaments = list_tournaments

        # Dynamically add buttons for each tournament
        # if (len(self.list_tournaments)) == 1:
        #     self.tournament_id = self.list_tournaments[0].id
        # else:
        for tournament in self.list_tournaments:
            button = discord.ui.Button(label=tournament.name, custom_id=f"tournament_{tournament.id}")
            button.callback = self.create_button_callback(tournament.id)
            self.add_item(button)

    def create_button_callback(self, tournament_id: int):
        async def callback(interaction: discord.Interaction):
            """Handles button press for selecting a tournament."""
            try:
                await interaction.response.defer()
                # Remove all buttons
                for item in self.children:
                    self.remove_item(item)

                # 2 Get the current bet_game for the tournament
                bet_games: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)

                # 3 Get all the bets for the tournament
                bet_user_games: List[BetUserGame] = data_access_fetch_bet_user_game_by_tournament_id(tournament_id)

                # 4 Get all tournament game
                tournament_games = fetch_tournament_games_by_tournament_id(tournament_id)

                # Filter the game to have only the one not distributed
                bet_user_games = [bet for bet in bet_user_games if not bet.bet_distributed]
                # Fast access
                bet_game_dict = {game.id: game for game in bet_games}
                tournament_games_dict = {game.id: game for game in tournament_games}

                tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
                msg = ""

                for bet in bet_user_games:
                    bet_game = bet_game_dict.get(bet.bet_game_id, None)
                    if bet_game is not None:
                        tournament_game = tournament_games_dict.get(bet_game.tournament_game_id, None)
                        if tournament_game is not None:

                            member1 = await fetch_user_info_by_user_id(tournament_game.user1_id)
                            user1_display = member1.display_name if member1 else tournament_game.user1_id
                            user1_odd = bet_game.odd_user_1()

                            member2 = await fetch_user_info_by_user_id(tournament_game.user2_id)
                            user2_display = member2.display_name if member2 else tournament_game.user2_id
                            user2_odd = bet_game.odd_user_2()

                            user_who_put_the_bed_id = bet.user_id
                            member3 = await fetch_user_info_by_user_id(user_who_put_the_bed_id)
                            user3_display = member3.display_name if member3 else user_who_put_the_bed_id

                            user_on_who_the_bed_is_on = (
                                user1_display if bet.user_id_bet_placed == tournament_game.user1_id else user2_display
                            )

                            msg += f"💰 `{user3_display}` placed a bet of **${bet.amount:.2f}** on `{user_on_who_the_bed_is_on}` in the game of `{user1_display} ({user1_odd:.2f})` vs `{user2_display} ({user2_odd:.2f})`\n"

                if msg == "":
                    msg = f"No active bet for this tournament. Use the command `/{COMMAND_BET}` to place a bet."
                else:
                    msg = f'Active bet for the tournament "**{tournament.name}**":\n\n' + msg
                # Update the interaction message with the new view
                await interaction.followup.edit_message(
                    message_id=interaction.message.id,
                    content=msg,
                    view=self,
                )
            except Exception as e:
                print_error_log(f"BetTournamentSelectorForActiveMarket>An error occurred: {e}")
                traceback.print_exc()  # This prints the full error traceback
                await interaction.followup.send(
                    "An unexpected error occurred. Please contact a moderator.", ephemeral=True
                )

        return callback
