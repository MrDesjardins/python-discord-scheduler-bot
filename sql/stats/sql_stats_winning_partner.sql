--------------------- ALL USER ---------------------
WITH
  MatchPairs AS (
    SELECT
      m1.match_uuid,
      m2.match_uuid,
      m1.user_id AS user1,
      m2.user_id AS user2,
      m1.has_win AS has_win
    FROM
      user_full_match_info m1
      JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
      AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
    WHERE
      m1.match_timestamp >= '2025-01-15'
  )
SELECT
  UI_1.display_name AS user1_name,
  UI_2.display_name AS user2_name,
  COUNT(*) AS games_played,
  SUM(has_win) AS has_win_sum,
  SUM(has_win) * 1.0 / COUNT(*) AS win_rate_percentage
FROM
  MatchPairs
  LEFT JOIN user_info AS UI_1 ON UI_1.id = user1
  LEFT JOIN user_info AS UI_2 ON UI_2.id = user2
WHERE
  user1 IS NOT NULL
  AND user2 IS NOT NULL
GROUP BY
  user1,
  user2
HAVING
  games_played >= 10
ORDER BY
  win_rate_percentage DESC;

--------------------- BY USER DUO ---------------------
WITH
  MatchPairs AS (
    SELECT
      m1.match_uuid,
      m2.match_uuid,
      m1.user_id AS user1,
      m2.user_id AS user2,
      m1.has_win AS has_win
    FROM
      user_full_match_info m1
      JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
      AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
    WHERE
      m1.match_timestamp >= '2025-02-05'
      AND m1.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-05'
      )
      AND m2.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-05'
      )
  )
SELECT
  UI_1.display_name AS user1_name,
  UI_2.display_name AS user2_name,
  COUNT(*) AS games_played,
  SUM(has_win) AS has_win_sum,
  SUM(has_win) * 1.0 / COUNT(*) AS win_rate_percentage
FROM
  MatchPairs
  LEFT JOIN user_info AS UI_1 ON UI_1.id = user1
  LEFT JOIN user_info AS UI_2 ON UI_2.id = user2
WHERE
  user1 IS NOT NULL
  AND user2 IS NOT NULL
GROUP BY
  user1,
  user2
HAVING
  games_played > 5
ORDER BY
  win_rate_percentage DESC;

--- DUO DEBUG---
SELECT
  m1.match_uuid,
  m2.match_uuid,
  m1.user_id AS user1,
  m2.user_id AS user2,
  m1.has_win AS has_win
FROM
  user_full_match_info m1
  JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
  AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
WHERE
  m1.match_timestamp >= '2025-02-01'
  AND (
    (
      user1 = 357551747146842124
      and user2 = 732441366621192374
    )
    or (
      user1 = 732441366621192374
      and user2 = 357551747146842124
    )
  );

SELECT
  match_uuid
FROM
  user_full_match_info
WHERE
  user_id = 732441366621192374
  AND match_timestamp >= '2025-02-01'
intersect
SELECT
  match_uuid
FROM
  user_full_match_info
WHERE
  user_id = 357551747146842124
  AND match_timestamp >= '2025-02-01'
select
  id
FROM
  user_full_match_info
where
  match_uuid = '3c7fa033-93c2-43da-8857-45547ba79cb3';

select
  id
FROM
  user_full_match_info
where
  match_uuid = '0c097d5e-c790-4ec8-bd35-ba45675e1d16';

---- TRIO --- 
WITH
  MatchPairs AS (
    SELECT
      m1.match_uuid,
      m2.match_uuid,
      m3.match_uuid,
      m1.user_id AS user1,
      m2.user_id AS user2,
      m3.user_id AS user3,
      m1.has_win AS has_win
    FROM
      user_full_match_info m1
      JOIN user_full_match_info m2 ON m1.match_uuid = m2.match_uuid
      JOIN user_full_match_info m3 ON m2.match_uuid = m3.match_uuid
      AND m1.user_id < m2.user_id -- Avoid duplicate pairs and self-joins
      AND m2.user_id < m3.user_id -- Avoid duplicate pairs and self-joins
    WHERE
      m1.match_timestamp >= '2025-02-05'
      AND m1.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-05'
      )
      AND m2.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-05'
      )
      AND m3.user_id IN (
        SELECT DISTINCT
          user_id
        from
          user_activity
        where
          timestamp >= '2025-02-05'
      )
  )
SELECT
  UI_1.display_name AS user1_name,
  UI_2.display_name AS user2_name,
  UI_3.display_name AS user3_name,
  COUNT(*) AS games_played,
  SUM(has_win) AS has_win_sum,
  SUM(has_win) * 1.0 / COUNT(*) AS win_rate_percentage
FROM
  MatchPairs
  LEFT JOIN user_info AS UI_1 ON UI_1.id = user1
  LEFT JOIN user_info AS UI_2 ON UI_2.id = user2
  LEFT JOIN user_info AS UI_3 ON UI_3.id = user3
WHERE
  user1 IS NOT NULL
  AND user2 IS NOT NULL
  AND user3 IS NOT NULL
GROUP BY
  user1,
  user2,
  user3
HAVING
  games_played >= 10
ORDER BY
  win_rate_percentage DESC;