"""
Analytics Match Data Access Module

This module handles match statistics persistence and retrieval, including batch
insertion of match data and user statistics from R6 Tracker.

Functions:
- insert_if_nonexistant_full_match_info: Batch insert match statistics (avoid duplicates)
- data_access_fetch_user_full_match_info: Fetch paginated match history for user
- data_access_fetch_users_full_match_info: Fetch paginated match history for multiple users
- insert_if_nonexistant_full_user_info: Insert/update aggregated user statistics
- data_access_fetch_user_full_user_info: Fetch user's overall statistics
"""

from dataclasses import asdict
from datetime import datetime
import json
from typing import Union, List

from deps.analytic_constants import (
    SELECT_USER_FULL_MATCH_INFO,
    SELECT_USER_FULL_STATS_INFO,
)
from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats, UserInformation
from deps.system_database import database_manager
from deps.log import print_error_log, print_log


def data_access_fetch_recent_win_loss(user_id: int, match_count: int = 10) -> tuple[int, int]:
    """
    Get win/loss counts from last N matches for a user.

    Args:
        user_id: Discord user ID
        match_count: Number of recent matches to analyze (default: 10)

    Returns:
        Tuple of (wins, losses)
    """
    query = """
        SELECT
            SUM(CASE WHEN has_win = 1 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN has_win = 0 THEN 1 ELSE 0 END) as losses
        FROM (
            SELECT has_win
            FROM user_full_match_info
            WHERE user_id = :user_id AND is_rollback = 0
            ORDER BY match_timestamp DESC
            LIMIT :match_count
        )
    """
    result = database_manager.get_cursor().execute(query, {"user_id": user_id, "match_count": match_count}).fetchone()
    return (result[0] or 0, result[1] or 0)


