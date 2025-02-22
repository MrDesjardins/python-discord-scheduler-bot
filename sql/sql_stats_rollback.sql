select
  id,
  match_uuid,
  user_id,
  r6_tracker_user_uuid,
  ubisoft_username,
  match_timestamp,
  rank_points
from
  user_full_match_info
where
  is_rollback = true;

select
  user_full_match_info.user_id,
  user_info.display_name,
  count(user_full_match_info.id) as count_rollbacks
from
  user_full_match_info
  left join user_info on user_info.id = user_full_match_info.user_id
where
  is_rollback = true
  and match_timestamp >= '2025-02-10'
  AND user_full_match_info.user_id IN (
    SELECT DISTINCT
      user_id
    from
      user_activity
    where
      timestamp >= '2025-02-10'
  )
group by
  user_id
order by
  count_rollbacks desc;