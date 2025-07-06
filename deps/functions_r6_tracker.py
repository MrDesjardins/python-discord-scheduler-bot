"""R6 Tracker API functions"""

import os
from typing import Any, Dict, List, Optional, Union
import json
from datetime import datetime
from dateutil import parser
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats, UserInformation, UserMatchInfoSessionAggregate
from deps.log import print_error_log

TRN_API_KEY = os.getenv("TRN_API_KEY")


def download_stub_file() -> Optional[str]:
    """
    Temporary until we get the API KEY
    """
    with open("./tests/tests_assets/player_rank_history.json", "r", encoding="utf8") as file:
        data = json.loads(file.read())
        return data


def parse_json_from_full_matches(data_dict, user_info: UserInfo) -> List[UserFullMatchStats]:
    """
    Function to parse the JSON dictionary into dataclasses
    The parse function returns more information than the one for the summary.
    """
    try:
        matches = data_dict["data"]["matches"]
        if not isinstance(matches, list) or len(matches) == 0:
            return []
    except KeyError as e:
        print_error_log(
            f"parse_json_from_full_matches: KeyError: {e} not found in the JSON data when parsing for active user: {user_info.ubisoft_username_active}."
        )
        return []
    except TypeError as e:
        print_error_log(f"parse_json_from_full_matches: TypeError: Unexpected data format - {e}")
        return []
    # Loopp all matches
    match_infos = []
    for match in matches:
        try:
            match_metadata = match["metadata"]
            segments = match.get("segments", [])
            if not segments:
                print("Warning: Empty segments in match data.")
                continue  # Skip if segments are empty
            segment = segments[0]
            metadata = segment["metadata"]
            stats = segment["stats"]
            map_name = match_metadata.get("sessionMapName", "Unknown")
            if map_name is None:
                # In some cases, the map name is not available but also few other metadata. We skip.
                # It is a very rare case. The entry does not show in the website TRN but in the API.
                continue
            match_infos.append(
                UserFullMatchStats(
                    id=None,
                    user_id=user_info.id,
                    match_uuid=match.get("attributes", {}).get("id", "Unknown"),
                    match_timestamp=parser.parse(match_metadata.get("timestamp", "1970-01-01T00:00:00Z")),
                    match_duration_ms=match_metadata.get("duration", 0) or 0,
                    data_center=match_metadata.get("datacenter", "Unknown"),
                    session_type=match_metadata.get("sessionTypeName", "Unknown"),
                    map_name=map_name,
                    is_surrender=match_metadata.get("isSurrender", False) or False,
                    is_forfeit=match_metadata.get("isForfeit", False) or False,
                    is_rollback=match_metadata.get("isRollback", False) or False,
                    r6_tracker_user_uuid=segment.get("attributes", {}).get("playerId", "Unknown"),
                    ubisoft_username=metadata.get("platformUserHandle", user_info.ubisoft_username_active),
                    operators=",".join(operator.get("name", "Unknown") for operator in metadata.get("operators", [])),
                    round_played_count=stats.get("roundsPlayed", {}).get("value", 0) or 0,
                    round_won_count=stats.get("roundsWon", {}).get("value", 0) or 0,
                    round_lost_count=stats.get("roundsLost", {}).get("value", 0) or 0,
                    round_disconnected_count=stats.get("roundsDisconnected", {}).get("value", 0) or 0,
                    kill_count=stats.get("kills", {}).get("value", 0) or 0,
                    death_count=stats.get("deaths", {}).get("value", 0) or 0,
                    assist_count=stats.get("assists", {}).get("value", 0) or 0,
                    head_shot_count=stats.get("headshots", {}).get("value", 0) or 0,
                    tk_count=stats.get("teamKills", {}).get("value", 0) or 0,
                    ace_count=stats.get("aces", {}).get("value", 0) or 0,
                    first_kill_count=stats.get("firstBloods", {}).get("value", 0) or 0,
                    first_death_count=stats.get("firstDeaths", {}).get("value", 0) or 0,
                    clutches_win_count=stats.get("clutches", {}).get("value", 0) or 0,
                    clutches_loss_count=stats.get("clutchesLost", {}).get("value", 0) or 0,
                    clutches_win_count_1v1=stats.get("clutches1v1", {}).get("value", 0) or 0,
                    clutches_win_count_1v2=stats.get("clutches1v2", {}).get("value", 0) or 0,
                    clutches_win_count_1v3=stats.get("clutches1v3", {}).get("value", 0) or 0,
                    clutches_win_count_1v4=stats.get("clutches1v4", {}).get("value", 0) or 0,
                    clutches_win_count_1v5=stats.get("clutches1v5", {}).get("value", 0) or 0,
                    clutches_lost_count_1v1=stats.get("clutchesLost1v1", {}).get("value", 0) or 0,
                    clutches_lost_count_1v2=stats.get("clutchesLost1v2", {}).get("value", 0) or 0,
                    clutches_lost_count_1v3=stats.get("clutchesLost1v3", {}).get("value", 0) or 0,
                    clutches_lost_count_1v4=stats.get("clutchesLost1v4", {}).get("value", 0) or 0,
                    clutches_lost_count_1v5=stats.get("clutchesLost1v5", {}).get("value", 0) or 0,
                    kill_1_count=stats.get("kills1K", {}).get("value", 0) or 0,
                    kill_2_count=stats.get("kills2K", {}).get("value", 0) or 0,
                    kill_3_count=stats.get("kills3K", {}).get("value", 0) or 0,
                    kill_4_count=stats.get("kills4K", {}).get("value", 0) or 0,
                    kill_5_count=stats.get("kills5K", {}).get("value", 0) or 0,
                    rank_points=stats.get("rankPoints", {}).get("value", 0) or 0,
                    rank_name=stats.get("rankPoints", {}).get("metadata", {}).get("name", "Unknown"),
                    points_gained=stats.get("rankPointsDelta", {}).get("value", 0) or 0,
                    rank_previous=stats.get("rankPointsPrevious", {}).get("value", 0) or 0,
                    kd_ratio=stats.get("kdRatio", {}).get("value", 0) or 0,
                    head_shot_percentage=stats.get("headshotPct", {}).get("value", 0) or 0,
                    kills_per_round=stats.get("killsPerRound", {}).get("value", 0) or 0,
                    deaths_per_round=stats.get("deathsPerRound", {}).get("value", 0) or 0,
                    assists_per_round=stats.get("assistsPerRound", {}).get("value", 0) or 0,
                    has_win=stats.get("wins", {}).get("value", 0) == 1,
                )
            )
        except (KeyError, IndexError, TypeError) as e:
            print_error_log(f"parse_json_from_full_matches: Error processing match data: {e}")
            continue
    return match_infos