def insert_if_nonexistant_full_match_info(user_info: UserInfo, list_matches: list[UserFullMatchStats]) -> None:
    """
    We have a list of full match info, we want to insert them if they do not exist
    A match might exist in the case we fetched more and the user already had some matches recorded.
    """

    # Remove duplicate match id (some times rollback appears twice)
    list_matches = list({match.match_uuid: match for match in list_matches}.values())

    match_user_pairs = [
        (
            match.match_uuid,
            match.user_id,
        )
        for match in list_matches
    ]

    # Construct a query using AND and OR instead of row-value comparisons
    conditions = " OR ".join(["(match_uuid = ? AND user_id = ?)" for _ in match_user_pairs])

    if not conditions.strip():  # Ensure conditions exist
        print_log("insert_if_nonexistant_full_match_info: No user-match pair to insert, leaving the function early")
        return

    query = f"""
        SELECT match_uuid, user_id
        FROM user_full_match_info
        WHERE {conditions}
    """
    params = [item for pair in match_user_pairs for item in pair]

    if len(params) == 0:
        print_log("insert_if_nonexistant_full_match_info: No match to insert, leaving the function early")
        return

    # Get the list of match that is already in the database that matches a match+user pair
    database_manager.get_cursor().execute(query, params)

    existing_records = database_manager.get_cursor().fetchall()
    existing_set = set(existing_records)
    filtered_data = [obj for obj in list_matches if (obj.match_uuid, obj.user_id) not in existing_set]
    print_log(
        f"insert_if_nonexistant_full_match_info: Found {len(filtered_data)} new matches to insert out of {len(list_matches)} for {user_info.display_name}"
    )
    # Try to insert the match that are not yet in the database
    # Todo: Batch insert
    last_match: Union[UserFullMatchStats, None] = None
    try:
        with database_manager.data_access_transaction():
            cursor = database_manager.get_cursor()
            for match in filtered_data:
                last_match = match
                cursor.execute(
                    """
                INSERT INTO user_full_match_info (
                    match_uuid,
                    user_id,
                    match_timestamp,
                    match_duration_ms,
                    data_center,
                    session_type,
                    map_name,
                    is_surrender,
                    is_forfeit,
                    is_rollback,
                    r6_tracker_user_uuid,
                    ubisoft_username,
                    operators,
                    round_played_count,
                    round_won_count,
                    round_lost_count,
                    round_disconnected_count,
                    kill_count,
                    death_count,
                    assist_count,
                    head_shot_count,
                    tk_count,
                    ace_count,
                    first_kill_count,
                    first_death_count,
                    clutches_win_count,
                    clutches_loss_count,
                    clutches_win_count_1v1,
                    clutches_win_count_1v2,
                    clutches_win_count_1v3,
                    clutches_win_count_1v4,
                    clutches_win_count_1v5,
                    clutches_lost_count_1v1,
                    clutches_lost_count_1v2,
                    clutches_lost_count_1v3,
                    clutches_lost_count_1v4,
                    clutches_lost_count_1v5,
                    kill_1_count,
                    kill_2_count,
                    kill_3_count,
                    kill_4_count,
                    kill_5_count,
                    rank_points,
                    rank_name,
                    points_gained,
                    rank_previous,
                    kd_ratio,
                    head_shot_percentage,
                    kills_per_round,
                    deaths_per_round,
                    assists_per_round,
                    has_win)
                VALUES (
                    :match_uuid,
                    :user_id,
                    :match_timestamp,
                    :match_duration_ms,
                    :data_center,
                    :session_type,
                    :map_name,
                    :is_surrender,
                    :is_forfeit,
                    :is_rollback,
                    :r6_tracker_user_uuid,
                    :ubisoft_username,
                    :operators,
                    :round_played_count,
                    :round_won_count,
                    :round_lost_count,
                    :round_disconnected_count,
                    :kill_count,
                    :death_count,
                    :assist_count,
                    :head_shot_count,
                    :tk_count,
                    :ace_count,
                    :first_kill_count,
                    :first_death_count,
                    :clutches_win_count,
                    :clutches_loss_count,
                    :clutches_win_count_1v1,
                    :clutches_win_count_1v2,
                    :clutches_win_count_1v3,
                    :clutches_win_count_1v4,
                    :clutches_win_count_1v5,
                    :clutches_lost_count_1v1,
                    :clutches_lost_count_1v2,
                    :clutches_lost_count_1v3,
                    :clutches_lost_count_1v4,
                    :clutches_lost_count_1v5,
                    :kill_1_count,
                    :kill_2_count,
                    :kill_3_count,
                    :kill_4_count,
                    :kill_5_count,
                    :rank_points,
                    :rank_name,
                    :points_gained,
                    :rank_previous,
                    :kd_ratio,
                    :head_shot_percentage,
                    :kills_per_round,
                    :deaths_per_round,
                    :assists_per_round,
                    :has_win
                )
                """,
                    {
                        "match_uuid": match.match_uuid,
                        "user_id": user_info.id,
                        "match_timestamp": match.match_timestamp,
                        "match_duration_ms": match.match_duration_ms,
                        "data_center": match.data_center,
                        "session_type": match.session_type,
                        "map_name": match.map_name,
                        "is_surrender": match.is_surrender,
                        "is_forfeit": match.is_forfeit,
                        "is_rollback": match.is_rollback,
                        "r6_tracker_user_uuid": match.r6_tracker_user_uuid,
                        "ubisoft_username": match.ubisoft_username,
                        "operators": match.operators,
                        "round_played_count": match.round_played_count,
                        "round_won_count": match.round_won_count,
                        "round_lost_count": match.round_lost_count,
                        "round_disconnected_count": match.round_disconnected_count,
                        "kill_count": match.kill_count,
                        "death_count": match.death_count,
                        "assist_count": match.assist_count,
                        "head_shot_count": match.head_shot_count,
                        "tk_count": match.tk_count,
                        "ace_count": match.ace_count,
                        "first_kill_count": match.first_kill_count,
                        "first_death_count": match.first_death_count,
                        "clutches_win_count": match.clutches_win_count,
                        "clutches_loss_count": match.clutches_loss_count,
                        "clutches_win_count_1v1": match.clutches_win_count_1v1,
                        "clutches_win_count_1v2": match.clutches_win_count_1v2,
                        "clutches_win_count_1v3": match.clutches_win_count_1v3,
                        "clutches_win_count_1v4": match.clutches_win_count_1v4,
                        "clutches_win_count_1v5": match.clutches_win_count_1v5,
                        "clutches_lost_count_1v1": match.clutches_lost_count_1v1,
                        "clutches_lost_count_1v2": match.clutches_lost_count_1v2,
                        "clutches_lost_count_1v3": match.clutches_lost_count_1v3,
                        "clutches_lost_count_1v4": match.clutches_lost_count_1v4,
                        "clutches_lost_count_1v5": match.clutches_lost_count_1v5,
                        "kill_1_count": match.kill_1_count,
                        "kill_2_count": match.kill_2_count,
                        "kill_3_count": match.kill_3_count,
                        "kill_4_count": match.kill_4_count,
                        "kill_5_count": match.kill_5_count,
                        "rank_points": match.rank_points,
                        "rank_name": match.rank_name,
                        "points_gained": match.points_gained,
                        "rank_previous": match.rank_previous,
                        "kd_ratio": match.kd_ratio,
                        "head_shot_percentage": match.head_shot_percentage,
                        "kills_per_round": match.kills_per_round,
                        "deaths_per_round": match.deaths_per_round,
                        "assists_per_round": match.assists_per_round,
                        "has_win": match.has_win,
                    },
                )
                print_log(
                    f"insert_if_nonexistant_full_match_info: Inserted match {cursor.rowcount} for {user_info.display_name}. Match id {match.match_uuid} and user id {user_info.id}"
                )
        # End transaction
    except Exception as e:
        if last_match is None:
            print_error_log("insert_if_nonexistant_full_match_info: Error inserting match: No match to insert")
        stringify_match = json.dumps(asdict(last_match), indent=4) if last_match is not None else "No match data"
        print_error_log(f"insert_if_nonexistant_full_match_info: Error inserting match: {e}\n{stringify_match}")
        raise e


