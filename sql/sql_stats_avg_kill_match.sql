SELECT
  user_full_match_info.user_id,
  user_info.display_name,
  sum(user_full_match_info.kill_count) as sum_kill,
  count(user_full_match_info.id) as count_match,
  sum(user_full_match_info.kill_count) * 1.0 / count(user_full_match_info.id) as avg_kill
FROM
  user_full_match_info
  LEFT JOIN user_info on user_info.id = user_full_match_info.user_id
where
  is_rollback = false
  and datetime (match_timestamp) > datetime ('2025-01-21')
GROUP BY
  user_id
ORDER BY
  avg_kill desc;

select
  user_id,
  display_name,
  avg_kill
from
  (
    SELECT
      user_full_match_info.user_id,
      user_info.display_name,
      sum(user_full_match_info.kill_count) as sum_kill,
      count(user_full_match_info.id) as count_match,
      sum(user_full_match_info.kill_count) * 1.0 / count(user_full_match_info.id) as avg_kill
    FROM
      user_full_match_info
      LEFT JOIN user_info on user_info.id = user_full_match_info.user_id
    where
      is_rollback = false
      and datetime (match_timestamp) > datetime ('2025-01-21')
    GROUP BY
      user_id
  )
ORDER BY
  avg_kill desc