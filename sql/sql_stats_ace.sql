SELECT
  user_info.display_name,
  SUM(kill_5_count) AS ace,
  SUM(kill_4_count) AS kill4,
  SUM(kill_3_count) AS kill3,
  SUM(kill_5_count) + SUM(kill_4_count) + SUM(kill_3_count) as total
FROM
  user_full_match_info
  LEFT JOIN user_info ON user_info.id = user_id
WHERE
  match_timestamp >= '2025-02-10'
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
ORDER BY
  total DESC
LIMIT
  0, 20;