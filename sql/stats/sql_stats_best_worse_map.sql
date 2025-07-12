SELECT
  user_info.display_name,
  user_full_match_info.map_name,
  count(user_full_match_info.map_name) as map_count
FROM
  user_full_match_info
  INNER JOIN user_info ON user_info.id = user_id
  AND user_info.display_name = 'GuyHero.'
WHERE
  match_timestamp >= '2025-01-14'
  and user_full_match_info.has_win = true
GROUP BY
  user_id;

SELECT
  user_info.display_name,
  user_full_match_info.map_name,
  COUNT(*) AS total_matches,
  SUM(
    CASE
      WHEN user_full_match_info.has_win = TRUE THEN 1
      ELSE 0
    END
  ) AS wins,
  SUM(
    CASE
      WHEN user_full_match_info.has_win = FALSE THEN 1
      ELSE 0
    END
  ) AS losses
FROM
  user_full_match_info
  INNER JOIN user_info ON user_info.id = user_id
WHERE
  match_timestamp >= '2025-01-14'
GROUP BY
  user_id,
  user_full_match_info.map_name;

--------------------------------------------------------------------
WITH
  match_stats AS (
    SELECT
      user_info.display_name,
      user_full_match_info.map_name,
      SUM(
        CASE
          WHEN user_full_match_info.has_win = TRUE THEN 1
          ELSE 0
        END
      ) AS wins,
      SUM(
        CASE
          WHEN user_full_match_info.has_win = FALSE THEN 1
          ELSE 0
        END
      ) AS losses
    FROM
      user_full_match_info
      INNER JOIN user_info ON user_info.id = user_id
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
      user_info.display_name,
      user_full_match_info.map_name
  ),
  max_wins AS (
    SELECT
      display_name,
      MAX(wins) AS max_wins
    FROM
      match_stats
    GROUP BY
      display_name
  ),
  max_losses AS (
    SELECT
      display_name,
      MAX(losses) AS max_losses
    FROM
      match_stats
    GROUP BY
      display_name
  ),
  most_won_maps AS (
    SELECT
      ms.display_name,
      GROUP_CONCAT (ms.map_name, ', ') AS most_won_maps,
      mw.max_wins AS wins
    FROM
      match_stats ms
      JOIN max_wins mw ON ms.display_name = mw.display_name
      AND ms.wins = mw.max_wins
    GROUP BY
      ms.display_name
  ),
  most_lost_maps AS (
    SELECT
      ms.display_name,
      GROUP_CONCAT (ms.map_name, ', ') AS most_lost_maps,
      ml.max_losses AS losses
    FROM
      match_stats ms
      JOIN max_losses ml ON ms.display_name = ml.display_name
      AND ms.losses = ml.max_losses
    GROUP BY
      ms.display_name
  )
SELECT
  mw.display_name,
  mw.most_won_maps,
  mw.wins,
  ml.most_lost_maps,
  ml.losses
FROM
  most_won_maps mw
  LEFT JOIN most_lost_maps ml ON mw.display_name = ml.display_name
WHERE
  mw.wins > 1
  AND ml.losses > 1;