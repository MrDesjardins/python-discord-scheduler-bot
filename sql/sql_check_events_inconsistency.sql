-- Get all user activity count
SELECT count(*) FROM user_activity;

-- Check what was the activity that was deleted
WITH user_event_sequence AS (
    SELECT 
        id,
        user_id,
        event,
        timestamp,
        LAG(event) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_event
    FROM 
        user_activity
),
violations AS (
    SELECT 
        id,
        user_id,
        event,
        previous_event,
        timestamp
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
SELECT * from violations;

-- Get the ID from the query above as well as the user id to check the activityF
SELECT * from  user_activity where id >= 1641 and user_id = 357551747146842124;

-- Real Query: Delete the event that does not have a open or close properly
WITH user_event_sequence AS (
    SELECT 
        id,
        user_id,
        event,
        timestamp,
        LAG(event) OVER (PARTITION BY user_id ORDER BY timestamp) AS previous_event
    FROM 
        user_activity
),
violations AS (
    SELECT 
        id,
        user_id,
        event,
        previous_event,
        timestamp
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
delete from user_activity where id in (select id from violations); 

SELECT count(*) FROM user_activity;