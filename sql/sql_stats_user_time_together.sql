WITH
  user_sessions AS (
    SELECT
      user_id,
      channel_id,
      guild_id,
      timestamp AS connect_time,
      LEAD (timestamp) OVER (
        PARTITION BY
          user_id,
          channel_id,
          guild_id
        ORDER BY
          timestamp
      ) AS disconnect_time,
      event,
      LEAD (event) OVER (
        PARTITION BY
          user_id,
          channel_id,
          guild_id
        ORDER BY
          timestamp
      ) AS next_event
    FROM
      user_activity
    WHERE
      event in ('connect', 'disconnect')
      AND timestamp > '2025-02-16'
  )
SELECT
  user1_info.display_name AS user1_display_name,
  user2_info.display_name AS user2_display_name,
  SUM(
    CAST(
      (
        strftime ('%s', MIN(a.disconnect_time, b.disconnect_time)) - strftime ('%s', MAX(a.connect_time, b.connect_time))
      ) AS INTEGER
    )
  ) AS total_overlap_seconds
FROM
  user_sessions a
  JOIN user_sessions b ON a.guild_id = b.guild_id
  AND a.user_id < b.user_id -- Avoid duplicate comparisons
  AND a.connect_time < b.disconnect_time
  AND b.connect_time < a.disconnect_time
  AND a.event = 'connect'
  AND a.next_event = 'disconnect'
  AND b.event = 'connect'
  AND b.next_event = 'disconnect'
  LEFT JOIN user_info AS user1_info ON user1_info.id = a.user_id
  LEFT JOIN user_info AS user2_info ON user2_info.id = b.user_id
WHERE
  a.connect_time IS NOT NULL -- Ensure proper session pairing
GROUP BY
  a.user_id,
  b.user_id
ORDER BY
  total_overlap_seconds DESC
LIMIT
  50;

-- Single user (Patrick) time spent in voice channels after a specific date
WITH
  user_sessions AS (
    SELECT
      user_id,
      channel_id,
      guild_id,
      timestamp AS connect_time,
      LEAD (timestamp) OVER (
        PARTITION BY
          user_id,
          channel_id,
          guild_id
        ORDER BY
          timestamp
      ) AS disconnect_time,
      event,
      LEAD (event) OVER (
        PARTITION BY
          user_id,
          channel_id,
          guild_id
        ORDER BY
          timestamp
      ) AS next_event
    FROM
      user_activity
    WHERE
      event in ('connect', 'disconnect')
      AND timestamp > '2025-02-01'
  )
SELECT
  user_id,
  channel_id,
  guild_id,
  connect_time,
  disconnect_time
FROM
  user_sessions
WHERE
  event = 'connect'
  AND next_event = 'disconnect' -- Ensure correct pairing
  AND user_id = 357551747146842124
ORDER BY
  connect_time;

-- Single user stryker
-- strykey 318126349648920577
WITH
  user_sessions AS (
    SELECT
      user_id,
      channel_id,
      guild_id,
      timestamp AS connect_time,
      LEAD (timestamp) OVER (
        PARTITION BY
          user_id,
          channel_id,
          guild_id
        ORDER BY
          timestamp
      ) AS disconnect_time,
      event,
      LEAD (event) OVER (
        PARTITION BY
          user_id,
          channel_id,
          guild_id
        ORDER BY
          timestamp
      ) AS next_event
    FROM
      user_activity
    WHERE
      event in ('connect', 'disconnect')
      AND timestamp > '2025-02-01'
  )
SELECT
  user_id,
  channel_id,
  guild_id,
  connect_time,
  disconnect_time
FROM
  user_sessions
WHERE
  event = 'connect'
  AND next_event = 'disconnect' -- Ensure correct pairing
  AND user_id = 318126349648920577
ORDER BY
  connect_time;

---
SELECT
  user_id,
  channel_id,
  guild_id,
  timestamp,
  event
FROM
  user_activity
WHERE
  timestamp > '2025-02-01'
  AND user_id in (318126349648920577, 357551747146842124)
ORDER BY
  timestamp;

SELECT
  user_id,
  channel_id,
  guild_id,
  timestamp,
  event
FROM
  user_activity
WHERE
  timestamp >= '2025-02-05'
  AND timestamp <= '2025-02-08'
  AND user_id in (318126349648920577, 357551747146842124)
ORDER BY
  timestamp;
SELECT
  ui1.id as user1_id,
  ui2.id as user2_id,
  ui1.display_name as user1_display_name,
  ui2.display_name as user2_display_name,
  weight
FROM
  user_weights
  left join user_info as ui1 on user_weights.user_a = ui1.id
  left join user_info as ui2 on user_weights.user_b = ui2.id
WHERE
  (
    user1_id = 318126349648920577
    and user2_id = 357551747146842124
  )
  or (
    user2_id = 318126349648920577
    and user1_id = 357551747146842124
  );

  SELECT
  user_id,
  channel_id,
  guild_id,
  timestamp,
  event
FROM
  user_activity
WHERE
  timestamp >= '2025-02-08'
  AND timestamp <= '2025-02-20'
  AND user_id in (357551747146842124)

ORDER BY
  timestamp;