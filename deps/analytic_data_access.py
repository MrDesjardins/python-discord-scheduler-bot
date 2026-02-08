"""
Analytics Data Access - Facade Module

This module provides backward compatibility by re-exporting all analytics
data access functions from specialized modules.

DEPRECATED IMPORT PATTERN (still supported):
    from deps.analytic_data_access import fetch_user_info

RECOMMENDED IMPORT PATTERN (new code):
    from deps.analytic_settings_data_access import fetch_user_info

Module Organization:
- analytic_constants: Cache keys and SQL field selectors
- analytic_activity_data_access: User activity tracking (join/leave events, time calculations)
- analytic_settings_data_access: User profile settings (timezone, usernames, MMR, R6 Tracker IDs)
- analytic_match_data_access: Match statistics persistence (insert/fetch match data and user stats)
- analytic_leaderboard_data_access: Community leaderboards (TK counts, K/D ratios, duos/trios, etc.)
- analytic_ranking_data_access: Top-N rankings (matches played, win rates, team kills, etc.)
- analytic_profile_data_access: Individual user profiles (MMR, activity timestamps, partnerships)
"""

# Re-export logging utilities (needed for test mocking)
from deps.log import print_error_log, print_log

# Re-export constants
from deps.analytic_constants import (
    KEY_USER_FULL_MATCH_INFO,
    KEY_USER_FULL_STATS_INFO,
    KEY_USER_INFO,
    KEY_USER_ACTIVITY,
    USER_ACTIVITY_SELECT_FIELD,
    USER_INFO_SELECT_FIELD,
    SELECT_USER_FULL_MATCH_INFO,
    SELECT_USER_FULL_STATS_INFO,
)

# Re-export activity functions
from deps.analytic_activity_data_access import (
    delete_all_user_weights,
    insert_user_activity,
    fetch_user_info,
    fetch_user_info_by_user_id,
    fetch_user_info_by_user_id_list,
    fetch_all_user_activities,
    fetch_all_user_activities2,
    fetch_user_activities,
    fetch_user_infos_with_activity,
    calculate_time_spent_from_db,
)

# Re-export settings functions
from deps.analytic_settings_data_access import (
    data_access_set_usertimezone,
    data_access_set_ubisoft_username_max,
    data_access_set_ubisoft_username_active,
    data_access_set_max_mmr,
    data_access_set_r6_tracker_id,
    upsert_user_info,
    get_active_user_info,
)

# Re-export match data functions
from deps.analytic_match_data_access import (
    insert_if_nonexistant_full_match_info,
    data_access_fetch_user_full_match_info,
    data_access_fetch_users_full_match_info,
    data_access_fetch_user_matches_in_time_range,
    insert_if_nonexistant_full_user_info,
    data_access_fetch_user_full_user_info,
    data_access_fetch_recent_win_loss,
)

# Re-export leaderboard functions
from deps.analytic_leaderboard_data_access import (
    data_access_fetch_tk_count_by_user,
    data_access_fetch_rollback_positive_count_by_user,
    data_access_fetch_rollback_negative_count_by_user,
    data_access_fetch_avg_kill_match,
    data_access_fetch_match_played_count_by_user,
    data_access_fetch_most_voice_time_by_user,
    data_access_fetch_users_operators,
    data_access_fetch_kd_by_user,
    data_access_fetch_best_duo,
    data_access_fetch_best_trio,
    data_access_fetch_first_death,
    data_access_fetch_first_kill,
    data_access_fetch_success_fragging,
    data_access_fetch_clutch_win_rate,
    data_access_fetch_ace_4k_3k,
    data_access_fetch_clutch_round_rate,
    data_access_fetch_win_rate_server,
    data_access_fetch_best_worse_map,
    data_access_fetch_unique_user_per_day,
)

# Re-export ranking functions
from deps.analytic_ranking_data_access import (
    data_access_fetch_top_matches_played,
    data_access_fetch_top_ranked_matches_played,
    data_access_fetch_top_win_rateranked_matches_played,
    data_access_fetch_top_team_kill,
    data_access_fetch_top_kill_per_match_rank,
    data_access_fetch_top_breacher,
    data_access_fetch_count_total_wallbangs,
    data_access_fetch_attacker_fragger_count,
    data_access_fetch_time_played_siege,
    data_access_fetch_time_played_siege_on_server,
    data_access_fetch_time_duo_partners,
)