def get_user_gaming_session_stats(
    username: str, from_datetime: datetime, list_matches: List[UserFullMatchStats]
) -> Optional[UserMatchInfoSessionAggregate]:
    """
    Get the aggregate of the user's gaming session. A gaming session is from the time we pass. It should be the last ~24h.
    """
    # Get the matches after the from_datetime
    matches_recent = [
        match for match in list_matches if match.match_timestamp > from_datetime and match.is_rollback is False
    ]
    if len(matches_recent) == 0:
        return None
    return UserMatchInfoSessionAggregate(
        matches_recent=matches_recent,
        match_count=len(matches_recent),
        match_win_count=sum(match.has_win for match in matches_recent),
        match_loss_count=len(matches_recent) - sum(match.has_win for match in matches_recent),
        total_kill_count=sum(match.kill_count for match in matches_recent),
        total_death_count=sum(match.death_count for match in matches_recent),
        total_assist_count=sum(match.assist_count for match in matches_recent),
        total_tk_count=sum(match.tk_count for match in matches_recent),
        started_rank_points=(
            matches_recent[-1].rank_points - (matches_recent[-1].points_gained or 0) if matches_recent else 0
        ),  # Subtract the points gained in the match to get the starting rank points
        ended_rank_points=matches_recent[0].rank_points if matches_recent else 0,
        total_gained_points=sum((match.points_gained or 0) for match in matches_recent),
        ubisoft_username_active=username,
        total_round_with_aces=sum(match.ace_count for match in matches_recent),
        total_round_with_3k=sum(match.kill_3_count for match in matches_recent),
        total_round_with_4k=sum(match.kill_4_count for match in matches_recent),
        total_clutches_win_count=sum(match.clutches_win_count for match in matches_recent),
        total_clutches_loss_count=sum(match.clutches_loss_count for match in matches_recent),
        total_first_death_count=sum(match.first_death_count for match in matches_recent),
        total_first_kill_count=sum(match.first_kill_count for match in matches_recent),
    )