def data_access_fetch_user_full_match_info(
    user_id: int, page_number_zero_index: int = 0, page_size: int = 50
) -> list[UserFullMatchStats]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    query = f"""
        SELECT {SELECT_USER_FULL_MATCH_INFO}
        FROM user_full_match_info
        WHERE user_full_match_info.user_id = :user_id
        ORDER BY match_timestamp DESC
        LIMIT :page_size OFFSET :offset
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id, "page_size": page_size, "offset": page_number_zero_index * page_size},
        )
    ).fetchall()
    # Convert the result to a list of Stats
    return [UserFullMatchStats.from_db_row(row) for row in result]


def data_access_fetch_users_full_match_info(
    user_ids: list[int], page_number_zero_index: int = 0, page_size: int = 50
) -> list[UserFullMatchStats]:
    """
    Fetch all connect and disconnect events from the user_activity table for a list of user ids
    """
    if not user_ids:
        return []

    list_ids = ",".join("?" for _ in user_ids)
    query = f"""
        SELECT {SELECT_USER_FULL_MATCH_INFO}
        FROM user_full_match_info
        WHERE user_full_match_info.user_id IN ({list_ids})
        ORDER BY match_timestamp DESC
        LIMIT :page_size OFFSET :offset
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            user_ids + [page_size, page_number_zero_index * page_size],
        )
    ).fetchall()
    # Convert the result to a list of Stats
    return [UserFullMatchStats.from_db_row(row) for row in result]


