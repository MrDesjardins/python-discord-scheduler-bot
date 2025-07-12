
-- Get for a specific user all the events that have time greater than a large amount of time.
WITH user_event_sequence AS (
    SELECT 
        id,
        user_id,
        event,
        timestamp,
        LAG(id) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_id,
        LAG(event) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_event,
        LAG(timestamp) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_timestamp
    FROM 
        user_activity
    WHERE user_id = 667970532490084384
),
valid_pairs AS (
    SELECT 
        previous_id,
        id,
        user_id,
        previous_event,
        event,
        previous_timestamp,
        timestamp,
        (strftime('%s', timestamp) - strftime('%s', previous_timestamp)) AS seconds_between_events
    FROM 
        user_event_sequence
    WHERE 
        event = 'disconnect'
        AND previous_event = 'connect'
        AND previous_timestamp IS NOT NULL -- Ensures valid pairs
),
aggregated_time AS (
    SELECT 
        user_id,
        SUM(seconds_between_events) AS total_time
    FROM 
        valid_pairs
    GROUP BY 
        user_id
)
SELECT 
    ua.display_name, 
    at.total_time / 3600 AS total_hours
FROM 
    aggregated_time at
LEFT JOIN 
    user_info ua
    ON at.user_id = ua.id
WHERE 
    at.total_time > 0
ORDER BY 
    at.total_time DESC;

-- The first user_activity
select * from user_activity order by timestamp asc limit 0,1; 

-- Major (667970532490084384)
SELECT * FROM user_activity WHERE user_id = 667970532490084384 ORDER BY timestamp ASC;