def parse_json_max_rank(data_dict: dict) -> str:
    """
    Parse the JSON data to extract the max rank.
    """
    try:
        # Extract the rank from the JSON data
        segments = data_dict["data"]["segments"]
        match_infos = []
        for segment in segments:
            if segment.get("type") == "season":
                stats = segment.get("stats", {})
                max_rank_points = stats.get("maxRankPoints", {})
                value = max_rank_points.get("value", 0)
                rank_name = max_rank_points.get("metadata", {}).get("name", "Copper")
                if value is not None and isinstance(value, (int, float)) and value > 0:
                    # Only consider valid ranks with positive points
                    if isinstance(rank_name, str) and rank_name.strip() != "":
                        # Ensure rank_name is a non-empty string
                        match_infos.append((value, rank_name))
        # Find the highest rank
        for value, rank in sorted(match_infos, key=lambda x: x[0], reverse=True):
            if isinstance(rank, str):
                return rank.split(" ")[0].lower().capitalize()

        print_error_log("parse_json_max_rank: Rank not found")
        return "Copper"
    except KeyError as e:
        print_error_log(f"parse_json_max_rank: KeyError: {e} not found in the JSON data.")
        return "Copper"
    except TypeError as e:
        print_error_log(f"parse_json_max_rank: TypeError: Unexpected data format - {e}")
        return "Copper"


