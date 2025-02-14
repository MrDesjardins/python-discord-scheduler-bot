-- Find the percentage of matches played on the server using the user_full_match_info and user_activity tables
WITH
  user_sessions AS (
    SELECT
      ua1.user_id,
      ua1.timestamp AS session_start,
      MIN(ua2.timestamp) AS session_end
    FROM
      user_activity ua1
      LEFT JOIN user_activity ua2 ON ua1.user_id = ua2.user_id
      AND ua1.timestamp < ua2.timestamp
      AND ua2.event = 'disconnect'
    WHERE
      ua1.event = 'connect'
      and ua1.timestamp >= '2025-01-22'
      and ua2.timestamp >= '2025-01-22'
      -- and ua1.user_id = 357551747146842124
      -- and ua2.user_id = 357551747146842124
    GROUP BY
      ua1.id
  ),
  matches_in_session AS (
    SELECT
      ufm.user_id,
      COUNT(ufm.id) AS matches_during_activity
    FROM
      user_full_match_info ufm
      JOIN user_sessions us ON ufm.user_id = us.user_id
      AND ufm.match_timestamp BETWEEN us.session_start AND us.session_end
    GROUP BY
      ufm.user_id
  ),
  total_matches AS (
    SELECT
      user_id,
      COUNT(id) AS total_matches
    FROM
      user_full_match_info
    WHERE
      user_full_match_info.match_timestamp >= '2025-01-22'
      --  and user_full_match_info.user_id = 357551747146842124
    GROUP BY
      user_id
  )
SELECT
  user_info.display_name,
  COALESCE(mis.matches_during_activity, 0) AS rank_matches_played_in_circus_maximus,
  tm.total_matches AS total_rank_matches,
  CASE
    WHEN tm.total_matches = 0 THEN 0
    ELSE ROUND(
      (COALESCE(mis.matches_during_activity, 0) * 100.0) / tm.total_matches,
      2
    )
  END AS percentage_in_circus_maximus
FROM
  total_matches tm
  LEFT JOIN matches_in_session mis ON tm.user_id = mis.user_id
  LEFT JOIN user_info ON tm.user_id = user_info.id
ORDER BY
  percentage_in_circus_maximus DESC;