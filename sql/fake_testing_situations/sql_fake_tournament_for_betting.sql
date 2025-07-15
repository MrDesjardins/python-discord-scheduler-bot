-- Create a fake tournament data for testing bet
-- Use cases:
-- 1. Use the /bet command
-- 2. Select a tournament
-- 3. Select a game
-- 4. Place a bet on the game (try <= 10$ and above 10$)
-- 5. Check the bet wallet /betwallet
-- 6. Check the leaderboard /betleaderboard
-- Delete Everything
DELETE FROM user_tournament
WHERE
  tournament_id = 9191222;
DELETE FROM bet_ledger_entry
WHERE
  tournament_id = 9191222;
DELETE FROM bet_user_game
WHERE
  tournament_id = 9191222;
DELETE FROM tournament_game
WHERE
  tournament_id = 9191222;
DELETE FROM bet_user_tournament
WHERE
  tournament_id = 9191222;
DELETE FROM bet_game
WHERE
  tournament_id = 9191222;
DELETE FROM tournament
WHERE
  id = 9191222;



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
    has_finished,
    team_size
  )
VALUES
  (
    9191222,
    1281020861591326803,
    '1v1 for bet #1',
    '2025-01-01 00:00:00',
    '2025-01-10 00:00:00',
    '2027-01-31 00:00:00',
    3,
    8,
    'oregon,villa,clubhouse,kafe,consulate',
    true,
    false,
    1
  );

-- Create fake tournament players
INSERT INTO
  user_tournament (tournament_id, user_id, registration_date)
VALUES
  (9191222, 588915156608876557, '2024-12-01 00:00:00'),
  (9191222, 357551747146842124, '2024-12-01 00:00:00'),
  (9191222, 232631945325051906, '2024-12-01 00:00:00'),
  (9191222, 488465866820812810, '2024-12-01 00:00:00'),
  (9191222, 333109962861576202, '2024-12-01 00:00:00'),
  (9191222, 261398260952858624, '2024-12-01 00:00:00'),
  (9191222, 212669889012301824, '2024-12-01 00:00:00'),
  (9191222, 557002311071694849, '2024-12-01 00:00:00'),
  (9191222, 342114709425881089, '2024-12-01 00:00:00'),
  (9191222, 97116159958081536, '2024-12-01 00:00:00'),
  (9191222, 151068544484769793, '2024-12-01 00:00:00'),
  (
    9191222,
    10120789763679465482,
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
    10150,
    9191222,
    NULL,
    NULL,
    588915156608876557,
    357551747146842124,
    'oregon',
    357551747146842124,
    '5-3'
  ),
  (
    10140,
    9191222,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    10130,
    9191222,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    333109962861576202,
    '5-4'
  ),
  (
    10120,
    9191222,
    NULL,
    NULL,
    212669889012301824,
    557002311071694849,
    'oregon',
    NULL,
    '5-3'
  ),
  (
    10110,
    9191222,
    NULL,
    NULL,
    342114709425881089,
    97116159958081536,
    'villa',
    NULL,
    NULL
  ),
  (
    10100,
    9191222,
    NULL,
    NULL,
    151068544484769793,
    1012789763679465482,
    'clubhouse',
    NULL,
    NULL
  ),
  (
    10090,
    9191222,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10080,
    9191222,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10070,
    9191222,
    10140,
    10150,
    232631945325051906,
    357551747146842124,
    'skyscraper',
    NULL,
    NULL
  ),
  (
    10060,
    9191222,
    10120,
    10130,
    333109962861576202,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10050,
    9191222,
    10100,
    10110,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10040,
    9191222,
    10080,
    10090,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10020,
    9191222,
    10040,
    10050,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10030,
    9191222,
    10060,
    10070,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    10010,
    9191222,
    10020,
    10030,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  );

-- Add wallets
INSERT INTO bet_user_tournament(id, tournament_id, user_id, amount)
VALUES
  (100, 9191222, 588915156608876557, 1000),
  (200, 9191222, 357551747146842124, 1000),
  (300, 9191222, 232631945325051906, 1000),
  (400, 9191222, 488465866820812810, 1000),
  (500, 9191222, 333109962861576202, 1000),
  (700, 9191222, 212669889012301824, 1000),
  (600, 9191222, 261398260952858624, 1000),
  (800, 9191222, 557002311071694849, 1000),
  (900, 9191222, 342114709425881089, 1000),
  (1000, 9191222, 97116159958081536, 1000),
  (1100, 9191222, 151068544484769793, 1000),
  (1200, 9191222, 1012789763679465482, 1000);

-- Add some bets

-- Bet on a game completed but not yet distributed
INSERT INTO
  bet_game (
    id,
    tournament_id,
    tournament_game_id,
    probability_user_1_win,
    probability_user_2_win,
    bet_distributed
  )
VALUES
  (90000, 9191222, 10150, 0.10, 0.90, 0);

-- Bet on a game not completed and not yet distributed
INSERT INTO
  bet_game (
    id,
    tournament_id,
    tournament_game_id,
    probability_user_1_win,
    probability_user_2_win,
    bet_distributed
  )
VALUES
  (90010, 9191222, 10110, 0.25, 0.75, 0);

-- Bet on a game not completed and not yet distributed
INSERT INTO
  bet_game (
    id,
    tournament_id,
    tournament_game_id,
    probability_user_1_win,
    probability_user_2_win,
    bet_distributed
  )
VALUES
  (90020, 9191222, 10100, 0.40, 0.60, 0);

INSERT INTO 
  bet_user_game (
            tournament_id,
            bet_game_id,
            user_id,
            amount,
            user_id_bet_placed,
            time_bet_placed,
            probability_user_win_when_bet_placed,
            bet_distributed)
VALUES
  (9191222, 90000, 232631945325051906, 1000, 588915156608876557, '2024-12-01 00:00:00', 0.10, 0),
  (9191222, 90010, 232631945325051906, 500, 357551747146842124, '2024-12-01 00:00:00', 0.90, 0),
  (9191222, 90020, 212669889012301824, 40, 488465866820812810, '2024-12-01 00:00:00', 0.50, 0)
;