def parse_json_user_full_stats_info(user_id: int, json_content: dict) -> UserInformation:
    """
    Parse the JSON content from the R6 Tracker API and create a UserInformation object

    Args:
        user_id: Discord user ID
        json_content: JSON content from the R6 Tracker API, can be a string or already parsed dict

    Returns:
        UserInformation object populated with data from the JSON
    """
    # Parse JSON if it's a string
    if isinstance(json_content, str):
        data = json.loads(json_content)
    else:
        data = json_content

    # Get the main data section
    main_data = data.get("data", {})

    # Extract platform info for r6_tracker_user_uuid
    platform_info = main_data.get("platformInfo", {})
    r6_tracker_user_uuid = platform_info.get("platformUserId", "")

    # Get overview stats
    overview_segment = None
    for segment in main_data.get("segments", []):
        if segment.get("type") == "overview":
            overview_segment = segment
            break

    if not overview_segment:
        # If no overview segment found, create an empty UserInformation object
        return UserInformation(user_id=user_id, r6_tracker_user_uuid=r6_tracker_user_uuid)

    # Extract gamemode stats (ranked, arcade, quickmatch)
    ranked_segment = None
    arcade_segment = None
    quickmatch_segment = None

    for segment in main_data.get("segments", []):
        if segment.get("type") == "gamemode":
            if segment.get("attributes", {}).get("sessionType") == "ranked":
                ranked_segment = segment
            elif segment.get("attributes", {}).get("sessionType") == "arcade":
                arcade_segment = segment
            elif segment.get("attributes", {}).get("sessionType") in ["quickplay", "standard"]:
                quickmatch_segment = segment

    # Helper function to get stat value
    def get_stat_value(segment, stat_name, default=0):
        if not segment:
            return default
        return segment.get("stats", {}).get(stat_name, {}).get("value", default)

    # Extract playstyle percentages
    def get_percentage(segment, stat_name, default=0.0):
        if not segment:
            return default
        value = segment.get("stats", {}).get(stat_name, {}).get("value", default)
        # Convert to percentage if it's not already
        if value and value > 0 and value <= 1:
            return value * 100
        return value or default

    # Create UserInformation object
    return UserInformation(
        user_id=user_id,
        r6_tracker_user_uuid=r6_tracker_user_uuid,
        # Overview stats
        total_matches_played=get_stat_value(overview_segment, "matchesPlayed"),
        total_matches_won=get_stat_value(overview_segment, "matchesWon"),
        total_matches_lost=get_stat_value(overview_segment, "matchesLost"),
        total_matches_abandoned=get_stat_value(overview_segment, "matchesAbandoned"),
        time_played_seconds=get_stat_value(overview_segment, "timePlayed"),
        total_kills=get_stat_value(overview_segment, "kills"),
        total_deaths=get_stat_value(overview_segment, "deaths"),
        total_attacker_round_wins=get_stat_value(overview_segment, "attackerRoundsWon"),
        total_defender_round_wins=get_stat_value(overview_segment, "defenderRoundsWon"),
        total_headshots=get_stat_value(overview_segment, "headshots"),
        total_headshots_missed=get_stat_value(overview_segment, "headshotsMissed"),
        headshot_percentage=get_stat_value(overview_segment, "headshotPercentage", 0.0),
        total_wall_bang=get_stat_value(overview_segment, "wallbangs"),
        total_damage=get_stat_value(overview_segment, "damageDealt"),
        total_assists=get_stat_value(overview_segment, "assists"),
        total_team_kills=get_stat_value(overview_segment, "teamKills"),
        # Attacker playstyles
        attacked_breacher_count=get_stat_value(overview_segment, "playstyleAttackerBreacher"),
        attacked_breacher_percentage=get_percentage(overview_segment, "playstyleAttackerBreacher"),
        attacked_fragger_count=get_stat_value(overview_segment, "playstyleAttackerEntryFragger"),
        attacked_fragger_percentage=get_percentage(overview_segment, "playstyleAttackerEntryFragger"),
        attacked_intel_count=get_stat_value(overview_segment, "playstyleAttackerIntelProvider"),
        attacked_intel_percentage=get_percentage(overview_segment, "playstyleAttackerIntelProvider"),
        attacked_roam_count=get_stat_value(overview_segment, "playstyleAttackerRoamClearer"),
        attacked_roam_percentage=get_percentage(overview_segment, "playstyleAttackerRoamClearer"),
        attacked_support_count=get_stat_value(overview_segment, "playstyleAttackerSupporter"),
        attacked_support_percentage=get_percentage(overview_segment, "playstyleAttackerSupporter"),
        attacked_utility_count=get_stat_value(overview_segment, "playstyleAttackerUtilityClearer"),
        attacked_utility_percentage=get_percentage(overview_segment, "playstyleAttackerUtilityClearer"),
        # Defender playstyles
        defender_debuffer_count=get_stat_value(overview_segment, "playstyleDefenderDebuffer"),
        defender_debuffer_percentage=get_percentage(overview_segment, "playstyleDefenderDebuffer"),
        defender_entry_denier_count=get_stat_value(overview_segment, "playstyleDefenderEntryDenier"),
        defender_entry_denier_percentage=get_percentage(overview_segment, "playstyleDefenderEntryDenier"),
        defender_intel_count=get_stat_value(overview_segment, "playstyleDefenderIntelProvider"),
        defender_intel_percentage=get_percentage(overview_segment, "playstyleDefenderIntelProvider"),
        defender_support_count=get_stat_value(overview_segment, "playstyleDefenderSupporter"),
        defender_support_percentage=get_percentage(overview_segment, "playstyleDefenderSupporter"),
        defender_trapper_count=get_stat_value(overview_segment, "playstyleDefenderTrapper"),
        defender_trapper_percentage=get_percentage(overview_segment, "playstyleDefenderTrapper"),
        defender_utility_denier_count=get_stat_value(overview_segment, "playstyleDefenderUtilityDenier"),
        defender_utility_denier_percentage=get_percentage(overview_segment, "playstyleDefenderUtilityDenier"),
        # Overall stats
        kd_ratio=get_stat_value(overview_segment, "kdRatio", 0.0),
        kill_per_match=get_stat_value(overview_segment, "killsPerMatch", 0.0),
        kill_per_minute=get_stat_value(overview_segment, "killsPerMin", 0.0),
        win_percentage=get_stat_value(overview_segment, "winPercentage", 0.0),
        # Ranked stats
        rank_match_played=get_stat_value(ranked_segment, "matchesPlayed"),
        rank_match_won=get_stat_value(ranked_segment, "matchesWon"),
        rank_match_lost=get_stat_value(ranked_segment, "matchesLost"),
        rank_match_abandoned=get_stat_value(ranked_segment, "matchesAbandoned"),
        rank_kills_count=get_stat_value(ranked_segment, "kills"),
        rank_deaths_count=get_stat_value(ranked_segment, "deaths"),
        rank_kd_ratio=get_stat_value(ranked_segment, "kdRatio", 0.0),
        rank_kill_per_match=get_stat_value(ranked_segment, "killsPerMatch", 0.0),
        rank_win_percentage=get_stat_value(ranked_segment, "winPercentage", 0.0),
        # Arcade stats
        arcade_match_played=get_stat_value(arcade_segment, "matchesPlayed"),
        arcade_match_won=get_stat_value(arcade_segment, "matchesWon"),
        arcade_match_lost=get_stat_value(arcade_segment, "matchesLost"),
        arcade_match_abandoned=get_stat_value(arcade_segment, "matchesAbandoned"),
        arcade_kills_count=get_stat_value(arcade_segment, "kills"),
        arcade_deaths_count=get_stat_value(arcade_segment, "deaths"),
        arcade_kd_ratio=get_stat_value(arcade_segment, "kdRatio", 0.0),
        arcade_kill_per_match=get_stat_value(arcade_segment, "killsPerMatch", 0.0),
        arcade_win_percentage=get_stat_value(arcade_segment, "winPercentage", 0.0),
        # Quickmatch stats
        quickmatch_match_played=get_stat_value(quickmatch_segment, "matchesPlayed"),
        quickmatch_match_won=get_stat_value(quickmatch_segment, "matchesWon"),
        quickmatch_match_lost=get_stat_value(quickmatch_segment, "matchesLost"),
        quickmatch_match_abandoned=get_stat_value(quickmatch_segment, "matchesAbandoned"),
        quickmatch_kills_count=get_stat_value(quickmatch_segment, "kills"),
        quickmatch_deaths_count=get_stat_value(quickmatch_segment, "deaths"),
        quickmatch_kd_ratio=get_stat_value(quickmatch_segment, "kdRatio", 0.0),
        quickmatch_kill_per_match=get_stat_value(quickmatch_segment, "killsPerMatch", 0.0),
        quickmatch_win_percentage=get_stat_value(quickmatch_segment, "winPercentage", 0.0),
    )


