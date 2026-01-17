"""
Analytics Data Access Constants Module

This module contains cache keys and SQL field selectors used across all
analytics data access modules.

Constants:
- KEY_USER_FULL_MATCH_INFO: Cache key for match information
- KEY_USER_FULL_STATS_INFO: Cache key for user statistics
- KEY_USER_INFO: Cache key for user profile information
- KEY_USER_ACTIVITY: Cache key for user activity tracking

- USER_ACTIVITY_SELECT_FIELD: SQL field selector for user_activity table
- USER_INFO_SELECT_FIELD: SQL field selector for user_info table
- SELECT_USER_FULL_MATCH_INFO: SQL field selector for user_full_match_info table
- SELECT_USER_FULL_STATS_INFO: SQL field selector for user_full_stats_info table
"""

KEY_USER_FULL_MATCH_INFO = "user_full_match_info"
KEY_USER_FULL_STATS_INFO = "user_full_stats_info"
KEY_USER_INFO = "user_info"
KEY_USER_ACTIVITY = "user_activity"

USER_ACTIVITY_SELECT_FIELD = """
    user_activity.user_id,
    user_activity.channel_id,
    user_activity.event,
    user_activity.timestamp,
    user_activity.guild_id
"""

USER_INFO_SELECT_FIELD = """
    user_info.id,
    user_info.display_name,
    user_info.ubisoft_username_max,
    user_info.ubisoft_username_active,
    user_info.r6_tracker_active_id,
    user_info.time_zone,
    user_info.max_mmr
    """

SELECT_USER_FULL_MATCH_INFO = """
    user_full_match_info.id,
    user_full_match_info.match_uuid,
    user_full_match_info.user_id,
    user_full_match_info.match_timestamp,
    user_full_match_info.match_duration_ms,
    user_full_match_info.data_center,
    user_full_match_info.session_type,
    user_full_match_info.map_name,
    user_full_match_info.is_surrender,
    user_full_match_info.is_forfeit,
    user_full_match_info.is_rollback,
    user_full_match_info.r6_tracker_user_uuid,
    user_full_match_info.ubisoft_username,
    user_full_match_info.operators,
    user_full_match_info.round_played_count,
    user_full_match_info.round_won_count,
    user_full_match_info.round_lost_count,
    user_full_match_info.round_disconnected_count,
    user_full_match_info.kill_count,
    user_full_match_info.death_count,
    user_full_match_info.assist_count,
    user_full_match_info.head_shot_count,
    user_full_match_info.tk_count,
    user_full_match_info.ace_count,
    user_full_match_info.first_kill_count,
    user_full_match_info.first_death_count,
    user_full_match_info.clutches_win_count,
    user_full_match_info.clutches_loss_count,
    user_full_match_info.clutches_win_count_1v1,
    user_full_match_info.clutches_win_count_1v2,
    user_full_match_info.clutches_win_count_1v3,
    user_full_match_info.clutches_win_count_1v4,
    user_full_match_info.clutches_win_count_1v5,
    user_full_match_info.clutches_lost_count_1v1,
    user_full_match_info.clutches_lost_count_1v2,
    user_full_match_info.clutches_lost_count_1v3,
    user_full_match_info.clutches_lost_count_1v4,
    user_full_match_info.clutches_lost_count_1v5,
    user_full_match_info.kill_1_count,
    user_full_match_info.kill_2_count,
    user_full_match_info.kill_3_count,
    user_full_match_info.kill_4_count,
    user_full_match_info.kill_5_count,
    user_full_match_info.rank_points,
    user_full_match_info.rank_name,
    user_full_match_info.points_gained,
    user_full_match_info.rank_previous,
    user_full_match_info.kd_ratio,
    user_full_match_info.head_shot_percentage,
    user_full_match_info.kills_per_round,
    user_full_match_info.deaths_per_round,
    user_full_match_info.assists_per_round,
    user_full_match_info.has_win
"""


SELECT_USER_FULL_STATS_INFO = """
    user_full_stats_info.user_id,
    user_full_stats_info.r6_tracker_user_uuid,
    user_full_stats_info.total_matches_played,
    user_full_stats_info.total_matches_won,
    user_full_stats_info.total_matches_lost,
    user_full_stats_info.total_matches_abandoned,
    user_full_stats_info.time_played_seconds,
    user_full_stats_info.total_kills,
    user_full_stats_info.total_deaths,
    user_full_stats_info.total_attacker_round_wins,
    user_full_stats_info.total_defender_round_wins,
    user_full_stats_info.total_headshots,
    user_full_stats_info.total_headshots_missed,
    user_full_stats_info.headshot_percentage,
    user_full_stats_info.total_wall_bang,
    user_full_stats_info.total_damage,
    user_full_stats_info.total_assists,
    user_full_stats_info.total_team_kills,
    user_full_stats_info.attacked_breacher_count,
    user_full_stats_info.attacked_breacher_percentage,
    user_full_stats_info.attacked_fragger_count,
    user_full_stats_info.attacked_fragger_percentage,
    user_full_stats_info.attacked_intel_count,
    user_full_stats_info.attacked_intel_percentage,
    user_full_stats_info.attacked_roam_count,
    user_full_stats_info.attacked_roam_percentage,
    user_full_stats_info.attacked_support_count,
    user_full_stats_info.attacked_support_percentage,
    user_full_stats_info.attacked_utility_count,
    user_full_stats_info.attacked_utility_percentage,
    user_full_stats_info.defender_debuffer_count,
    user_full_stats_info.defender_debuffer_percentage,
    user_full_stats_info.defender_entry_denier_count,
    user_full_stats_info.defender_entry_denier_percentage,
    user_full_stats_info.defender_intel_count,
    user_full_stats_info.defender_intel_percentage,
    user_full_stats_info.defender_support_count,
    user_full_stats_info.defender_support_percentage,
    user_full_stats_info.defender_trapper_count,
    user_full_stats_info.defender_trapper_percentage,
    user_full_stats_info.defender_utility_denier_count,
    user_full_stats_info.defender_utility_denier_percentage,
    user_full_stats_info.kd_ratio,
    user_full_stats_info.kill_per_match,
    user_full_stats_info.kill_per_minute,
    user_full_stats_info.win_percentage,
    user_full_stats_info.rank_match_played,
    user_full_stats_info.rank_match_won,
    user_full_stats_info.rank_match_lost,
    user_full_stats_info.rank_match_abandoned,
    user_full_stats_info.rank_kills_count,
    user_full_stats_info.rank_deaths_count,
    user_full_stats_info.rank_kd_ratio,
    user_full_stats_info.rank_kill_per_match,
    user_full_stats_info.rank_win_percentage,
    user_full_stats_info.arcade_match_played,
    user_full_stats_info.arcade_match_won,
    user_full_stats_info.arcade_match_lost,
    user_full_stats_info.arcade_match_abandoned,
    user_full_stats_info.arcade_kills_count,
    user_full_stats_info.arcade_deaths_count,
    user_full_stats_info.arcade_kd_ratio,
    user_full_stats_info.arcade_kill_per_match,
    user_full_stats_info.arcade_win_percentage,
    user_full_stats_info.quickmatch_match_played,
    user_full_stats_info.quickmatch_match_won,
    user_full_stats_info.quickmatch_match_lost,
    user_full_stats_info.quickmatch_match_abandoned,
    user_full_stats_info.quickmatch_kills_count,
    user_full_stats_info.quickmatch_deaths_count,
    user_full_stats_info.quickmatch_kd_ratio,
    user_full_stats_info.quickmatch_kill_per_match,
    user_full_stats_info.quickmatch_win_percentage
"""
