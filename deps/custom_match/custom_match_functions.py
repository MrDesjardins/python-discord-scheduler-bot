from datetime import datetime, timezone
from typing import List, Union, Union

import discord

from deps.analytic_data_access import data_access_fetch_user_full_user_info
from deps.custom_match.custom_match_models import TeamSuggestion
from deps.models import Reason, UserInformation

async def create_team_by_win_percentage(user_ids: List[discord.Member]) -> TeamSuggestion:

    team_suggestion = TeamSuggestion()
    users_kd: List[tuple[discord.Member, float]] = []
    for discord_member in user_ids:
        user_info: Union[UserInformation, None] = await data_access_fetch_user_full_user_info(discord_member.id)
        if user_info:
            users_kd.append((discord_member, user_info.win_percentage))
        else:
            users_kd.append((discord_member, 1.0))  # Default KD if not available

    # Balance teams based on KD ratio
    users_kd.sort(key=lambda x: x[1], reverse=True)  # Sort by KD ratio descending
    team1_kd = 0.0
    team2_kd = 0.0
    team_suggestion.logic = "Balanced by Rank win %"
    team1_text = ""
    team2_text = ""
    for discord_member, kd in users_kd:
        if team1_kd <= team2_kd:
            team_suggestion.team1.members.append(discord_member)
            team1_kd += kd
            team1_text += f"{discord_member.mention} (Win %: {kd:.2f})\n"
        else:
            team_suggestion.team2.members.append(discord_member)
            team2_kd += kd
            team2_text += f"{discord_member.mention} (Win %: {kd:.2f})\n"
    team1_kd_average = team1_kd / len(team_suggestion.team1.members) if team_suggestion.team1.members else 0
    team2_kd_average = team2_kd / len(team_suggestion.team2.members) if team_suggestion.team2.members else 0
    team_suggestion.explanation = f"Team 1 Average Win %: {team1_kd_average:.2f}\n{team1_text}\nTeam 2 Average Win %: {team2_kd_average:.2f}\n{team2_text}"
    return team_suggestion
  
  
async def create_team_by_kd(user_ids: List[discord.Member]) -> TeamSuggestion:

    team_suggestion = TeamSuggestion()
    users_kd: List[tuple[discord.Member, float]] = []
    for discord_member in user_ids:
        user_info: Union[UserInformation, None] = await data_access_fetch_user_full_user_info(discord_member.id)
        if user_info:
            users_kd.append((discord_member, user_info.rank_kd_ratio))
        else:
            users_kd.append((discord_member, 1.0))  # Default KD if not available

    # Balance teams based on KD ratio
    users_kd.sort(key=lambda x: x[1], reverse=True)  # Sort by KD ratio descending
    team1_kd = 0.0
    team2_kd = 0.0
    team_suggestion.logic = "Balanced by Rank K/D"
    team1_text = ""
    team2_text = ""
    for discord_member, kd in users_kd:
        if team1_kd <= team2_kd:
            team_suggestion.team1.members.append(discord_member)
            team1_kd += kd
            team1_text += f"{discord_member.mention} (KD: {kd:.2f})\n"
        else:
            team_suggestion.team2.members.append(discord_member)
            team2_kd += kd
            team2_text += f"{discord_member.mention} (KD: {kd:.2f})\n"
    team1_kd_average = team1_kd / len(team_suggestion.team1.members) if team_suggestion.team1.members else 0
    team2_kd_average = team2_kd / len(team_suggestion.team2.members) if team_suggestion.team2.members else 0
    team_suggestion.explanation = f"Team 1 Average KD: {team1_kd_average}\n{team1_text}\nTeam 2 Average KD: {team2_kd_average}\n{team2_text}"
    return team_suggestion