def data_access_fetch_user_matches_in_time_range(
    user_ids: list[int], from_timestamp: Union[datetime, None], to_timestamp: Union[datetime, None] = None
) -> dict[int, list[UserFullMatchStats]]:
    """
    Fetch matches for multiple users within a specific time range.

    Args:
        user_ids: List of Discord user IDs
        from_timestamp: Start of time range (inclusive), None for unbounded
        to_timestamp: End of time range (inclusive), None for unbounded

    Returns:
        Dictionary mapping user_id to list of matches
    """
    if not user_ids:
        return {}

    # Build query with proper parameter binding
    placeholders = ",".join(["?"] * len(user_ids))

    # Build WHERE clause components
    where_clauses = [f"user_id IN ({placeholders})"]
    params = list(user_ids)

    if from_timestamp is not None:
        where_clauses.append("match_timestamp >= ?")
        params.append(from_timestamp)

    if to_timestamp is not None:
        where_clauses.append("match_timestamp <= ?")
        params.append(to_timestamp)

    where_clause = " AND ".join(where_clauses)

    query = f"""
        SELECT {SELECT_USER_FULL_MATCH_INFO}
        FROM user_full_match_info
        WHERE {where_clause}
        ORDER BY match_timestamp DESC
    """

    # Execute query
    result = database_manager.get_cursor().execute(query, params).fetchall()

    # Group by user_id
    matches_by_user = {}
    for row in result:
        match = UserFullMatchStats.from_db_row(row)
        if match.user_id not in matches_by_user:
            matches_by_user[match.user_id] = []
        matches_by_user[match.user_id].append(match)

    return matches_by_user


