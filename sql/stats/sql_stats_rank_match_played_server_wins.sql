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
      and ua1.timestamp >= '2025-02-14'
      and ua2.timestamp >= '2025-02-14'
    GROUP BY
      ua1.id
  ),
  matches_in_session AS (
    SELECT
      ufm.user_id,
      COUNT(ufm.id) AS matches_during_activity,
      SUM(
        CASE
          WHEN ufm.has_win = 1 THEN 1
          ELSE 0
        END
      ) AS wins_during_activity
    FROM
      user_full_match_info ufm
      JOIN user_sessions us ON ufm.user_id = us.user_id
      AND ufm.match_timestamp BETWEEN us.session_start AND us.session_end
      and ufm.match_timestamp >= '2025-02-14'
    GROUP BY
      ufm.user_id
  ),
  matches_outside_session AS (
      SELECT 
          ufm.user_id,
          COUNT(ufm.id) AS matches_outside_activity,
          SUM(CASE WHEN ufm.has_win = 1 THEN 1 ELSE 0 END) AS wins_outside_activity
      FROM user_full_match_info ufm
      WHERE NOT EXISTS (
          SELECT 1 
          FROM user_sessions us 
          WHERE ufm.user_id = us.user_id
          AND ufm.match_timestamp BETWEEN us.session_start AND us.session_end
      )
      and ufm.match_timestamp >= '2025-02-14'
      GROUP BY ufm.user_id
  ),
  total_matches AS (
    SELECT
      user_id,
      COUNT(id) AS total_matches
    FROM
      user_full_match_info 
    WHERE
      user_full_match_info.match_timestamp >= '2025-02-14'
    GROUP BY
      user_id
  )
SELECT
  user_info.display_name,
  total_matches AS total_rank_matches,
  COALESCE(mis.matches_during_activity, 0) AS matches_count_in_circus,
  -- COALESCE(mis.wins_during_activity, 0) AS wins_during_activity,
  CASE
    WHEN COALESCE(mis.matches_during_activity, 0) = 0 THEN 0
    ELSE ROUND(
      (mis.wins_during_activity * 100.0) / mis.matches_during_activity,
      2
    )
  END AS win_rate_circus,
  --COALESCE(mos.matches_outside_activity, 0) AS matches_outside_activity,
  --COALESCE(mos.wins_outside_activity, 0) AS wins_outside_activity,
  CASE
    WHEN COALESCE(mos.matches_outside_activity, 0) = 0 THEN 0
    ELSE ROUND(
      (mos.wins_outside_activity * 100.0) / mos.matches_outside_activity,
      2
    )
  END AS win_rate_not_circus,
  CASE
    WHEN COALESCE(tm.total_matches, 0) = 0 THEN 0
    ELSE ROUND(
      (COALESCE(mis.matches_during_activity, 0) * 100.0) / tm.total_matches,
      2
    )
  END AS rate_play_in_circus
FROM
  total_matches tm
  LEFT JOIN matches_in_session mis ON tm.user_id = mis.user_id
  LEFT JOIN matches_outside_session mos ON tm.user_id = mos.user_id
  LEFT JOIN user_info ON tm.user_id = user_info.id
ORDER BY
  rate_play_in_circus DESC
LIMIT 60 OFFSET 0;