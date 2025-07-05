"""Functions used to interact with the user in the Discord UI."""

from typing import List, Optional
import discord
from deps.analytic_data_access import fetch_user_info
from deps.data_access import data_access_get_member
from deps.bet.bet_functions import (
    generate_msg_bet_leaderboard,
)
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.tournaments.tournament_data_access import (
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
    fetch_tournament_team_members_by_leader,
)
from deps.log import print_error_log, print_warning_log
from deps.tournaments.tournament_discord_actions import generate_bracket_file
from deps.tournaments.tournament_functions import build_tournament_tree, get_tournament_final_result_positions


async def post_end_tournament_messages(interaction: discord.Interaction, tournament_id: int) -> None:
    """
    Post to Discord the end of the tournament with the winners and the leaderboard of the bets
    """
    if interaction.guild_id is None:
        return
    guild_id = interaction.guild_id
    tournament: Optional[Tournament] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        print_warning_log(f"send_end_tournament_by_mod: cannot find tournament {tournament_id}.")
        await interaction.response.send_message("No active tournament available", ephemeral=True)
        return
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        print_error_log(
            f"TournamentMatchScoreReport: process_tournament_result: Failed to build tournament tree for tournament {tournament_id}. Skipping."
        )
        return
    final_score = get_tournament_final_result_positions(tournament_tree)
    file = generate_bracket_file(tournament_id)
    if file is None:
        # Should never go here
        print_error_log(
            f"TournamentMatchScoreReport: process_tournament_result: Failed to generate bracket file for tournament {tournament_id}."
        )
        await interaction.followup.send(
            f"The tournament **{tournament.name}** has finished! No winners were found. No bracket available.",
            ephemeral=False,
        )
        return
    if final_score is None:
        # Should always go here
        await interaction.followup.send(file=file, ephemeral=False)
    else:
        # Tournament is over. We show the winners
        try:
            leader_partners: dict[int, list[int]] = fetch_tournament_team_members_by_leader(tournament.id)
            m1 = await data_access_get_member(guild_id, final_score.first_place_user_id)
            first_place = m1.mention if m1 else "Unknown"
            m2 = await data_access_get_member(guild_id, final_score.second_place_user_id)
            second_place = m2.mention if m2 else "Unknown"
            m3_1 = await data_access_get_member(guild_id, final_score.third_place_user_id_1)
            third_place1 = m3_1.mention if m3_1 else "Unknown"
            m3_2 = await data_access_get_member(guild_id, final_score.third_place_user_id_2)
            third_place2 = m3_2.mention if m3_2 else "None"
            if tournament.team_size > 1:
                if final_score.first_place_user_id in leader_partners:
                    teammates = leader_partners[final_score.first_place_user_id]
                    first_place += await get_teammate_mentions(teammates, guild_id)
                if final_score.second_place_user_id in leader_partners:
                    teammates = leader_partners[final_score.second_place_user_id]
                    second_place += await get_teammate_mentions(teammates, guild_id)
                if final_score.third_place_user_id_1 in leader_partners:
                    teammates = leader_partners[final_score.third_place_user_id_1]
                    third_place1 += await get_teammate_mentions(teammates, guild_id)
                if final_score.third_place_user_id_2 in leader_partners:
                    teammates = leader_partners[final_score.third_place_user_id_2]
                    third_place2 += await get_teammate_mentions(teammates, guild_id)
        except Exception as e:
            # Might go in here in development since there is no member in the guild
            print_error_log(f"TournamentMatchScoreReport: process_tournament_result: Error while fetching member: {e}")
            first_place = "Unknown"
            second_place = "Unknown"
            third_place1 = "Unknown"
            third_place2 = "Unknown"
        await interaction.followup.send(file=file, ephemeral=False)
        third_place_full = f"{third_place1} and {third_place2}" if third_place2 != "None" else third_place1
        await interaction.followup.send(
            f"The tournament **{tournament.name}** has finished!\n Winners are:\n🥇 {first_place}\n🥈 {second_place}\n🥉 {third_place_full} ",
            ephemeral=False,
        )

        # Generate leaderboard at the end of the tournament
        try:
            msg_better_list = await generate_msg_bet_leaderboard(tournament)
        except Exception as e:
            print_error_log(
                f"TournamentMatchScoreReport: process_tournament_result: Error while generating bet leaderboard: {e}"
            )
            msg_better_list = ""
        if msg_better_list != "":
            await interaction.followup.send(
                f"Top Better Wallet Value for the tournament **{tournament.name}** are:\n{msg_better_list}",
                ephemeral=False,
            )


async def get_teammate_mentions(teammates: List[int], guild_id: int) -> str:
    """
    Fetches the mentions of the teammates from the guild.
    """
    mentions = []
    for teammate in teammates:
        member = await data_access_get_member(guild_id, teammate)
        mentions.append(member.mention if member else str(teammate))
    return ", ".join(mentions)
