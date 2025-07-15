-- Team lost in a tournament
-- Use case:
-- 1. The reported is NOT a leader but a member of the team
DELETE FROM user_tournament WHERE tournament_id = 62623;

DELETE FROM tournament_game WHERE tournament_id = 62623;

DELETE FROM tournament WHERE id = 62623;

DELETE FROM bet_user_tournament WHERE tournament_id = 62623;

DELETE FROM tournament_team_members WHERE tournament_id = 62623;


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
    62623,
    1281020861591326803,
    'Fake Tournament Team #2',
    '2025-01-01 00:00:00',
    '2025-01-10 00:00:00',
    '2026-01-31 00:00:00',
    3,
    8,
    'oregon,villa,clubhouse,kafe,consulate',
    true,
    2
  );

-- Create fake tournament players
INSERT INTO
  user_tournament (tournament_id, user_id, registration_date)
VALUES
  (62623, 588915156608876557, '2024-12-01 00:00:00'),
  (62623, 557002311071694849, '2024-12-01 00:00:00'),
  (62623, 232631945325051906, '2024-12-01 00:00:00'),
  (62623, 488465866820812810, '2024-12-01 00:00:00'),
  (62623, 333109962861576202, '2024-12-01 00:00:00'),
  (62623, 261398260952858624, '2024-12-01 00:00:00'),

  (62623, 212669889012301824, '2024-12-01 00:00:00'),
  (62623, 357551747146842124, '2024-12-01 00:00:00'),
  (62623, 342114709425881089, '2024-12-01 00:00:00'),
  (62623, 97116159958081536, '2024-12-01 00:00:00'),
  (62623, 151068544484769793, '2024-12-01 00:00:00'),
  (62623, 1012789763679465482, '2024-12-01 00:00:00');


INSERT INTO tournament_team_members (
    user_leader_id,
    tournament_id,
    user_id
) VALUES
  (588915156608876557, 62623, 212669889012301824),
  (557002311071694849, 62623, 357551747146842124),
  (232631945325051906, 62623, 342114709425881089),
  (488465866820812810, 62623, 97116159958081536),
  (333109962861576202, 62623, 151068544484769793),
  (261398260952858624, 62623, 1012789763679465482);


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
    78015,
    62623,
    NULL,
    NULL,
    588915156608876557,
    557002311071694849,
    'oregon',
    557002311071694849,
    '5-3'
  ),
  (
    78014,
    62623,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    78013,
    62623,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    333109962861576202,
    '5-4'
  ),
  (
    78012,
    62623,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    78007,
    62623,
    78014,
    78015,
    557002311071694849,
    232631945325051906,
    'skyscraper',
    557002311071694849,
    '7-0'
  ),
  (
    78006,
    62623,
    78013,
    78012,
    333109962861576202,
    NULL,
    NULL,
    333109962861576202,
    NULL
  ),
  (
    78005,
    62623,
    78007,
    78006,
    557002311071694849,
    333109962861576202,
    'Coastline',
    NULL, 
    NULL
  );

-- Add bets
INSERT INTO
  bet_user_tournament (tournament_id, user_id, amount)
VALUES
  (62623, 588915156608876557, 1000),
  (62623, 357551747146842124, 1230),
  (62623, 232631945325051906, 200),
  (62623, 1012789763679465482, 0);