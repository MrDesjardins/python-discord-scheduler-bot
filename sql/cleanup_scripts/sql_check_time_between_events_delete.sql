-- Get for a specific user all the events that have time greater than a large amount of time.
-- Real query: Delete the event that has a time greater than 16h between events
SELECT count(*) FROM user_activity;
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
),
all_ids_to_delete AS (
    SELECT id AS delete_id FROM violations
    UNION
    SELECT previous_id AS delete_id FROM violations
)
delete from user_activity where id in (select delete_id from all_ids_to_delete);
SELECT count(*) FROM user_activity;