def insert_if_nonexistant_full_user_info(user_info: UserInfo, user_information: UserInformation) -> None:
    """
    Insert or update the user full stats info if it does not exist.
    This function checks if stats already exist for the user in the database
    and inserts the new stats if they don't.

    Args:
        user_info: The UserInfo object containing the user's basic information
        user_information: The UserInformation object containing the detailed user statistics
    """
    # Wrap DELETE + INSERT in transaction to prevent data loss on failure
    try:
        with database_manager.data_access_transaction() as cursor:
            # Check if a record for this user already exists and delete it
            query = """
                DELETE FROM user_full_stats_info
                WHERE user_id = ?
            """

            cursor.execute(query, (user_info.id,))
            deleted_count = cursor.rowcount

            if deleted_count > 0:
                print_log(
                    f"insert_if_nonexistant_full_user_info: Deleted {deleted_count} existing record(s) for user {user_info.display_name}"
                )

            # Insert the new record
            cursor.execute(
            """
            INSERT INTO user_full_stats_info (
                user_id,
                r6_tracker_user_uuid,
                total_matches_played,
                total_matches_won,
                total_matches_lost,
                total_matches_abandoned,
                time_played_seconds,
                total_kills,
                total_deaths,
                total_attacker_round_wins,
                total_defender_round_wins,
                total_headshots,
                total_headshots_missed,
                headshot_percentage,
                total_wall_bang,
                total_damage,
                total_assists,
                total_team_kills,
                attacked_breacher_count,
                attacked_breacher_percentage,
                attacked_fragger_count,
                attacked_fragger_percentage,
                attacked_intel_count,
                attacked_intel_percentage,
                attacked_roam_count,
                attacked_roam_percentage,
                attacked_support_count,
                attacked_support_percentage,
                attacked_utility_count,
                attacked_utility_percentage,
                defender_debuffer_count,
                defender_debuffer_percentage,
                defender_entry_denier_count,
                defender_entry_denier_percentage,
                defender_intel_count,
                defender_intel_percentage,
                defender_support_count,
                defender_support_percentage,
                defender_trapper_count,
                defender_trapper_percentage,
                defender_utility_denier_count,
                defender_utility_denier_percentage,
                kd_ratio,
                kill_per_match,
                kill_per_minute,
                win_percentage,
                rank_match_played,
                rank_match_won,
                rank_match_lost,
                rank_match_abandoned,
                rank_kills_count,
                rank_deaths_count,
                rank_kd_ratio,
                rank_kill_per_match,
                rank_win_percentage,
                arcade_match_played,
                arcade_match_won,
                arcade_match_lost,
                arcade_match_abandoned,
                arcade_kills_count,
                arcade_deaths_count,
                arcade_kd_ratio,
                arcade_kill_per_match,
                arcade_win_percentage,
                quickmatch_match_played,
                quickmatch_match_won,
                quickmatch_match_lost,
                quickmatch_match_abandoned,
                quickmatch_kills_count,
                quickmatch_deaths_count,
                quickmatch_kd_ratio,
                quickmatch_kill_per_match,
                quickmatch_win_percentage
            )
            VALUES (
                :user_id,
                :r6_tracker_user_uuid,
                :total_matches_played,
                :total_matches_won,
                :total_matches_lost,
                :total_matches_abandoned,
                :time_played_seconds,
                :total_kills,
                :total_deaths,
                :total_attacker_round_wins,
                :total_defender_round_wins,
                :total_headshots,
                :total_headshots_missed,
                :headshot_percentage,
                :total_wall_bang,
                :total_damage,
                :total_assists,
                :total_team_kills,
                :attacked_breacher_count,
                :attacked_breacher_percentage,
                :attacked_fragger_count,
                :attacked_fragger_percentage,
                :attacked_intel_count,
                :attacked_intel_percentage,
                :attacked_roam_count,
                :attacked_roam_percentage,
                :attacked_support_count,
                :attacked_support_percentage,
                :attacked_utility_count,
                :attacked_utility_percentage,
                :defender_debuffer_count,
                :defender_debuffer_percentage,
                :defender_entry_denier_count,
                :defender_entry_denier_percentage,
                :defender_intel_count,
                :defender_intel_percentage,
                :defender_support_count,
                :defender_support_percentage,
                :defender_trapper_count,
                :defender_trapper_percentage,
                :defender_utility_denier_count,
                :defender_utility_denier_percentage,
                :kd_ratio,
                :kill_per_match,
                :kill_per_minute,
                :win_percentage,
                :rank_match_played,
                :rank_match_won,
                :rank_match_lost,
                :rank_match_abandoned,
                :rank_kills_count,
                :rank_deaths_count,
                :rank_kd_ratio,
                :rank_kill_per_match,
                :rank_win_percentage,
                :arcade_match_played,
                :arcade_match_won,
                :arcade_match_lost,
                :arcade_match_abandoned,
                :arcade_kills_count,
                :arcade_deaths_count,
                :arcade_kd_ratio,
                :arcade_kill_per_match,
                :arcade_win_percentage,
                :quickmatch_match_played,
                :quickmatch_match_won,
                :quickmatch_match_lost,
                :quickmatch_match_abandoned,
                :quickmatch_kills_count,
                :quickmatch_deaths_count,
                :quickmatch_kd_ratio,
                :quickmatch_kill_per_match,
                :quickmatch_win_percentage
            )
            """,
            {
                "user_id": user_info.id,
                "r6_tracker_user_uuid": user_information.r6_tracker_user_uuid,
                "total_matches_played": user_information.total_matches_played,
                "total_matches_won": user_information.total_matches_won,
                "total_matches_lost": user_information.total_matches_lost,
                "total_matches_abandoned": user_information.total_matches_abandoned,
                "time_played_seconds": user_information.time_played_seconds,
                "total_kills": user_information.total_kills,
                "total_deaths": user_information.total_deaths,
                "total_attacker_round_wins": user_information.total_attacker_round_wins,
                "total_defender_round_wins": user_information.total_defender_round_wins,
                "total_headshots": user_information.total_headshots,
                "total_headshots_missed": user_information.total_headshots_missed,
                "headshot_percentage": user_information.headshot_percentage,
                "total_wall_bang": user_information.total_wall_bang,
                "total_damage": user_information.total_damage,
                "total_assists": user_information.total_assists,
                "total_team_kills": user_information.total_team_kills,
                "attacked_breacher_count": user_information.attacked_breacher_count,
                "attacked_breacher_percentage": user_information.attacked_breacher_percentage,
                "attacked_fragger_count": user_information.attacked_fragger_count,
                "attacked_fragger_percentage": user_information.attacked_fragger_percentage,
                "attacked_intel_count": user_information.attacked_intel_count,
                "attacked_intel_percentage": user_information.attacked_intel_percentage,
                "attacked_roam_count": user_information.attacked_roam_count,
                "attacked_roam_percentage": user_information.attacked_roam_percentage,
                "attacked_support_count": user_information.attacked_support_count,
                "attacked_support_percentage": user_information.attacked_support_percentage,
                "attacked_utility_count": user_information.attacked_utility_count,
                "attacked_utility_percentage": user_information.attacked_utility_percentage,
                "defender_debuffer_count": user_information.defender_debuffer_count,
                "defender_debuffer_percentage": user_information.defender_debuffer_percentage,
                "defender_entry_denier_count": user_information.defender_entry_denier_count,
                "defender_entry_denier_percentage": user_information.defender_entry_denier_percentage,
                "defender_intel_count": user_information.defender_intel_count,
                "defender_intel_percentage": user_information.defender_intel_percentage,
                "defender_support_count": user_information.defender_support_count,
                "defender_support_percentage": user_information.defender_support_percentage,
                "defender_trapper_count": user_information.defender_trapper_count,
                "defender_trapper_percentage": user_information.defender_trapper_percentage,
                "defender_utility_denier_count": user_information.defender_utility_denier_count,
                "defender_utility_denier_percentage": user_information.defender_utility_denier_percentage,
                "kd_ratio": user_information.kd_ratio,
                "kill_per_match": user_information.kill_per_match,
                "kill_per_minute": user_information.kill_per_minute,
                "win_percentage": user_information.win_percentage,
                "rank_match_played": user_information.rank_match_played,
                "rank_match_won": user_information.rank_match_won,
                "rank_match_lost": user_information.rank_match_lost,
                "rank_match_abandoned": user_information.rank_match_abandoned,
                "rank_kills_count": user_information.rank_kills_count,
                "rank_deaths_count": user_information.rank_deaths_count,
                "rank_kd_ratio": user_information.rank_kd_ratio,
                "rank_kill_per_match": user_information.rank_kill_per_match,
                "rank_win_percentage": user_information.rank_win_percentage,
                "arcade_match_played": user_information.arcade_match_played,
                "arcade_match_won": user_information.arcade_match_won,
                "arcade_match_lost": user_information.arcade_match_lost,
                "arcade_match_abandoned": user_information.arcade_match_abandoned,
                "arcade_kills_count": user_information.arcade_kills_count,
                "arcade_deaths_count": user_information.arcade_deaths_count,
                "arcade_kd_ratio": user_information.arcade_kd_ratio,
                "arcade_kill_per_match": user_information.arcade_kill_per_match,
                "arcade_win_percentage": user_information.arcade_win_percentage,
                "quickmatch_match_played": user_information.quickmatch_match_played,
                "quickmatch_match_won": user_information.quickmatch_match_won,
                "quickmatch_match_lost": user_information.quickmatch_match_lost,
                "quickmatch_match_abandoned": user_information.quickmatch_match_abandoned,
                "quickmatch_kills_count": user_information.quickmatch_kills_count,
                "quickmatch_deaths_count": user_information.quickmatch_deaths_count,
                "quickmatch_kd_ratio": user_information.quickmatch_kd_ratio,
                "quickmatch_kill_per_match": user_information.quickmatch_kill_per_match,
                "quickmatch_win_percentage": user_information.quickmatch_win_percentage,
            },
            )
            print_log(f"insert_if_nonexistant_full_user_info: Inserted stats for user {user_info.display_name}")
            # Transaction will be committed automatically by context manager
    except Exception as e:
        try:
            stringify_user_info = (
                json.dumps(asdict(user_information), indent=4)
                if user_information is not None
                else f"No user_information for user id: {user_info.id}"
            )
        except Exception:
            stringify_user_info = f"user id: {user_info.id}"
        print_error_log(f"insert_if_nonexistant_full_user_info: Error inserting user stats: {e}\n{stringify_user_info}")
        raise e


def data_access_fetch_user_full_user_info(user_id: int) -> Union[UserInformation, None]:
    """
    Fetch the full user stats info for a specific user
    """
    query = f"""
        SELECT {SELECT_USER_FULL_STATS_INFO}
        FROM user_full_stats_info
        WHERE user_id = :user_id
        """
    result = (
        database_manager.get_cursor().execute(
            query,
            {"user_id": user_id},
        )
    ).fetchone()

    if result is None:
        return None

    return UserInformation.from_db_row(result)
