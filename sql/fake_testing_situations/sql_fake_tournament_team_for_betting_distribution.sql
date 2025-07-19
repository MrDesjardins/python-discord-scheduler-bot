-- Create a fake 2v2 tournament data that is not yet completed when reporting the next match
-- Use case: Gaining or losing a bet

-- 1. /reportlosttournament
-- 2. /betleaderboard 
-- Should see Yuuka with 11000.00 (had 1000 + *10)
-- Should see Hank with 1000.00 (Had 1000+1000 bet that he lost)

-- Delete Everything
DELETE FROM tournament_team_members
WHERE
  tournament_id = 77228;
DELETE FROM user_tournament
WHERE
  tournament_id = 77228;
DELETE FROM bet_ledger_entry
WHERE
  tournament_id = 77228;
DELETE FROM bet_user_game
WHERE
  tournament_id = 77228;
DELETE FROM tournament_game
WHERE
  tournament_id = 77228;
DELETE FROM bet_user_tournament
WHERE
  tournament_id = 77228;
DELETE FROM bet_game
WHERE
  tournament_id = 77228;
DELETE FROM tournament
WHERE
  id = 77228;



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
    77228,
    1281020861591326803,
    'Fake Team 2v2 for bet #1 inside tournament',
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
  (77228, 588915156608876557, '2024-12-01 00:00:00'),
  (77228, 357551747146842124, '2024-12-01 00:00:00'),
  (77228, 232631945325051906, '2024-12-01 00:00:00'),
  (77228, 488465866820812810, '2024-12-01 00:00:00'),
  (77228, 333109962861576202, '2024-12-01 00:00:00'),
  (77228, 261398260952858624, '2024-12-01 00:00:00'),

  (77228, 212669889012301824, '2024-12-01 00:00:00'),
  (77228, 557002311071694849, '2024-12-01 00:00:00'),
  (77228, 342114709425881089, '2024-12-01 00:00:00'),
  (77228, 97116159958081536, '2024-12-01 00:00:00'),
  (77228, 151068544484769793, '2024-12-01 00:00:00'),
  (77228, 1012789763679465482, '2024-12-01 00:00:00');


INSERT INTO tournament_team_members (
    user_leader_id,
    tournament_id,
    user_id
) VALUES
  (588915156608876557, 77228, 212669889012301824),
  (357551747146842124, 77228, 557002311071694849),
  (232631945325051906, 77228, 342114709425881089),
  (488465866820812810, 77228, 97116159958081536),
  (333109962861576202, 77228, 151068544484769793),
  (261398260952858624, 77228, 1012789763679465482);


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
    33151,
    77228,
    NULL,
    NULL,
    588915156608876557,
    357551747146842124,
    'oregon',
    357551747146842124,
    '5-3'
  ),
  (
    33141,
    77228,
    NULL,
    NULL,
    232631945325051906,
    488465866820812810,
    'villa',
    232631945325051906,
    '3-0'
  ),
  (
    33131,
    77228,
    NULL,
    NULL,
    333109962861576202,
    261398260952858624,
    'skyscraper',
    NULL,
    NULL
  ),
  (
    33121,
    77228,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    33071,
    77228,
    33141,
    33151,
    357551747146842124,
    232631945325051906,
    'map X',
    NULL,
    NULL
  ),
  (
    33061,
    77228,
    33131,
    33121,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    33051,
    77228,
    33071,
    33061,
    NULL,
    NULL,
    NULL,
    NULL, 
    NULL
  );


-- Add wallets
INSERT INTO bet_user_tournament(id, tournament_id, user_id, amount)
VALUES
  (3631, 77228, 588915156608876557, 1000),
  (3632, 77228, 357551747146842124, 1000),
  (3633, 77228, 232631945325051906, 1000),
  (3634, 77228, 488465866820812810, 1000),
  (3635, 77228, 333109962861576202, 1000),
  (3636, 77228, 261398260952858624, 1000),
  (3637, 77228, 212669889012301824, 1000),
  (3638, 77228, 557002311071694849, 1000),
  (3639, 77228, 342114709425881089, 1000),
  (36310, 77228, 97116159958081536, 1000),
  (36311, 77228, 151068544484769793, 1000),
  (36312, 77228, 1012789763679465482, 1000);

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
  (13331, 77228, 33151, 0.10, 0.90, 1),
  (13332, 77228, 33141, 0.20, 0.80, 1),
  (13333, 77228, 33131, 0.20, 0.80, 1),
  (13334, 77228, 33071, 0.30, 0.70, 0);



INSERT INTO 
  bet_user_game (
            id,
            tournament_id,
            bet_game_id,
            user_id,
            amount,
            user_id_bet_placed,
            time_bet_placed,
            probability_user_win_when_bet_placed,
            bet_distributed)
VALUES
  (888887, 77228, 13334, 261398260952858624, 1000, 232631945325051906, '2024-12-01 00:00:00', 0.10, 0), -- win
  (888888, 77228, 13334, 333109962861576202, 1000, 357551747146842124, '2024-12-01 00:00:00', 0.10, 0); -- lose