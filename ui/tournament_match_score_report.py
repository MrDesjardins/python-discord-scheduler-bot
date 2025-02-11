""" User interface for the bot"""

from typing import List, Optional
import discord
from discord.ui import Select, View
from deps.bet.bet_functions import generate_msg_bet_game
from deps.data_access import data_access_get_member
from deps.tournaments.tournament_data_class import Tournament
from deps.tournaments.tournament_functions import (
    report_lost_tournament,
)
from deps.log import print_error_log
from deps.tournaments.tournament_models import TournamentNode
from deps.tournaments.tournament_ui_functions import post_end_tournament_messages


class TournamentMatchScoreReport(View):
    """
    A view that allows the user to select the tournament to report a lost match.
    """

    def __init__(self, list_tournaments: List[Tournament], user_id: Optional[int] = None):
        super().__init__()
        self.tournament_id = None
        self.round_lost = None
        self.round_won = None
        self.list_tournaments = list_tournaments
        self.user_id_lost_match = user_id  # The user that lost the match, only provided when the user is not the one that lost the match (moderator report)

        # Dynamically add buttons for each tournament
        if (len(self.list_tournaments)) == 1:
            self.tournament_id = self.list_tournaments[0].id
        else:
            for tournament in self.list_tournaments:
                button = discord.ui.Button(label=tournament.name, custom_id=f"tournament_{tournament.id}")
                button.callback = self.create_button_callback(tournament.id)
                self.add_item(button)

        # Add dropdown for "round lost"
        self.round_lost_select = Select(
            placeholder="Round lost:",
            options=[discord.SelectOption(value=str(i), label=str(i)) for i in range(11)],
            custom_id="round_lost",
            min_values=1,
            max_values=1,
        )
        self.round_lost_select.callback = self.handle_round_lost
        self.add_item(self.round_lost_select)

        # Add dropdown for "round won"
        self.round_won_select = Select(
            placeholder="Round won:",
            options=[discord.SelectOption(value=str(i), label=str(i)) for i in range(11)],
            custom_id="round_won",
            min_values=1,
            max_values=1,
        )
        self.round_won_select.callback = self.handle_round_won
        self.add_item(self.round_won_select)

    def create_button_callback(self, tournament_id: int):
        async def callback(interaction: discord.Interaction):
            """Handles button press for selecting a tournament."""
            self.tournament_id = tournament_id
            if self.round_lost is None or self.round_won is None:
                await interaction.response.send_message(
                    "Now select the number of round you lost and the number of round you won.", ephemeral=True
                )
            else:
                await interaction.response.defer()

        return callback

    async def handle_round_lost(self, interaction: discord.Interaction):
        """Handles selection of the round lost."""
        self.round_lost = int(self.round_lost_select.values[0])
        await interaction.response.defer()
        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.round_lost is not None and self.round_won is not None:
            await self.process_tournament_result(interaction)

    async def handle_round_won(self, interaction: discord.Interaction):
        """Handles selection of the round won."""
        self.round_won = int(self.round_won_select.values[0])
        await interaction.response.defer()
        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.round_lost is not None and self.round_won is not None:
            await self.process_tournament_result(interaction)

    async def process_tournament_result(self, interaction: discord.Interaction):
        """Processes the tournament match result."""

        score_string = f"{self.round_won}-{self.round_lost}"
        user_id = self.user_id_lost_match if self.user_id_lost_match is not None else interaction.user.id
        result = await report_lost_tournament(self.tournament_id, user_id, score_string)
        tournament = next((t for t in self.list_tournaments if t.id == self.tournament_id), None)

        if not tournament:
            print_error_log(
                f"TournamentMatchScoreReport: process_tournament_result: Tournament not found for id {self.tournament_id}"
            )
            await interaction.followup.send("Tournament not found. Please try again.", ephemeral=True)
            return

        if result.is_successful:
            completed_node: TournamentNode = result.context
            # Played can be set by a moderator
            if self.user_id_lost_match is not None:
                player_lose = await data_access_get_member(interaction.guild_id, self.user_id_lost_match)
            else:
                player_lose: discord.Member = interaction.user
            try:
                player_win = await data_access_get_member(
                    guild_id=interaction.guild_id, user_id=completed_node.user_winner_id
                )
                player_win_display_name = player_win.mention
            except Exception as e:
                # Might go in here in development since there is no member in the guild
                print_error_log(
                    f"TournamentMatchScoreReport: process_tournament_result: Error while fetching member: {e}"
                )
                player_win_display_name = completed_node.user_winner_id
            await interaction.followup.send(
                f"{player_win_display_name} wins against {player_lose.mention} on {completed_node.map} with a score of {completed_node.score}",
                ephemeral=False,
            )

            # Display a message with the result of the bets
            try:
                msg_result_bets = await generate_msg_bet_game(result.context)
                if msg_result_bets != "":
                    await interaction.followup.send(
                        f"Bets results for the match {player_win_display_name} vs {player_lose.mention}:\n{msg_result_bets}",
                        ephemeral=False,
                    )
            except Exception as e:
                print_error_log(
                    f"TournamentMatchScoreReport: process_tournament_result: Error while generating bet game: {e}"
                )
            try:
                await post_end_tournament_messages(interaction, self.tournament_id)
            except Exception as e:
                print_error_log(
                    f"TournamentMatchScoreReport: process_tournament_result: Error while posting end tournament messages: {e}"
                )
                await interaction.followup.send(
                    "The tournament ended but the final ranking and the bet leaderboard could not be displayed. Please contact a moderator to re-generate.",
                    ephemeral=True,
                )
        else:
            print_error_log(f"Error while reporting lost: {result.text}")
            await interaction.followup.send(
                f"TournamentMatchScoreReport: process_tournament_result: Cannot report lost match: {result.text} Please contact a moderator if you should have reported a match.",
                ephemeral=True,
            )
