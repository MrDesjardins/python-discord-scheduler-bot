SELECT
  user_info.display_name,
  SUM(first_death_count) AS first_death_count_sum,
  SUM(round_played_count) AS round_played_count_sum,
  SUM(first_death_count) * 1.0 / SUM(round_played_count) AS first_death_rate
FROM
  user_full_match_info
  LEFT JOIN user_info ON user_info.id = user_id
WHERE
  match_timestamp >= '2025-02-01'
GROUP BY
  user_id
ORDER BY
  first_death_rate DESC;

----- First Kills -----
SELECT
  user_info.display_name,
  SUM(first_kill_count) AS first_kill_count_sum,
  SUM(round_played_count) AS round_played_count_sum,
  SUM(first_kill_count) * 1.0 / SUM(round_played_count) AS first_kill_rate
FROM
  user_full_match_info
  LEFT JOIN user_info ON user_info.id = user_id
WHERE
  match_timestamp >= '2025-02-01'
GROUP BY
  user_id
ORDER BY
  first_kill_rate DESC;

--- DIFF ---
SELECT
  user_info.display_name,
  SUM(first_death_count) AS first_death_count_sum,
  SUM(first_kill_count) AS first_kill_count_sum,
  SUM(round_played_count) AS round_played_count_sum,
  SUM(first_death_count) * 1.0 / SUM(round_played_count) AS first_death_rate,
  SUM(first_kill_count) * 1.0 / SUM(round_played_count) AS first_kill_rate,
  (
    SUM(first_kill_count) * 1.0 / SUM(round_played_count)
  ) - (
    SUM(first_death_count) * 1.0 / SUM(round_played_count)
  ) AS delta,
  SUM(first_kill_count) * 1.0 / (SUM(first_kill_count) + SUM(first_death_count)) AS first_kill_ratio
FROM
  user_full_match_info
  LEFT JOIN user_info ON user_info.id = user_id
WHERE
  match_timestamp >= '2025-01-08'
GROUP BY
  user_id
ORDER BY
  first_kill_ratio DESC;