
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
),
violations AS (
    SELECT 
        previous_id,
        id,
        user_id,
        previous_event,
        event,
        previous_timestamp,
        timestamp,
         (strftime('%s', timestamp) - strftime('%s', previous_timestamp)) as seconds_between_events
    FROM 
        user_event_sequence
    WHERE 
        event = 'disconnect'
    AND
        previous_event = 'connect'
    AND
        -- Check if the time between events is greater than 12h
       seconds_between_events > 60*60*11
)
SELECT ua.display_name, 
    vio.user_id ,
  vio.previous_event, 
  vio.event, 
  vio.seconds_between_events / 3600 AS hours_between_events,
  vio.previous_id,
  vio.id
FROM 
  violations vio
LEFT JOIN 
  user_info ua
    ON vio.user_id = ua.id;



select * from user_activity where id in(1390, 1486) order by timestamp desc limit 10; 

-- 180436297368862723

SELECT 
    id,
    user_id,
    event,
    timestamp
FROM 
    user_activity
WHERE user_id = 180436297368862723
ORDER BY timestamp ASC;


-- 1390 and 1486
