WITH RECURSIVE
  split_operators AS (
    -- Base case: Split the first operator from the string
    SELECT
      user_full_match_info.user_id,
      user_info.display_name,
      TRIM(
        SUBSTR (
          user_full_match_info.operators,
          0,
          INSTR (user_full_match_info.operators || ',', ',')
        )
      ) AS operator,
      SUBSTR (
        user_full_match_info.operators,
        INSTR (user_full_match_info.operators || ',', ',') + 1
      ) AS remaining_operators
    FROM
      user_full_match_info
      LEFT JOIN user_info ON user_info.id = user_full_match_info.user_id
    WHERE
      datetime (match_timestamp) > datetime ('2025-01-20')
    UNION ALL
    -- Recursive case: Split the next operator from the remaining string
    SELECT
      user_id,
      display_name,
      TRIM(
        SUBSTR (
          remaining_operators,
          0,
          INSTR (remaining_operators || ',', ',')
        )
      ) AS operator,
      SUBSTR (
        remaining_operators,
        INSTR (remaining_operators || ',', ',') + 1
      ) AS remaining_operators
    FROM
      split_operators
    WHERE
      remaining_operators <> ''
  ),
  operator_counts AS (
    -- Aggregate the results to count occurrences of each operator
    SELECT
      display_name,
      operator,
      COUNT(*) AS operator_count
    FROM
      split_operators
    WHERE
      operator <> ''
    GROUP BY
      display_name,
      operator
  ),
  ranked_operators AS (
    -- Add a row number to rank operators for each person by count
    SELECT
      display_name,
      operator,
      operator_count,
      ROW_NUMBER() OVER (
        PARTITION BY
          display_name
        ORDER BY
          operator_count DESC,
          operator ASC
      ) AS rank
    FROM
      operator_counts
  )
  -- Select only the top 8 operators for each person
SELECT
  display_name,
  operator,
  operator_count
FROM
  ranked_operators
WHERE
  rank <= 8
ORDER BY
  display_name ASC,
  rank ASC;