# Re-export profile functions
from deps.analytic_profile_data_access import (
    data_access_fetch_user_max_current_mmr,
    data_access_fetch_user_max_mmr,
    data_access_fetch_first_activity,
    data_access_fetch_last_activity,
    data_access_fetch_total_hours,
    data_access_fetch_top_game_played_for_user,
    data_access_fetch_top_winning_partners_for_user,
)

__all__ = [
    # Logging utilities
    "print_error_log",
    "print_log",
    # Constants
    "KEY_USER_FULL_MATCH_INFO",
    "KEY_USER_FULL_STATS_INFO",
    "KEY_USER_INFO",
    "KEY_USER_ACTIVITY",
    "USER_ACTIVITY_SELECT_FIELD",
    "USER_INFO_SELECT_FIELD",
    "SELECT_USER_FULL_MATCH_INFO",
    "SELECT_USER_FULL_STATS_INFO",
    # Activity functions
    "delete_all_user_weights",
    "insert_user_activity",
    "fetch_user_info",
    "fetch_user_info_by_user_id",
    "fetch_user_info_by_user_id_list",
    "fetch_all_user_activities",
    "fetch_all_user_activities2",
    "fetch_user_activities",
    "fetch_user_infos_with_activity",
    "calculate_time_spent_from_db",
    # Settings functions
    "data_access_set_usertimezone",
    "data_access_set_ubisoft_username_max",
    "data_access_set_ubisoft_username_active",
    "data_access_set_max_mmr",
    "data_access_set_r6_tracker_id",
    "upsert_user_info",
    "get_active_user_info",
    # Match data functions
    "insert_if_nonexistant_full_match_info",
    "data_access_fetch_user_full_match_info",
    "data_access_fetch_users_full_match_info",
    "data_access_fetch_user_matches_in_time_range",
    "insert_if_nonexistant_full_user_info",
    "data_access_fetch_user_full_user_info",
    # Leaderboard functions
    "data_access_fetch_tk_count_by_user",
    "data_access_fetch_rollback_positive_count_by_user",
    "data_access_fetch_rollback_negative_count_by_user",
    "data_access_fetch_avg_kill_match",
    "data_access_fetch_match_played_count_by_user",
    "data_access_fetch_most_voice_time_by_user",
    "data_access_fetch_users_operators",
    "data_access_fetch_kd_by_user",
    "data_access_fetch_best_duo",
    "data_access_fetch_best_trio",
    "data_access_fetch_first_death",
    "data_access_fetch_first_kill",
    "data_access_fetch_success_fragging",
    "data_access_fetch_clutch_win_rate",
    "data_access_fetch_ace_4k_3k",
    "data_access_fetch_clutch_round_rate",
    "data_access_fetch_win_rate_server",
    "data_access_fetch_best_worse_map",
    "data_access_fetch_unique_user_per_day",
    # Ranking functions
    "data_access_fetch_top_matches_played",
    "data_access_fetch_top_ranked_matches_played",
    "data_access_fetch_top_win_rateranked_matches_played",
    "data_access_fetch_top_team_kill",
    "data_access_fetch_top_kill_per_match_rank",
    "data_access_fetch_top_breacher",
    "data_access_fetch_count_total_wallbangs",
    "data_access_fetch_attacker_fragger_count",
    "data_access_fetch_time_played_siege",
    "data_access_fetch_time_played_siege_on_server",
    "data_access_fetch_time_duo_partners",
    # Profile functions
    "data_access_fetch_user_max_current_mmr",
    "data_access_fetch_user_max_mmr",
    "data_access_fetch_first_activity",
    "data_access_fetch_last_activity",
    "data_access_fetch_total_hours",
    "data_access_fetch_top_game_played_for_user",
    "data_access_fetch_top_winning_partners_for_user",
]
