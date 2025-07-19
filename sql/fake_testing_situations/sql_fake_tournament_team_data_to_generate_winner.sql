-- Create a fake team tournament data for testing purposes
-- Use case:
-- 1. The reported is the leader of a team
DELETE FROM user_tournament WHERE tournament_id = 23564;

DELETE FROM tournament_game WHERE tournament_id = 23564;

DELETE FROM tournament WHERE id = 23564;

DELETE FROM bet_user_tournament WHERE tournament_id = 23564;

DELETE FROM tournament_team_members WHERE tournament_id = 23564;


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
    23564,
    1281020861591326803,
    'Fake Tournament Team #1',
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
  (23564, 588915156608876557, '2024-12-01 00:00:00'),
  (23564, 357551747146842124, '2024-12-01 00:00:00'),
  (23564, 232631945325051906, '2024-12-01 00:00:00'),
  (23564, 488465866820812810, '2024-12-01 00:00:00'),
  (23564, 333109962861576202, '2024-12-01 00:00:00'),
  (23564, 261398260952858624, '2024-12-01 00:00:00'),

  (23564, 212669889012301824, '2024-12-01 00:00:00'),
  (23564, 557002311071694849, '2024-12-01 00:00:00'),
  (23564, 342114709425881089, '2024-12-01 00:00:00'),
  (23564, 97116159958081536, '2024-12-01 00:00:00'),
  (23564, 151068544484769793, '2024-12-01 00:00:00'),
  (23564, 1012789763679465482, '2024-12-01 00:00:00');


INSERT INTO tournament_team_members (
    user_leader_id,
    tournament_id,
    user_id
) VALUES
  (588915156608876557, 23564, 212669889012301824),
  (357551747146842124, 23564, 557002311071694849),
  (232631945325051906, 23564, 342114709425881089),
  (488465866820812810, 23564, 97116159958081536),
  (333109962861576202, 23564, 151068544484769793),
  (261398260952858624, 23564, 1012789763679465482);


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
    332015,
    23564,
    NULL,
    NULL,
    588915156608876557,
    357551747146842124,
    'oregon',
    357551747146842124,
    '5-3'
  ),
  (
    332014,
    23564,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    332013,
    23564,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    333109962861576202,
    '5-4'
  ),
  (
    332012,
    23564,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    332007,
    23564,
    332014,
    332015,
    357551747146842124,
    232631945325051906,
    'skyscraper',
    357551747146842124,
    '7-0'
  ),
  (
    332006,
    23564,
    332013,
    332012,
    333109962861576202,
    NULL,
    NULL,
    333109962861576202,
    NULL
  ),
  (
    332005,
    23564,
    332007,
    332006,
    357551747146842124,
    333109962861576202,
    'Coastline',
    NULL, 
    NULL
  );

-- Add bets
INSERT INTO
  bet_user_tournament (tournament_id, user_id, amount)
VALUES
  (23564, 588915156608876557, 1000),
  (23564, 357551747146842124, 1230),
  (23564, 232631945325051906, 200),
  (23564, 1012789763679465482, 0);