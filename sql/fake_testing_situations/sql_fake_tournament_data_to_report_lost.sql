-- Create a fake 1v1 tournament data for testing purposes
-- The scenario is that upon reporting the lost the tournament is NOT over
-- Use cases:
-- Report lost /reportlosttournament
-- Report lost again (eliminated should not allow)
-- Place a bet /bet (should not allow since completed)
DELETE FROM user_tournament WHERE tournament_id = 123123;

DELETE FROM tournament_game WHERE tournament_id = 123123;

DELETE FROM tournament WHERE id = 123123;

-- Create a fake tournament
INSERT INTO
  tournament (
    id,
    guild_id,
    name,
    registration_date,
    start_date,
    end_date,
    best_of,
    max_players,
    maps,
    has_started,
    team_size
  )
VALUES
  (
    123123,
    1281020861591326803,
    '1v1 Fake Tournament #2',
    '2025-01-01 00:00:00',
    '2025-01-10 00:00:00',
    '2026-05-31 00:00:00',
    3,
    8,
    'oregon,villa,clubhouse,kafe,consulate',
    true,
    1
  );

-- Create fake tournament players
INSERT INTO
  user_tournament (tournament_id, user_id, registration_date)
VALUES
  (123123, 588915156608876557, '2024-12-01 00:00:00'),
  (123123, 357551747146842124, '2024-12-01 00:00:00'),
  (123123, 232631945325051906, '2024-12-01 00:00:00'),
  (123123, 488465866820812810, '2024-12-01 00:00:00'),
  (123123, 333109962861576202, '2024-12-01 00:00:00'),
  (123123, 261398260952858624, '2024-12-01 00:00:00'),
  (123123, 212669889012301824, '2024-12-01 00:00:00'),
  (123123, 557002311071694849, '2024-12-01 00:00:00'),
  (123123, 342114709425881089, '2024-12-01 00:00:00'),
  (123123, 97116159958081536, '2024-12-01 00:00:00'),
  (123123, 151068544484769793, '2024-12-01 00:00:00'),
  (
    123123,
    1012789763679465482,
    '2024-12-01 00:00:00'
  );

-- Create fake tournament matches
INSERT INTO
  tournament_game (
    id,
    tournament_id,
    next_game1_id,
    next_game2_id,
    user1_id,
    user2_id,
    map,
    user_winner_id,
    score
  )
VALUES
  (
    1015,
    123123,
    NULL,
    NULL,
    588915156608876557,
    357551747146842124,
    'oregon',
    357551747146842124,
    '5-3'
  ),
  (
    1014,
    123123,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    1013,
    123123,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    333109962861576202,
    '5-4'
  ),
  (
    1012,
    123123,
    NULL,
    NULL,
    212669889012301824,
    557002311071694849,
    'oregon',
    NULL,
    '5-3'
  ),
  (
    1011,
    123123,
    NULL,
    NULL,
    342114709425881089,
    97116159958081536,
    'villa',
    NULL,
    NULL
  ),
  (
    1010,
    123123,
    NULL,
    NULL,
    151068544484769793,
    1012789763679465482,
    'clubhouse',
    NULL,
    NULL
  ),
  (
    1009,
    123123,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1008,
    123123,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1007,
    123123,
    1014,
    1015,
    232631945325051906,
    357551747146842124,
    'skyscraper',
    NULL,
    NULL
  ),
  (
    1006,
    123123,
    1012,
    1013,
    333109962861576202,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1005,
    123123,
    1010,
    1011,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1004,
    123123,
    1008,
    1009,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1002,
    123123,
    1004,
    1005,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1003,
    123123,
    1006,
    1007,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    1001,
    123123,
    1002,
    1003,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  );