def parse_json_user_info(user_id: int, json_content: Union[str, Dict[str, Any]]) -> UserInformation:
    """
    Parse the JSON content from the R6 Tracker API and create a UserInformation object

    Args:
        user_id: Discord user ID
        json_content: JSON content from the R6 Tracker API, can be a string or already parsed dict

    Returns:
        UserInformation object populated with data from the JSON
    """
    # Parse JSON if it's a string
    if isinstance(json_content, str):
        data = json.loads(json_content)
    else:
        data = json_content

    # Get the main data section
    main_data = data.get("data", {})

    # Extract platform info for r6_tracker_user_uuid
    platform_info = main_data.get("platformInfo", {})
    r6_tracker_user_uuid = platform_info.get("platformUserId", "")

    # Get overview stats
    overview_segment = None
    for segment in main_data.get("segments", []):
        if segment.get("type") == "overview":
            overview_segment = segment
            break

    if not overview_segment:
        # If no overview segment found, create an empty UserInformation object
        return UserInformation(user_id=user_id, r6_tracker_user_uuid=r6_tracker_user_uuid)

    overview_stats = overview_segment.get("stats", {})

    # Extract gamemode stats (ranked, arcade, quickmatch)
    ranked_segment = None
    arcade_segment = None
    quickmatch_segment = None

    for segment in main_data.get("segments", []):
        if segment.get("type") == "gamemode":
            if segment.get("attributes", {}).get("sessionType") == "ranked":
                ranked_segment = segment
            elif segment.get("attributes", {}).get("sessionType") == "arcade":
                arcade_segment = segment
            elif segment.get("attributes", {}).get("sessionType") in ["quickplay", "standard"]:
                quickmatch_segment = segment

    # Helper function to get stat value
    def get_stat_value(segment, stat_name, default=0):
        if not segment:
            return default
        return segment.get("stats", {}).get(stat_name, {}).get("value", default)

    # Extract playstyle percentages
    def get_percentage(segment, stat_name, default=0.0):
        if not segment:
            return default
        value = segment.get("stats", {}).get(stat_name, {}).get("metadata", {}).get("usage", {}).get("value", default)
        # Convert to percentage if it's not already
        # if value and value > 0 and value <= 1:
        #     return value * 100
        return value or default

    # Create UserInformation object
    return UserInformation(
        user_id=user_id,
        r6_tracker_user_uuid=r6_tracker_user_uuid,
        # Overview stats
        total_matches_played=get_stat_value(overview_segment, "matchesPlayed"),
        total_matches_won=get_stat_value(overview_segment, "matchesWon"),
        total_matches_lost=get_stat_value(overview_segment, "matchesLost"),
        total_matches_abandoned=get_stat_value(overview_segment, "matchesAbandoned"),
        time_played_seconds=get_stat_value(overview_segment, "timePlayed"),
        total_kills=get_stat_value(overview_segment, "kills"),
        total_deaths=get_stat_value(overview_segment, "deaths"),
        total_attacker_round_wins=get_stat_value(overview_segment, "attackerRoundsWon"),
        total_defender_round_wins=get_stat_value(overview_segment, "defenderRoundsWon"),
        total_headshots=get_stat_value(overview_segment, "headshots"),
        total_headshots_missed=get_stat_value(overview_segment, "headshotsMissed"),
        headshot_percentage=get_stat_value(overview_segment, "headshotPercentage", 0.0),
        total_wall_bang=get_stat_value(overview_segment, "wallbangs"),
        total_damage=get_stat_value(overview_segment, "damageDealt"),
        total_assists=get_stat_value(overview_segment, "assists"),
        total_team_kills=get_stat_value(overview_segment, "teamKills"),
        # Attacker playstyles
        attacked_breacher_count=get_stat_value(overview_segment, "playstyleAttackerBreacher"),
        attacked_breacher_percentage=get_percentage(overview_segment, "playstyleAttackerBreacher"),
        attacked_fragger_count=get_stat_value(overview_segment, "playstyleAttackerEntryFragger"),
        attacked_fragger_percentage=get_percentage(overview_segment, "playstyleAttackerEntryFragger"),
        attacked_intel_count=get_stat_value(overview_segment, "playstyleAttackerIntelProvider"),
        attacked_intel_percentage=get_percentage(overview_segment, "playstyleAttackerIntelProvider"),
        attacked_roam_count=get_stat_value(overview_segment, "playstyleAttackerRoamClearer"),
        attacked_roam_percentage=get_percentage(overview_segment, "playstyleAttackerRoamClearer"),
        attacked_support_count=get_stat_value(overview_segment, "playstyleAttackerSupporter"),
        attacked_support_percentage=get_percentage(overview_segment, "playstyleAttackerSupporter"),
        attacked_utility_count=get_stat_value(overview_segment, "playstyleAttackerUtilityClearer"),
        attacked_utility_percentage=get_percentage(overview_segment, "playstyleAttackerUtilityClearer"),
        # Defender playstyles
        defender_debuffer_count=get_stat_value(overview_segment, "playstyleDefenderDebuffer"),
        defender_debuffer_percentage=get_percentage(overview_segment, "playstyleDefenderDebuffer"),
        defender_entry_denier_count=get_stat_value(overview_segment, "playstyleDefenderEntryDenier"),
        defender_entry_denier_percentage=get_percentage(overview_segment, "playstyleDefenderEntryDenier"),
        defender_intel_count=get_stat_value(overview_segment, "playstyleDefenderIntelProvider"),
        defender_intel_percentage=get_percentage(overview_segment, "playstyleDefenderIntelProvider"),
        defender_support_count=get_stat_value(overview_segment, "playstyleDefenderSupporter"),
        defender_support_percentage=get_percentage(overview_segment, "playstyleDefenderSupporter"),
        defender_trapper_count=get_stat_value(overview_segment, "playstyleDefenderTrapper"),
        defender_trapper_percentage=get_percentage(overview_segment, "playstyleDefenderTrapper"),
        defender_utility_denier_count=get_stat_value(overview_segment, "playstyleDefenderUtilityDenier"),
        defender_utility_denier_percentage=get_percentage(overview_segment, "playstyleDefenderUtilityDenier"),
        # Overall stats
        kd_ratio=get_stat_value(overview_segment, "kdRatio", 0.0),
        kill_per_match=get_stat_value(overview_segment, "killsPerMatch", 0.0),
        kill_per_minute=get_stat_value(overview_segment, "killsPerMin", 0.0),
        win_percentage=get_stat_value(overview_segment, "winPercentage", 0.0),
        # Ranked stats
        rank_match_played=get_stat_value(ranked_segment, "matchesPlayed"),
        rank_match_won=get_stat_value(ranked_segment, "matchesWon"),
        rank_match_lost=get_stat_value(ranked_segment, "matchesLost"),
        rank_match_abandoned=get_stat_value(ranked_segment, "matchesAbandoned"),
        rank_kills_count=get_stat_value(ranked_segment, "kills"),
        rank_deaths_count=get_stat_value(ranked_segment, "deaths"),
        rank_kd_ratio=get_stat_value(ranked_segment, "kdRatio", 0.0),
        rank_kill_per_match=get_stat_value(ranked_segment, "killsPerMatch", 0.0),
        rank_win_percentage=get_stat_value(ranked_segment, "winPercentage", 0.0),
        # Arcade stats
        arcade_match_played=get_stat_value(arcade_segment, "matchesPlayed"),
        arcade_match_won=get_stat_value(arcade_segment, "matchesWon"),
        arcade_match_lost=get_stat_value(arcade_segment, "matchesLost"),
        arcade_match_abandoned=get_stat_value(arcade_segment, "matchesAbandoned"),
        arcade_kills_count=get_stat_value(arcade_segment, "kills"),
        arcade_deaths_count=get_stat_value(arcade_segment, "deaths"),
        arcade_kd_ratio=get_stat_value(arcade_segment, "kdRatio", 0.0),
        arcade_kill_per_match=get_stat_value(arcade_segment, "killsPerMatch", 0.0),
        arcade_win_percentage=get_stat_value(arcade_segment, "winPercentage", 0.0),
        # Quickmatch stats
        quickmatch_match_played=get_stat_value(quickmatch_segment, "matchesPlayed"),
        quickmatch_match_won=get_stat_value(quickmatch_segment, "matchesWon"),
        quickmatch_match_lost=get_stat_value(quickmatch_segment, "matchesLost"),
        quickmatch_match_abandoned=get_stat_value(quickmatch_segment, "matchesAbandoned"),
        quickmatch_kills_count=get_stat_value(quickmatch_segment, "kills"),
        quickmatch_deaths_count=get_stat_value(quickmatch_segment, "deaths"),
        quickmatch_kd_ratio=get_stat_value(quickmatch_segment, "kdRatio", 0.0),
        quickmatch_kill_per_match=get_stat_value(quickmatch_segment, "killsPerMatch", 0.0),
        quickmatch_win_percentage=get_stat_value(quickmatch_segment, "winPercentage", 0.0),
    )
