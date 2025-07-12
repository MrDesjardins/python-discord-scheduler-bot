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
      AND match_timestamp >= '2025-02-20'
      AND user_full_match_info.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-20'
      )
    GROUP BY
      user_id
  )
ORDER BY
  kd DESC;

select
  user_full_match_info.kill_count,
  user_full_match_info.death_count,
  user_info.display_name
from
  user_full_match_info
  left join user_info on user_info.id = user_full_match_info.user_id
where
  user_full_match_info.user_id = 225233803185094656
  AND user_full_match_info.match_timestamp >= '2025-02-13'
order by
  user_full_match_info.match_timestamp desc;

--- Activity
select * from user_activity where user_id = 225233803185094656 order by timestamp desc;