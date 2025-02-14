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
      and match_timestamp > datetime ('2025-01-01') GROUP BY user_id
  )
ORDER BY kd DESC;