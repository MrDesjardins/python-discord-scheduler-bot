-- Remove voice sessions whose duration exceeds a threshold (default: 11 hours).
--
-- Why the old LAG-only version missed spikes:
--   LAG(...) OVER (PARTITION BY user_id ORDER BY timestamp) compares each row to the
--   previous row for that user across ALL channels. A disconnect in channel A can have
--   its "previous" row be a connect in channel B, so a long session in A is never flagged.
--
-- This script pairs each disconnect with the correct opening connect for the SAME
-- (user_id, channel_id): the latest connect before that disconnect with no disconnect
-- between that connect and this disconnect.
--
-- TUNE: change the number below (seconds). Examples: 8*3600 = 8h, 6*3600 = 6h.
-- Stricter = more AFK-style time removed (and more chart spikes flattened).

SELECT count(*) AS row_count_before FROM user_activity;

-- Inspect worst sessions (run this CTE + SELECT alone first if you want a preview)
WITH paired AS (
    SELECT
        d.id AS disconnect_id,
        d.user_id,
        d.channel_id,
        d.timestamp AS disconnect_ts,
        (
            SELECT c.id
            FROM user_activity AS c
            WHERE c.user_id = d.user_id
              AND c.channel_id = d.channel_id
              AND c.event = 'connect'
              AND c.timestamp < d.timestamp
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_activity AS x
                  WHERE x.user_id = d.user_id
                    AND x.channel_id = d.channel_id
                    AND x.event = 'disconnect'
                    AND x.timestamp > c.timestamp
                    AND x.timestamp < d.timestamp
              )
            ORDER BY c.timestamp DESC
            LIMIT 1
        ) AS connect_id
    FROM user_activity AS d
    WHERE d.event = 'disconnect'
),
violations AS (
    SELECT
        p.disconnect_id,
        p.connect_id,
        p.user_id,
        p.channel_id,
        (strftime('%s', p.disconnect_ts) - strftime('%s', c.timestamp)) AS seconds_session
    FROM paired AS p
    INNER JOIN user_activity AS c ON c.id = p.connect_id
    WHERE p.connect_id IS NOT NULL
      AND (strftime('%s', p.disconnect_ts) - strftime('%s', c.timestamp)) > (11 * 60 * 60)
)
SELECT *
FROM violations
ORDER BY seconds_session DESC
LIMIT 100;

-- Delete opening connect + closing disconnect for each violating session
WITH paired AS (
    SELECT
        d.id AS disconnect_id,
        d.user_id,
        d.channel_id,
        d.timestamp AS disconnect_ts,
        (
            SELECT c.id
            FROM user_activity AS c
            WHERE c.user_id = d.user_id
              AND c.channel_id = d.channel_id
              AND c.event = 'connect'
              AND c.timestamp < d.timestamp
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_activity AS x
                  WHERE x.user_id = d.user_id
                    AND x.channel_id = d.channel_id
                    AND x.event = 'disconnect'
                    AND x.timestamp > c.timestamp
                    AND x.timestamp < d.timestamp
              )
            ORDER BY c.timestamp DESC
            LIMIT 1
        ) AS connect_id
    FROM user_activity AS d
    WHERE d.event = 'disconnect'
),
violations AS (
    SELECT
        p.disconnect_id,
        p.connect_id,
        (strftime('%s', p.disconnect_ts) - strftime('%s', c.timestamp)) AS seconds_session
    FROM paired AS p
    INNER JOIN user_activity AS c ON c.id = p.connect_id
    WHERE p.connect_id IS NOT NULL
      AND (strftime('%s', p.disconnect_ts) - strftime('%s', c.timestamp)) > (11 * 60 * 60)
),
all_ids_to_delete AS (
    SELECT disconnect_id AS delete_id FROM violations
    UNION
    SELECT connect_id AS delete_id FROM violations
)
DELETE FROM user_activity
WHERE id IN (SELECT delete_id FROM all_ids_to_delete);

SELECT count(*) AS row_count_after FROM user_activity;
