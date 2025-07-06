-- Get the top x users who played the most matches

SELECT
  user_info.display_name,
  user_full_stats_info.total_matches_played
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.rank_match_played DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.rank_match_played
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.rank_match_played DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.rank_win_percentage
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.rank_win_percentage DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.total_team_kills
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.total_team_kills DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.rank_kill_per_match
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.rank_kill_per_match DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.attacked_breacher_count
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.attacked_breacher_count DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.total_wall_bang
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.total_wall_bang DESC
LIMIT 30;

SELECT
  user_info.display_name,
  user_full_stats_info.attacked_fragger_count
FROM
  user_full_stats_info
LEFT JOIN user_info ON 
    user_info.id = user_full_stats_info.user_id
WHERE user_full_stats_info.user_id IN (
        SELECT DISTINCT
        user_id
        from
        user_activity
        where
        timestamp >= '2025-06-06'
    )
ORDER BY
  user_full_stats_info.attacked_fragger_count DESC
LIMIT 30;
