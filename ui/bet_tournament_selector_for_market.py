""" User interface for the bot"""

from typing import List, Optional
import discord
from discord.ui import Select, View
from deps.data_access import data_access_get_member
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.data_access_data_class import UserInfo
from deps.bet.bet_data_access import data_access_fetch_bet_games_by_tournament_id
from deps.bet.bet_functions import get_bet_user_wallet_for_tournament, place_bet_for_game
from deps.bet.bet_data_class import BetGame, BetUserTournament
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.log import print_error_log, print_warning_log
from deps.tournaments.tournament_data_access import fetch_tournament_games_by_tournament_id


class BetTournamentSelectorForMarket(View):
    """
    A view that allows the user to select the tournament to see the wallet amount.
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.tournament_id = None
        self.bet_game_id = None
        self.user_bet_on_id = None
        self.amount = None
        self.list_tournaments = list_tournaments
        self.bet_game_ui = None
        self.bet_user_selection_ui = None
        self.wallet: BetUserTournament = None
        self.message_id = None
        self.game_by_bet_game_id: dict[int, BetGame] = {}
        self.bet_game_by_bet_game_id: dict[int, BetGame] = {}
        self.bet_game_chosen: Optional[BetGame] = None
        self.game_chosen: Optional[TournamentGame] = None
        self.user_info1: Optional[UserInfo] = None
        self.user_info2: Optional[UserInfo] = None

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
            self.tournament_id = tournament_id
            if self.bet_game_id is None:
                self.wallet = get_bet_user_wallet_for_tournament(self.tournament_id, interaction.user.id)
                # 1 Get the tournament games
                tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

                # 2 Get the current bet_game for the tournament
                bet_games: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)
                self.game_by_bet_game_id = {game.tournament_game_id: game for game in bet_games}
                self.bet_game_by_bet_game_id = {game.id: game for game in bet_games}
                games_with_bet_game = [
                    game
                    for game in tournament_games
                    if game.id in self.game_by_bet_game_id and game.user_winner_id is None
                ]
                options: List[discord.SelectOption] = []
                for game in games_with_bet_game:
                    user_info1: Optional[UserInfo] = await fetch_user_info_by_user_id(game.user1_id)
                    user_info2: Optional[UserInfo] = await fetch_user_info_by_user_id(game.user2_id)
                    bet_game_for_game: Optional[BetGame] = self.game_by_bet_game_id.get(game.id, None)
                    if bet_game_for_game is None:
                        print_error_log(f"Bet game not found for game {game.id}")
                        continue
                    text_display = f"{user_info1.display_name} ({bet_game_for_game.odd_user_1():.2f}) vs {user_info2.display_name} ({bet_game_for_game.odd_user_2():.2f})"
                    options.append(discord.SelectOption(label=text_display, value=str(bet_game_for_game.id)))
                if len(options) == 0:
                    await interaction.response.send_message(
                        "No games available to bet in this tournament. Please try again later.", ephemeral=True
                    )
                    return

                # Disable all buttons
                for item in self.children:
                    item.disabled = True
                # 3 Add the select with the possible bet
                self.remove_item(self.bet_game_ui)
                self.bet_game_ui = Select(
                    placeholder="Bet:",
                    options=options,
                    custom_id="bet_game_ui",
                    min_values=1,
                    max_values=1,
                )
                self.bet_game_ui.callback = self.handle_bet_game_ui
                self.add_item(self.bet_game_ui)
                # Update the interaction message with the new view
                await interaction.response.edit_message(
                    content=f"Select one of the bets available in the market for this tournament. You have ${self.wallet.amount:.2f}",
                    view=self,
                )
            else:
                await interaction.response.defer()

        return callback

    async def handle_bet_game_ui(self, interaction: discord.Interaction):
        """Handles selection of the round lost."""
        try:
            # Safely access the selected values
            selected_values = interaction.data.get("values", [])
            if not selected_values:
                raise ValueError("No values found in interaction data.")

            self.bet_game_id = int(selected_values[0])  # Convert to int
        except Exception as e:
            print_error_log(f"bet_tournament_selector_for_market_handle_bet_game_ui: Error in handle_bet_game_ui: {e}")
            await interaction.response.send_message(
                "An error occurred while processing your selection.", ephemeral=True
            )
            return
        # Avoid responding multiple times
        if interaction.response.is_done():
            await interaction.followup.defer()
        else:
            await interaction.response.defer()
        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.bet_game_id is not None:
            if self.user_bet_on_id is None:
                # Add the select with the possible user to bet from the selected game bet
                self.bet_game_chosen = self.bet_game_by_bet_game_id.get(self.bet_game_id, None)
                self.game_chosen = next(
                    (
                        game
                        for game in fetch_tournament_games_by_tournament_id(self.tournament_id)
                        if game.id == self.bet_game_chosen.tournament_game_id
                    ),
                    None,
                )
                if self.bet_game_chosen is None or self.game_chosen is None:
                    print_error_log(f"Bet game not found for game {self.bet_game_id}")
                    return
                options: List[discord.SelectOption] = []
                self.user_info1 = await fetch_user_info_by_user_id(self.game_chosen.user1_id)
                self.user_info2 = await fetch_user_info_by_user_id(self.game_chosen.user2_id)
                options.append(
                    discord.SelectOption(
                        label=f"{self.user_info1.display_name} ({self.bet_game_chosen.odd_user_1():.2f})",
                        value=str(self.user_info1.id),
                    )
                )
                options.append(
                    discord.SelectOption(
                        label=f"{self.user_info2.display_name} ({self.bet_game_chosen.odd_user_2():.2f})",
                        value=str(self.user_info2.id),
                    )
                )
                # Disable the bet selection (select)
                for item in self.children:
                    self.remove_item(item)
                self.bet_user_selection_ui = Select(
                    placeholder="User",
                    options=options,
                    custom_id="bet_user_selection_ui",
                    min_values=1,
                    max_values=1,
                )
                self.bet_user_selection_ui.callback = self.handle_user_ui
                self.add_item(self.bet_user_selection_ui)
                # Update the interaction message with the new view
                await interaction.followup.send(
                    content=f"Select one of two participants. You have ${self.wallet.amount:.2f}",
                    view=self,
                    ephemeral=True,
                )

        return False

    async def handle_user_ui(self, interaction: discord.Interaction):
        """Handles selection of the round lost."""
        try:
            # Safely access the selected values
            selected_values = interaction.data.get("values", [])
            if not selected_values:
                raise ValueError("No values found in interaction data.")

            self.user_bet_on_id = int(selected_values[0])  # Convert to int
        except Exception as e:
            print_error_log(f"bet_tournament_selector_for_market_handle_bet_game_ui: Error in handle_bet_game_ui: {e}")
            await interaction.response.send_message(
                "An error occurred while processing your selection.", ephemeral=True
            )
            return
        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.bet_game_id is not None and self.user_bet_on_id is not None:
            # Disable all user selection
            for item in self.children:
                item.disabled = True
            modal = AmountModal(self)
            await interaction.response.send_modal(modal)
            return True
        return False


class AmountModal(discord.ui.Modal, title="Amount of money"):
    """Modal that allows text box for the user name"""

    def __init__(self, view: discord.ui.view):
        super().__init__()
        self.view = view  # Pass view to access the view's variables

        self.amount_ui = discord.ui.TextInput(
            label=f"Amount of money to bet (you have ${view.wallet.amount:.2f})",
            placeholder="Amount",
            custom_id="amount_bet_id",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.amount_ui)

    async def on_submit(self, interaction: discord.Interaction):
        """Save the modal input values back to the view"""
        try:
            self.view.amount = float(self.amount_ui.value)
        except ValueError as e:
            print_error_log(f"bet_tournament_selector_for_market_handle_bet_game_ui: AmountModal_on_submit: {e}")
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            return
        # Acknowledge the submission and close the modal
        await interaction.response.defer()  # This closes the modal after the submission

        try:
            place_bet_for_game(
                self.view.tournament_id,
                self.view.bet_game_id,
                interaction.user.id,
                self.view.amount,
                self.view.user_bet_on_id,
            )
        except ValueError as e:
            print_warning_log(f"bet_tournament_selector_for_market_handle_bet_game_ui: AmountModal_on_submit: {e}")
            await interaction.followup.send(f"An error occurred while placing the bet: {e}", ephemeral=True)
            return
        except Exception as e:
            print_error_log(f"bet_tournament_selector_for_market_handle_bet_game_ui: AmountModal_on_submit: {e}")
            await interaction.followup.send(
                "An error occurred while placing the bet. Please notify a moderator.", ephemeral=True
            )
            return
        # Send the follow-up message
        if self.view.user_info1 is not None and self.view.user_info2 is not None:

            member1 = await data_access_get_member(interaction.guild_id, self.view.user_info1.id)
            user1 = member1.mention if member1 else self.view.user_info1.display_name
            user1_odd = self.view.bet_game_chosen.odd_user_1()

            member2 = await data_access_get_member(interaction.guild_id, self.view.user_info2.id)
            user2 = member2.mention if member2 else self.view.user_info2.display_name
            user2_odd = self.view.bet_game_chosen.odd_user_2()

            user_bet_on = user1 if self.view.user_info1.id == self.view.user_bet_on_id else user2

            tournament_name = next(t for t in self.view.list_tournaments if t.id == self.view.tournament_id).name
            await interaction.followup.send(
                f'💰 {interaction.user.mention} bet **${self.view.amount:.2f}** on {user_bet_on} in the match {user1} ({user1_odd:.2f}) vs {user2} ({user2_odd:.2f}) in tournanent "{tournament_name}"',
                ephemeral=False,
            )
