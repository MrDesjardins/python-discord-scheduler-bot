import random
from typing import List, Union

import discord

from deps.custom_match.custom_match_data_class import MapSuggestion
from deps.custom_match.custom_match_data_access import data_access_fetch_all_maps, data_access_fetch_all_maps, data_access_fetch_best_maps_first, data_access_fetch_less_played_maps_first, data_access_fetch_worse_maps_first
from deps.custom_match.custom_match_values import MapAlgo, TeamAlgo
from deps.analytic_data_access import data_access_fetch_user_full_user_info, data_access_fetch_user_max_current_mmr, data_access_fetch_user_max_mmr
from deps.custom_match.custom_match_models import TeamSuggestion
from deps.models import UserInformation


async def _create_team_by_metric(
    user_ids: List[discord.Member],
    metric_attr: str,
    logic: str,
    label: str,
    fmt: str = ".2f",
) -> TeamSuggestion:
    team_suggestion = TeamSuggestion()
    users_metric: List[tuple[discord.Member, float]] = []
    for discord_member in user_ids:
        if metric_attr == "mmr":
                value = data_access_fetch_user_max_current_mmr(discord_member.id)
        elif metric_attr == "max_mmr":
            value = data_access_fetch_user_max_mmr(discord_member.id)
        else:
            user_info: Union[UserInformation, None] = data_access_fetch_user_full_user_info(discord_member.id)
            if user_info:
                value = getattr(user_info, metric_attr, 1.0)
            else:
                value = 1.0
        if value is None:
            value = 1.0
        users_metric.append((discord_member, float(value)))

    users_metric.sort(key=lambda x: x[1], reverse=True)
    team1_total = 0.0
    team2_total = 0.0
    team_suggestion.logic = logic
    team1_text = ""
    team2_text = ""
    for discord_member, val in users_metric:
        if team1_total <= team2_total:
            team_suggestion.team1.members.append(discord_member)
            team1_total += val
            team1_text += f"{discord_member.mention} ({label}: {format(val, fmt)})\n"
        else:
            team_suggestion.team2.members.append(discord_member)
            team2_total += val
            team2_text += f"{discord_member.mention} ({label}: {format(val, fmt)})\n"

    team1_avg = team1_total / len(team_suggestion.team1.members) if team_suggestion.team1.members else 0
    team2_avg = team2_total / len(team_suggestion.team2.members) if team_suggestion.team2.members else 0
    team_suggestion.explanation = (
        f"Team 1 Average {label}: {format(team1_avg, fmt)}\n{team1_text}\n"
        f"Team 2 Average {label}: {format(team2_avg, fmt)}\n{team2_text}"
    )
    return team_suggestion


async def create_team_by_win_percentage(user_ids: List[discord.Member]) -> TeamSuggestion:
    return await _create_team_by_metric(
        user_ids, metric_attr="win_percentage", logic="Balanced by Rank win %", label="Win %", fmt=".2f"
    )

async def create_team_by_kd(user_ids: List[discord.Member]) -> TeamSuggestion:
    return await _create_team_by_metric(
        user_ids, metric_attr="rank_kd_ratio", logic="Balanced by Rank K/D", label="KD", fmt=".2f"
    )

async def create_team_by_current_mmr(user_ids: List[discord.Member]) -> TeamSuggestion:
    return await _create_team_by_metric(
        user_ids, metric_attr="mmr", logic="Balanced by Current MMR", label="MMR", fmt=".0f"
    )
    
async def create_team_by_max_mmr(user_ids: List[discord.Member]) -> TeamSuggestion:
    return await _create_team_by_metric(
        user_ids, metric_attr="max_mmr", logic="Balanced by Max MMR", label="Max MMR", fmt=".0f"
    )

async def select_team_by_algorithm(team_algo: TeamAlgo, user_ids: List[discord.Member]) -> TeamSuggestion:
    if team_algo == TeamAlgo.WIN_RATIO:
        return await create_team_by_win_percentage(user_ids)
    elif team_algo == TeamAlgo.K_D_RATIO:
        return await create_team_by_kd(user_ids)
    elif team_algo == TeamAlgo.CURRENT_MMR:
        return await create_team_by_current_mmr(user_ids)
    elif team_algo == TeamAlgo.MAX_MMR:
        return await create_team_by_max_mmr(user_ids)

async def select_map_based_on_algorithm(map_algo: MapAlgo, user_ids: List[int]) -> List[MapSuggestion]:
    if map_algo == MapAlgo.WORSE_MAPS_FIRST:
        return data_access_fetch_worse_maps_first(user_ids)
    elif map_algo == MapAlgo.BEST_MAPS_FIRST:
        return data_access_fetch_best_maps_first(user_ids)
    elif map_algo == MapAlgo.LEAST_PLAYED:
        return data_access_fetch_less_played_maps_first(user_ids)
    else:
        maps = data_access_fetch_all_maps(user_ids)
        map = maps[random.randint(0, len(maps) - 1)]
        return [map]
    