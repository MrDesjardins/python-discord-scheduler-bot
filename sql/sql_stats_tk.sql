select
  id,
  match_uuid,
  user_id,
  r6_tracker_user_uuid,
  ubisoft_username,
  match_timestamp,
  tk_count
from
  user_full_match_info
where
  tk_count > 0
select
  user_full_match_info.user_id,
  user_info.display_name,
  count(user_full_match_info.id) as count_tk
from
  user_full_match_info
  left join user_info on user_info.id = user_full_match_info.user_id
where
  tk_count > 0
  and datetime (match_timestamp) > datetime ('2025-01-20')
group by
  user_id
order by
  count_tk desc;