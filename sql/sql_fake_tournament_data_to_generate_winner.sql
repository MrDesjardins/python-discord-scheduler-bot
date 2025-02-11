-- Create a fake tournament data for testing purposes
-- Delete Everything
DELETE FROM user_tournament
WHERE
  tournament_id = 65564;

DELETE FROM tournament_game
WHERE
  tournament_id = 65564;

DELETE FROM tournament
WHERE
  id = 65564;

DELETE FROM bet_user_tournament
WHERE
  tournament_id = 65564;

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
    has_started
  )
VALUES
  (
    65564,
    1281020861591326803,
    'Fake Tournament #3',
    '2025-01-01 00:00:00',
    '2025-01-10 00:00:00',
    '2026-01-31 00:00:00',
    3,
    8,
    'oregon,villa,clubhouse,kafe,consulate',
    false
  );

-- Create fake tournament players
INSERT INTO
  user_tournament (tournament_id, user_id, registration_date)
VALUES
  (65564, 588915156608876557, '2024-12-01 00:00:00'),
  (65564, 357551747146842124, '2024-12-01 00:00:00'),
  (65564, 232631945325051906, '2024-12-01 00:00:00'),
  (65564, 488465866820812810, '2024-12-01 00:00:00'),
  (65564, 333109962861576202, '2024-12-01 00:00:00'),
  (65564, 261398260952858624, '2024-12-01 00:00:00'),
  (65564, 212669889012301824, '2024-12-01 00:00:00'),
  (65564, 557002311071694849, '2024-12-01 00:00:00'),
  (65564, 342114709425881089, '2024-12-01 00:00:00'),
  (65564, 97116159958081536, '2024-12-01 00:00:00'),
  (65564, 151068544484769793, '2024-12-01 00:00:00'),
  (65564, 1012789763679465482, '2024-12-01 00:00:00');

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
    2015,
    65564,
    NULL,
    NULL,
    588915156608876557,
    357551747146842124,
    'oregon',
    357551747146842124,
    '5-3'
  ),
  (
    2014,
    65564,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    2013,
    65564,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    333109962861576202,
    '5-4'
  ),
  (
    2012,
    65564,
    NULL,
    NULL,
    212669889012301824,
    557002311071694849,
    'oregon',
    557002311071694849,
    '5-3'
  ),
  (
    2011,
    65564,
    NULL,
    NULL,
    342114709425881089,
    97116159958081536,
    'villa',
    342114709425881089,
    '6-5'
  ),
  (
    2010,
    65564,
    NULL,
    NULL,
    151068544484769793,
    1012789763679465482,
    'clubhouse',
    1012789763679465482,
    '7-3'
  ),
  (
    2009,
    65564,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    2008,
    65564,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    2007,
    65564,
    2014,
    2015,
    232631945325051906,
    357551747146842124,
    'skyscraper',
    357551747146842124,
    '7-0'
  ),
  (
    2006,
    65564,
    2012,
    2013,
    333109962861576202,
    557002311071694849,
    'Villa',
    557002311071694849,
    '7-1'
  ),
  (
    2005,
    65564,
    2010,
    2011,
    1012789763679465482,
    342114709425881089,
    'Coastline',
    1012789763679465482,
    '4-3'
  ),
  (
    2004,
    65564,
    2008,
    2009,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    2002,
    65564,
    2004,
    2005,
    1012789763679465482,
    NULL,
    'None',
    1012789763679465482,
    '4-0'
  ),
  (
    2003,
    65564,
    2006,
    2007,
    557002311071694849,
    357551747146842124,
    'House',
    357551747146842124,
    '6-0'
  ),
  (
    2001,
    65564,
    2002,
    2003,
    1012789763679465482,
    357551747146842124,
    NULL,
    NULL,
    NULL
  );

-- Add bets
INSERT INTO
  bet_user_tournament (tournament_id, user_id, amount)
VALUES
  (65564, 588915156608876557, 1000),
  (65564, 357551747146842124, 1230),
  (65564, 232631945325051906, 200),
  (65564, 1012789763679465482, 0);