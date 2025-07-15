"""User interface for the bot"""

from typing import List, Optional
import discord
from discord.ui import Select, View
from deps.bet.bet_functions import generate_msg_bet_game
from deps.data_access import data_access_get_member
from deps.tournaments.tournament_data_class import Tournament
from deps.tournaments.tournament_functions import (
    report_lost_tournament,
    return_leader,
)
from deps.log import print_error_log
from deps.tournaments.tournament_models import TournamentNode
from deps.tournaments.tournament_ui_functions import post_end_tournament_messages
from deps.tournaments.tournament_data_access import fetch_tournament_team_members_by_leader
from deps.functions import is_production_env


class TournamentMatchScoreReport(View):
    """
    A view that allows the user to select the tournament to report a lost match.
    """

    def add_rounds_ui_components(self) -> None:
        """
        Add additional UI components (drop downs) for selecting the rounds lost and won.
        """
        # Add dropdown for "round lost"
        self.round_lost_select: discord.ui.Select = Select(
            placeholder="Round lost by you (bigger number):",
            options=[discord.SelectOption(value=str(i), label=str(i)) for i in range(11)],
            custom_id="round_lost",
            min_values=1,
            max_values=1,
        )
        self.round_lost_select.callback = self.handle_round_lost
        self.add_item(self.round_lost_select)

        # Add dropdown for "round won"
        self.round_won_select: discord.ui.Select = Select(
            placeholder="Round won by you (smaller number):",
            options=[discord.SelectOption(value=str(i), label=str(i)) for i in range(11)],
            custom_id="round_won",
            min_values=1,
            max_values=1,
        )
        self.round_won_select.callback = self.handle_round_won
        self.add_item(self.round_won_select)

    def __init__(self, list_tournaments: List[Tournament], user_id: Optional[int] = None):
        super().__init__()
        self.tournament_id: Optional[int] = None
        self.round_lost: Optional[int] = None
        self.round_won: Optional[int] = None
        self.list_tournaments = list_tournaments
        # The user that lost the match, only provided when the user is not the one
        # that lost the match (moderator report)
        self.user_id_lost_match = user_id

        # Dynamically add buttons for each tournament
        if (len(self.list_tournaments)) == 1:
            self.tournament_id = self.list_tournaments[0].id
        else:
            for tournament in self.list_tournaments:
                if tournament.id is not None:
                    button: discord.ui.Button = discord.ui.Button(
                        label=tournament.name, custom_id=f"tournament_{tournament.id}"
                    )
                    button.callback = self.create_button_callback(tournament.id)
                    self.add_item(button)

        if (len(self.list_tournaments)) == 1:
            self.add_rounds_ui_components()

    def create_button_callback(self, tournament_id: int):
        """
        Create tournament button action.
        Each tournament as a different action using the tournament.id
        Only occurs if more than one tournament is available at the same time.
        """

        async def callback(interaction: discord.Interaction):
            """Handles button press for selecting a tournament."""
            self.tournament_id = tournament_id
            if self.round_lost is None or self.round_won is None:
                self.add_rounds_ui_components()
                await interaction.response.edit_message(
                    content="Now select the number of round you lost and the number of round you won.", view=self
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
        """
        Processes the tournament match result.
        This function should always have the tournament_id, round_lost and round_won set.
        """

        if interaction.guild_id is None:
            print_error_log("TournamentMatchScoreReport: process_tournament_result: Guild id is None")
            await interaction.followup.send(
                """An unexpected error occurred. Please contact a moderator.""", ephemeral=True
            )
            return
        if self.round_lost is None or self.round_won is None:
            print_error_log(
                """TournamentMatchScoreReport: process_tournament_result: Round lost or round won is None"""
            )
            await interaction.followup.send(
                """An unexpected error occurred. Please contact a moderator.""", ephemeral=True
            )
            return
        if self.tournament_id is None:
            print_error_log("TournamentMatchScoreReport: process_tournament_result: Tournament id is None")
            await interaction.followup.send(
                """An unexpected error occurred. Please contact a moderator.""", ephemeral=True
            )
            return
        # Get the tournament
        tournament = next((t for t in self.list_tournaments if t.id == self.tournament_id), None)
        if tournament is None:
            print_error_log(
                f"""TournamentMatchScoreReport: process_tournament_result: Tournament not found for id {self.tournament_id}"""
            )
            await interaction.followup.send("Tournament not found. Please try again.", ephemeral=True)
            return
        is_team_tournament = tournament.team_size > 1
        # Get the participants of the tournament
        leader_partners: dict[int, list[int]] = fetch_tournament_team_members_by_leader(tournament.id)

        score_string = f"{self.round_lost}-{self.round_won}"  # We flip because the round_win/lost were registered from the perspective of the loser
        # The user who is reporting OR the user passed by a moderator
        leader_id_loser_tournament: int = (
            self.user_id_lost_match if self.user_id_lost_match is not None else interaction.user.id
        )
        if is_team_tournament:
            leader_id_loser = return_leader(leader_partners, leader_id_loser_tournament)
            if leader_id_loser is None:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: Leader id not found for user {leader_id_loser_tournament} in tournament {tournament.id}"""
                )
                await interaction.followup.send(
                    "The loser is not a participant of this tournament. Please contact a moderator.", ephemeral=True
                )
                return
            else:
                leader_id_loser_tournament = leader_id_loser
        result = await report_lost_tournament(self.tournament_id, leader_id_loser_tournament, score_string)

        if result.is_successful:
            completed_node: TournamentNode = result.context
            if completed_node.user_winner_id is None:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: User winner id is None for tournament {self.tournament_id}"""
                )
                await interaction.followup.send(
                    "The winner wasn't saved properly. Please contact a moderator.", ephemeral=True
                )
                return

            # Player Loser
            # Played can be set by a moderator, if the case, user_id_lost_match is set, otherwise, none and use the interaction user
            player_lose: Optional[discord.Member] = None
            player_lose_str: str = ""

            user_or_member = await data_access_get_member(interaction.guild_id, leader_id_loser_tournament)
            player_lose = user_or_member if isinstance(user_or_member, discord.Member) else None  # Ensure it's a Member
            if player_lose is None:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: player_lose is None for tournament {self.tournament_id}"""
                )
                await interaction.followup.send(
                    """Losing member not found. Please contact a moderator.""", ephemeral=True
                )
                if is_production_env():
                    # In debug/dev we do not return since members do not exist for real
                    return
            player_lose_str = ""
            # In case that is not a 1v1 tournament
            if is_team_tournament:
                player_lose_str = await build_team_mentions(
                    leader_partners, leader_id_loser_tournament, interaction.guild_id
                )
            else:
                player_lose_str = player_lose.mention if player_lose is not None else str(leader_id_loser_tournament)

            # Player Winner
            player_win: Optional[discord.Member] = None
            player_win_str: str = ""
            leader_id_winner = (
                return_leader(leader_partners, completed_node.user_winner_id)
                if is_team_tournament
                else completed_node.user_winner_id
            )
            if leader_id_winner is None:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: Leader id winner not found for user {completed_node.user_winner_id} in tournament {self.tournament_id}"""
                )
                await interaction.followup.send(
                    "The winner of the match is not a participant of this tournament. Please contact a moderator.",
                    ephemeral=True,
                )
                return
            if leader_id_winner == leader_id_loser_tournament:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: Leader id winner is the same as the loser {leader_id_winner} in tournament {self.tournament_id}"""
                )
                await interaction.followup.send(
                    "The winner of the match cannot be the same as the loser. Please contact a moderator.",
                    ephemeral=True,
                )
                return
            try:
                user_or_member = await data_access_get_member(interaction.guild_id, leader_id_winner)
                player_win = user_or_member if isinstance(user_or_member, discord.Member) else None
                if player_win is None:
                    print_error_log(
                        f"""TournamentMatchScoreReport: process_tournament_result: player_win is None for tournament {self.tournament_id}"""
                    )
                    await interaction.followup.send(
                        """Winning member not found. Please contact a moderator.""", ephemeral=True
                    )
                    if is_production_env():
                        # In debug/dev we do not return since members do not exist for real
                        return
            except Exception as e:
                # Might go in here in development since there is no member in the guild
                print_error_log(
                    f"TournamentMatchScoreReport: process_tournament_result: Error while fetching member: {e}"
                )
                await interaction.followup.send(
                    """An unexpected error occurred while fetching the winning member. Please contact a moderator.""",
                    ephemeral=True,
                )
                return
            if is_team_tournament:
                player_win_str = await build_team_mentions(leader_partners, leader_id_winner, interaction.guild_id)
            else:
                player_win_str = player_win.mention if player_win is not None else str(leader_id_winner)

            await interaction.followup.send(
                f"""{player_win_str} wins against {player_lose_str} on {completed_node.map} with a score of {completed_node.score}""",
                ephemeral=False,
            )

            # Display a message with the result of the bets
            try:
                msg_result_bets = await generate_msg_bet_game(result.context)
                if msg_result_bets != "":
                    await interaction.followup.send(
                        f"""Bets results for the match {player_win_str} vs {player_lose_str}:\n{msg_result_bets}""",
                        ephemeral=False,
                    )
            except Exception as e:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: Error while generating bet game: {e}"""
                )
            try:
                await post_end_tournament_messages(interaction, self.tournament_id)
            except Exception as e:
                print_error_log(
                    f"""TournamentMatchScoreReport: process_tournament_result: Error while posting end tournament messages: {e}"""
                )
                await interaction.followup.send(
                    """The tournament ended but the final ranking and the bet leaderboard could not be displayed. Please contact a moderator to re-generate.""",
                    ephemeral=True,
                )
        else:
            print_error_log(
                f"TournamentMatchScoreReport: process_tournament_result: Error while reporting lost: {result.text}"
            )
            await interaction.followup.send(
                f"""Cannot report lost match: {result.text} Please contact a moderator if you should have reported a match.""",
                ephemeral=True,
            )


async def build_team_mentions(leader_partners: dict[int, list[int]], leader_id: int, guild_id: int) -> str:
    """Build a string of mentions for the team members of the leader."""
    mentions = []
    m = await data_access_get_member(guild_id, leader_id)
    if m is not None:
        mentions.append(m.mention)
    else:
        mentions.append(str(leader_id))
    teammates = leader_partners.get(leader_id, [])
    for teammate in teammates:
        m = await data_access_get_member(guild_id, teammate)
        if m is not None:
            mentions.append(m.mention)
        else:
            mentions.append(str(teammate))
    return ", ".join(mentions)
