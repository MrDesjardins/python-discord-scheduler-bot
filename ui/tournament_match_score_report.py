""" User interface for the bot"""

from typing import List
import discord
from discord.ui import Select, View
from deps.data_access import data_access_get_member
from deps.tournament_data_class import Tournament
from deps.tournament_functions import report_lost_tournament
from deps.log import print_error_log
from deps.tournament_models import TournamentNode


class TournamentMatchScoreReport(View):
    """
    A view that allows the user to select the tournament to report a lost match.
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.tournament_id = None
        self.round_lost = None
        self.round_won = None
        self.list_tournaments = list_tournaments

        # Dynamically add buttons for each tournament
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
            await interaction.response.send_message(
                f"Tournament selected: {tournament_id}. Now select rounds.", ephemeral=True
            )

        return callback

    async def handle_round_lost(self, interaction: discord.Interaction):
        """Handles selection of the round lost."""
        self.round_lost = int(self.round_lost_select.values[0])
        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.round_lost is not None and self.round_won is not None:
            await self.process_tournament_result(interaction)

    async def handle_round_won(self, interaction: discord.Interaction):
        """Handles selection of the round won."""
        self.round_won = int(self.round_won_select.values[0])

        # Check if all inputs are set and process the result
        if self.tournament_id is not None and self.round_lost is not None and self.round_won is not None:
            await self.process_tournament_result(interaction)

    async def process_tournament_result(self, interaction: discord.Interaction):
        """Processes the tournament match result."""

        score_string = f"{self.round_won}-{self.round_lost}"
        result = report_lost_tournament(self.tournament_id, interaction.user.id, score_string)
        tournament = next((t for t in self.list_tournaments if t.id == self.tournament_id), None)

        if not tournament:
            print_error_log(f"Tournament not found for id {self.tournament_id}")
            await interaction.followup.send("Tournament not found. Please try again.", ephemeral=True)
            return

        if result.is_successful:
            completed_node: TournamentNode = result.context
            player_lose = interaction.user
            player_win = await data_access_get_member(guild_id=interaction.guild_id, user_id=completed_node.player_win)
            await interaction.followup.send(
                f"{player_win.display_name} wins against {player_lose.display_name} on {completed_node.map} with a score of {completed_node.score}",
                ephemeral=False,
            )
        else:
            print_error_log(f"Error while reporting lost: {result.text}")
            await interaction.followup.send(
                f"An error occurred while reporting the lost match: {result.text}. Please contact a moderator.",
                ephemeral=True,
            )
