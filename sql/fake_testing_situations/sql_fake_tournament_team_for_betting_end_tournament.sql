-- Create a fake 2v2 tournament data for testing bet
-- Use case: Creating a new bet
-- 1. Use the /bet command
-- 2. Select a tournament
-- 3. Select a game
-- 4. Place a bet on the game (try <= 10$ and above 10$)
-- 5. Check the bet wallet and leaderboard

-- Use case: distributing the bet
--1. Use the /modreportlosttournamentdebug
--2. Set the number 333109962861576202


-- Delete Everything
DELETE FROM tournament_team_members
WHERE
  tournament_id = 44311222;
DELETE FROM user_tournament
WHERE
  tournament_id = 44311222;
DELETE FROM bet_ledger_entry
WHERE
  tournament_id = 44311222;
DELETE FROM bet_user_game
WHERE
  tournament_id = 44311222;
DELETE FROM tournament_game
WHERE
  tournament_id = 44311222;
DELETE FROM bet_user_tournament
WHERE
  tournament_id = 44311222;
DELETE FROM bet_game
WHERE
  tournament_id = 44311222;
DELETE FROM tournament
WHERE
  id = 44311222;



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
    44311222,
    1281020861591326803,
    'Fake Team 2v2 for bet #1',
    '2025-01-01 00:00:00',
    '2025-01-10 00:00:00',
    '2027-01-31 00:00:00',
    3,
    8,
    'oregon,villa,clubhouse,kafe,consulate',
    true,
    false,
    2
  );

-- Create fake tournament players

-- Create fake tournament players
INSERT INTO
  user_tournament (tournament_id, user_id, registration_date)
VALUES
  (44311222, 588915156608876557, '2024-12-01 00:00:00'),
  (44311222, 357551747146842124, '2024-12-01 00:00:00'),
  (44311222, 232631945325051906, '2024-12-01 00:00:00'),
  (44311222, 488465866820812810, '2024-12-01 00:00:00'),
  (44311222, 333109962861576202, '2024-12-01 00:00:00'),
  (44311222, 261398260952858624, '2024-12-01 00:00:00'),

  (44311222, 212669889012301824, '2024-12-01 00:00:00'),
  (44311222, 557002311071694849, '2024-12-01 00:00:00'),
  (44311222, 342114709425881089, '2024-12-01 00:00:00'),
  (44311222, 97116159958081536, '2024-12-01 00:00:00'),
  (44311222, 151068544484769793, '2024-12-01 00:00:00'),
  (44311222, 1012789763679465482, '2024-12-01 00:00:00');


INSERT INTO tournament_team_members (
    user_leader_id,
    tournament_id,
    user_id
) VALUES
  (588915156608876557, 44311222, 212669889012301824),
  (357551747146842124, 44311222, 557002311071694849),
  (232631945325051906, 44311222, 342114709425881089),
  (488465866820812810, 44311222, 97116159958081536),
  (333109962861576202, 44311222, 151068544484769793),
  (261398260952858624, 44311222, 1012789763679465482);


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
    3315,
    44311222,
    NULL,
    NULL,
    588915156608876557,
    357551747146842124,
    'oregon',
    357551747146842124,
    '5-3'
  ),
  (
    3314,
    44311222,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    3313,
    44311222,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    333109962861576202,
    '5-4'
  ),
  (
    3312,
    44311222,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    3307,
    44311222,
    3314,
    3315,
    357551747146842124,
    232631945325051906,
    'skyscraper',
    232631945325051906,
    '7-0'
  ),
  (
    3306,
    44311222,
    3313,
    3312,
    333109962861576202,
    NULL,
    NULL,
    333109962861576202,
    NULL
  ),
  (
    3305,
    44311222,
    3307,
    3306,
    232631945325051906,
    333109962861576202,
    'Coastline',
    NULL, 
    NULL
  );


-- Add wallets
INSERT INTO bet_user_tournament(id, tournament_id, user_id, amount)
VALUES
  (331, 44311222, 588915156608876557, 1000),
  (332, 44311222, 357551747146842124, 1000),
  (333, 44311222, 232631945325051906, 1000),
  (334, 44311222, 488465866820812810, 1000),
  (335, 44311222, 333109962861576202, 1000),
  (336, 44311222, 261398260952858624, 1000),
  (337, 44311222, 212669889012301824, 1000),
  (338, 44311222, 557002311071694849, 1000),
  (339, 44311222, 342114709425881089, 1000),
  (3310, 44311222, 97116159958081536, 1000),
  (3311, 44311222, 151068544484769793, 1000),
  (3312, 44311222, 1012789763679465482, 1000);

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
  (9000, 44311222, 2015, 0.10, 0.90, 0);

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
  (9001, 44311222, 2014, 0.25, 0.75, 0);

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
  (9002, 44311222, 2013, 0.40, 0.60, 0);

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
  (9003, 44311222, 2005, 0.51, 0.49, 0);

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
  (44311222, 9000, 333109962861576202, 1000, 588915156608876557, '2024-12-01 00:00:00', 0.10, 0),
  (44311222, 9001, 261398260952858624, 500, 488465866820812810, '2024-12-01 00:00:00', 0.90, 0),
  (44311222, 9002, 151068544484769793, 40, 333109962861576202, '2024-12-01 00:00:00', 0.50, 0)
;