--- DIFF ---
SELECT
  user_info.display_name,
  SUM(clutches_win_count) AS win,
  SUM(clutches_loss_count) AS loss,
  SUM(round_played_count) AS round_played_count_sum,
  SUM(clutches_win_count) * 1.0 / (
    SUM(clutches_win_count) + SUM(clutches_loss_count)
  ) AS ratio
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
  ratio DESC;