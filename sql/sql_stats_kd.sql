SELECT
  user_id,
  display_name,
  sum_kill * 1.0 / sum_death as kd
FROM
  (
    SELECT
      user_full_match_info.user_id,
      user_info.display_name,
      sum(user_full_match_info.kill_count) as sum_kill,
      sum(user_full_match_info.death_count) as sum_death
    FROM
      user_full_match_info
      LEFT JOIN user_info on user_info.id = user_full_match_info.user_id
    WHERE
      is_rollback = false
      AND match_timestamp >= '2025-02-10'
      AND user_full_match_info.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-10'
      )
    GROUP BY
      user_id
  )
ORDER BY
  kd DESC;