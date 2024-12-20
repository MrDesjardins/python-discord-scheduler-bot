-- Get all user activity count
SELECT count(*) FROM user_activity;

-- Check what was the activity that was deleted
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
        -- Check if the event repeats (i.e., no alternation)
        (event = previous_event)
        OR
        -- Check if the sequence breaks the expected alternating pattern
        (previous_event IS NOT NULL AND 
         previous_event = 'connect' AND event != 'disconnect')
        OR
        (previous_event IS NOT NULL AND 
         previous_event = 'disconnect' AND event != 'connect')
)
SELECT ua.display_name, 
    vio.user_id ,
  vio.previous_event, 
  vio.event, 
  vio.seconds_between_events / 3600 AS hours_between_events,
  vio.previous_id,
  vio.id,
  vio.timestamp
FROM 
  violations vio
LEFT JOIN 
  user_info ua
    ON vio.user_id = ua.id;
SELECT count(*) FROM user_activity;

-- Get the ID from the query above as well as the user id to check the activity
SELECT * from  user_activity where id >= 2197 and user_id = 261398260952858624;

