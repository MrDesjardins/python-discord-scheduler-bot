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
      AND timestamp > '2024-02-16'
  )
SELECT
  user1_info.display_name AS user1_display_name,
  SUM(
    CAST(
      (
        strftime ('%s', MIN(a.disconnect_time, b.disconnect_time)) - strftime ('%s', MAX(a.connect_time, b.connect_time))
      ) AS INTEGER
    )
  )/3600 AS total_overlap_seconds
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
WHERE
  a.connect_time IS NOT NULL -- Ensure proper session pairing
GROUP BY
  a.user_id
ORDER BY
  total_overlap_seconds DESC
LIMIT
  50;