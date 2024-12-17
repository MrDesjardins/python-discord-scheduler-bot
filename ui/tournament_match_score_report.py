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
    A view that allows the user to selecft the tournament to report a lost
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.tournament_id = None
        self.list_tournaments = list_tournaments

        for t in self.list_tournaments:
            self.add_item(discord.ui.Button(label=t.name, custom_id="tournament_id", sku_id=t.id))

        self.round_lost = Select(
            placeholder="Round lost:",
            options=[
                discord.SelectOption(value="0", label="0"),
                discord.SelectOption(value="1", label="1"),
                discord.SelectOption(value="2", label="2"),
                discord.SelectOption(value="3", label="3"),
                discord.SelectOption(value="4", label="4"),
                discord.SelectOption(value="5", label="5"),
                discord.SelectOption(value="6", label="6"),
                discord.SelectOption(value="7", label="7"),
                discord.SelectOption(value="8", label="8"),
                discord.SelectOption(value="9", label="9"),
                discord.SelectOption(value="10", label="10"),
            ],
            custom_id="round_lost",
            min_values=1,
            max_values=1,
        )
        self.add_item(self.round_lost)

        self.round_won = Select(
            placeholder="Round won:",
            options=[
                discord.SelectOption(value="0", label="0"),
                discord.SelectOption(value="1", label="1"),
                discord.SelectOption(value="2", label="2"),
                discord.SelectOption(value="3", label="3"),
                discord.SelectOption(value="4", label="4"),
                discord.SelectOption(value="5", label="5"),
                discord.SelectOption(value="6", label="6"),
                discord.SelectOption(value="7", label="7"),
                discord.SelectOption(value="8", label="8"),
                discord.SelectOption(value="9", label="9"),
                discord.SelectOption(value="10", label="10"),
            ],
            custom_id="round_won",
            min_values=1,
            max_values=1,
        )
        self.add_item(self.round_won)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Callback function to check if the interaction is valid"""

        if interaction.data["custom_id"] == "round_lost":
            self.round_lost = self.round_lost.values
        elif interaction.data["custom_id"] == "round_won":
            self.round_won = self.round_won.values
        elif interaction.data["custom_id"] == "tournament_name":
            self.tournament_id = int(interaction.data["sku_id"])

        if self.round_lost is not None and self.round_won is not None and self.tournament_id is not None:
            # Save user responses
            result = report_lost_tournament(self.tournament_id, interaction.user.id)

            # Find the tournament from the id variable in the list of tournament to get the starting date
            tournament = next((t for t in self.list_tournaments if t.id == self.tournament_id), None)
            if not tournament:
                print_error_log(f"Tournament not found for id {self.list_tournaments}")
                return True

            # Send final confirmation message with the saved data
            if result.is_successful:
                completed_node: TournamentNode = result.context
                player_lose = interaction.user
                player_win = await data_access_get_member(
                    guild_id=interaction.guild_id, user_id=completed_node.player_win
                )
                await interaction.followup.send(
                    f"{player_win.display_name} wins against {player_lose.display_name} on {completed_node.map} with a score of {completed_node.score}",
                    ephemeral=False,
                )
            else:
                print_error_log(f"Error while reporting lost: {result.text}")
                await interaction.followup.send(
                    f"And error as occured while reporting the lost: {result.text}. Please contact a moderator.",
                    ephemeral=False,
                )
            return True
        return False
