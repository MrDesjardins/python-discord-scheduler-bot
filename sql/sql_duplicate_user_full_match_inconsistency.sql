SELECT id, match_uuid, user_id, MIN(match_timestamp) AS earliest_timestamp
FROM user_full_match_info
GROUP BY match_uuid, user_id
HAVING COUNT(*) > 1;

-- Delete the duplicate rows (keep earliest timestamp)
select count(*) from user_full_match_info;
DELETE FROM user_full_match_info
WHERE id NOT IN (
    SELECT id FROM (
        SELECT id
        FROM user_full_match_info AS u
        WHERE match_timestamp = (
            SELECT MIN(match_timestamp)
            FROM user_full_match_info
            WHERE match_uuid = u.match_uuid AND user_id = u.user_id
        )
    ) AS subquery
);
select count(*) from user_full_match_info;