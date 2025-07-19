"""User interface for the bot"""

import math
import traceback
from typing import List, Optional, Union
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
from deps.tournaments.tournament_data_access import (
    data_access_get_team_labels,
    fetch_tournament_games_by_tournament_id,
)


class BetTournamentSelectorForMarket(View):
    """
    A view that allows the user to select the tournament to see the wallet amount.
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.tournament_id: Union[int, None] = None
        self.bet_game_id: Union[int, None] = None
        self.user_bet_on_id: Union[int, None] = None
        self.amount: Union[float, None] = None
        self.list_tournaments = list_tournaments
        self.bet_game_ui: Union[discord.ui.Select, None] = None
        self.bet_user_selection_ui: Union[discord.ui.Select, None] = None
        self.wallet: Union[BetUserTournament, None] = None
        self.message_id: Union[int, None] = None
        self.bet_game_by_tournament_game_id: dict[int, BetGame] = {}
        self.bet_game_by_bet_game_id: dict[int, BetGame] = {}
        self.bet_game_chosen: Optional[BetGame] = None
        self.game_chosen: Optional[TournamentGame] = None
        self.user_info1: Optional[UserInfo] = None
        self.user_info2: Optional[UserInfo] = None

        for tournament in self.list_tournaments:
            button: discord.ui.Button = discord.ui.Button(
                label=tournament.name, custom_id=f"tournament_{tournament.id}"
            )
            button.callback = lambda interaction, tid=tournament.id: self.create_button_callback(tid)(interaction)
            self.add_item(button)

    def create_button_callback(self, tournament_id: int):
        """
        Create a new button for each tournament
        """

        async def callback(interaction: discord.Interaction):
            """Handles button press for selecting a tournament."""
            try:
                # Defer the response immediately to prevent timeout errors
                await interaction.response.defer()

                self.tournament_id = tournament_id
                if self.bet_game_id is None:
                    self.wallet = get_bet_user_wallet_for_tournament(self.tournament_id, interaction.user.id)
                    # 1 Get the tournament games
                    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

                    # 2 Get the current bet_game for the tournament
                    bet_games: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)
                    self.bet_game_by_tournament_game_id = {game.tournament_game_id: game for game in bet_games}
                    self.bet_game_by_bet_game_id = {game.id: game for game in bet_games}
                    games_with_bet_game = [
                        game
                        for game in tournament_games
                        if game.id in self.bet_game_by_tournament_game_id and game.user_winner_id is None
                    ]
                    options: List[discord.SelectOption] = []
                    for tournament_game in games_with_bet_game:
                        if tournament_game.id is None:
                            continue
                        user_info1: Optional[UserInfo] = (
                            await fetch_user_info_by_user_id(tournament_game.user1_id)
                            if tournament_game.user1_id
                            else None
                        )
                        user_info2: Optional[UserInfo] = (
                            await fetch_user_info_by_user_id(tournament_game.user2_id)
                            if tournament_game.user2_id
                            else None
                        )
                        bet_game_for_game: Optional[BetGame] = self.bet_game_by_tournament_game_id.get(
                            tournament_game.id, None
                        )
                        if bet_game_for_game is None:
                            print_error_log(f"Bet game not found for game {tournament_game.id}")
                            continue
                        if user_info1 is None or user_info2 is None:
                            print_error_log(f"User info not found for game {tournament_game.id}")
                            continue
                        text_display = f"""{user_info1.display_name} ({bet_game_for_game.odd_user_1():.2f}) vs {user_info2.display_name} ({bet_game_for_game.odd_user_2():.2f})"""
                        options.append(discord.SelectOption(label=text_display, value=str(bet_game_for_game.id)))
                    if len(options) == 0:
                        await interaction.followup.send(
                            "No games available to bet in this tournament. Please try again later.", ephemeral=True
                        )
                        return

                    # Disable all buttons
                    for item in self.children:
                        item.disabled = True
                    # 3 Add the select with the possible bet
                    if self.bet_game_ui is not None:
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
                    try:
                        amount = math.floor(self.wallet.amount * 100) / 100
                        await interaction.followup.edit_message(
                            message_id=interaction.message.id,
                            content=f"""Select one of the bets available in the market for this tournament. You have ${amount:.2f}""",
                            view=self,
                        )
                    except discord.errors.NotFound:
                        print_error_log(
                            "BetTournamentSelectorForMarket>: Cannot edit the message because it no longer exists."
                        )
                        await interaction.followup.send("The message has expired or been deleted.", ephemeral=True)
            except Exception as e:
                print_error_log(f"BetTournamentSelectorForMarket>An error occurred: {e}")
                traceback.print_exc()  # This prints the full error traceback
                await interaction.followup.send(
                    "An unexpected error occurred. Please contact a moderator.", ephemeral=True
                )

        return callback

    async def handle_bet_game_ui(self, interaction: discord.Interaction):
        """Handles selection of the round lost."""
        try:
            # Safely access the selected values
            if interaction.data is None:
                raise ValueError("No values found in interaction data.")

            selected_values = interaction.data.get("values", [])

            if not selected_values or not isinstance(selected_values, list):
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
            await interaction.followup.send("Please wait for the previous action to complete.", ephemeral=True)
        else:
            await interaction.response.defer()
        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.bet_game_id is not None:
            if self.user_bet_on_id is None:
                # Add the select with the possible user to bet from the selected game bet
                self.bet_game_chosen = self.bet_game_by_bet_game_id.get(self.bet_game_id, None)
                if self.bet_game_chosen is None:
                    print_error_log(f"Bet game not found for game {self.bet_game_id}")
                    return
                self.game_chosen = next(
                    (
                        game
                        for game in fetch_tournament_games_by_tournament_id(self.tournament_id)
                        if game.id == self.bet_game_chosen.tournament_game_id
                    ),
                    None,
                )
                if self.game_chosen is None:
                    print_error_log(f"Bet game not found for game {self.bet_game_id}")
                    return
                options: List[discord.SelectOption] = []
                self.user_info1 = (
                    await fetch_user_info_by_user_id(self.game_chosen.user1_id) if self.game_chosen.user1_id else None
                )
                self.user_info2 = (
                    await fetch_user_info_by_user_id(self.game_chosen.user2_id) if self.game_chosen.user2_id else None
                )
                if self.user_info1 is None or self.user_info2 is None:
                    await interaction.followup.send(
                        "An unexpected error occurred. Please contact a moderator.", ephemeral=True
                    )
                    return

                label1, label2 = data_access_get_team_labels(self.tournament_id, self.user_info1, self.user_info2)

                options.append(
                    discord.SelectOption(
                        label=f"{label1} ({self.bet_game_chosen.odd_user_1():.2f})",
                        value=str(self.user_info1.id),
                    )
                )
                options.append(
                    discord.SelectOption(
                        label=f"{label2} ({self.bet_game_chosen.odd_user_2():.2f})",
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
                amount = math.floor(self.wallet.amount * 100) / 100
                await interaction.followup.send(
                    content=f"Select one of two. You have ${amount:.2f}",
                    view=self,
                    ephemeral=True,
                )

        return False

    async def handle_user_ui(self, interaction: discord.Interaction):
        """Handles selection of the round lost."""
        try:
            # Safely access the selected values
            if interaction.data is None:
                raise ValueError("No values found in interaction data.")

            selected_values = interaction.data.get("values", [])

            if not selected_values or not isinstance(selected_values, list):
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

    def __init__(self, view: BetTournamentSelectorForMarket):
        super().__init__()
        self.view = view  # Pass view to access the view's variables
        if view.wallet is None:
            amount = 0.0
        else:
            amount = view.wallet.amount
        self.amount_ui: discord.ui.TextInput = discord.ui.TextInput(
            label=f"Amount of money to bet (you have ${amount:.2f})",
            placeholder="Amount",
            custom_id="amount_bet_id",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.amount_ui)

    async def on_submit(self, interaction: discord.Interaction):
        """Save the modal input values back to the view"""
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command is only available in a server. Please try again in a server.", ephemeral=True
            )
            return
        try:
            if self.amount_ui.value is None:
                amount = 0.0
            else:
                amount = float(self.amount_ui.value)
            self.view.amount = amount
        except ValueError as e:
            print_error_log(
                f"""bet_tournament_selector_for_market_handle_bet_game_ui: (user id {interaction.user.id}) AmountModal_on_submit: {e}"""
            )
            await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            return

        if self.view.tournament_id is None or self.view.bet_game_id is None or self.view.user_bet_on_id is None:
            await interaction.response.send_message(
                "An error occurred while processing your selection. Please try again.", ephemeral=True
            )
            return
        # Acknowledge the submission and close the modal
        await interaction.response.defer()  # This closes the modal after the submission

        try:
            place_bet_for_game(
                self.view.tournament_id,
                self.view.bet_game_id,
                interaction.user.id,
                amount,
                self.view.user_bet_on_id,
            )
        except ValueError as e:
            print_warning_log(
                f"""bet_tournament_selector_for_market_handle_bet_game_ui: (user id {interaction.user.id}) AmountModal_on_submit: {e}"""
            )
            await interaction.followup.send(f"An error occurred while placing the bet: {e}", ephemeral=True)
            return
        except Exception as e:
            print_error_log(
                f"""bet_tournament_selector_for_market_handle_bet_game_ui:  (user id {interaction.user.id}) AmountModal_on_submit: {e}"""
            )
            await interaction.followup.send(
                "An error occurred while placing the bet. Please notify a moderator.", ephemeral=True
            )
            return
        # Send the follow-up message
        if (
            self.view.user_info1 is not None
            and self.view.user_info2 is not None
            and self.view.bet_game_chosen is not None
        ):

            member1 = await data_access_get_member(interaction.guild_id, self.view.user_info1.id)
            user1 = member1.mention if member1 else self.view.user_info1.display_name
            user1_odd = self.view.bet_game_chosen.odd_user_1()

            member2 = await data_access_get_member(interaction.guild_id, self.view.user_info2.id)
            user2 = member2.mention if member2 else self.view.user_info2.display_name
            user2_odd = self.view.bet_game_chosen.odd_user_2()

            user_bet_on = user1 if self.view.user_info1.id == self.view.user_bet_on_id else user2

            tournament_name = next(t for t in self.view.list_tournaments if t.id == self.view.tournament_id).name
            label1, label2 = data_access_get_team_labels(
                self.view.tournament_id, self.view.user_info1, self.view.user_info2
            )
            await interaction.followup.send(
                f'''💰 {interaction.user.mention} bet **${amount:.2f}** on {user_bet_on} in the match {label1} ({user1_odd:.2f}) vs {label2} ({user2_odd:.2f}) in tournanent "{tournament_name}"''',
                ephemeral=False,
            )
