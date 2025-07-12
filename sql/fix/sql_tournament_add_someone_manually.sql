-- User to add 
358015434655793152

select * from tournament_game where tournament_id = 2;

update tournament_game
set user2_id = 358015434655793152,
user_winner_id = NULL,
score= NULL,
map = 'chalet',
timestamp= NULL
where tournament_id = 2 
and id = 12;

update tournament_game
set user2_id = NULL,
user1_id = NULL,
user_winner_id = NULL,
score= NULL,
map = NULL,
timestamp= NULL
where tournament_id = 2 
and id in (18,21,22);


insert into bet_game(tournament_id, tournament_game_id, probability_user_1_win, probability_user_2_win, bet_distributed)
VALUES (2, 12, 0.6, 0.4, false);

insert into user_tournament(user_id, tournament_id, registration_date)
VALUES (358015434655793152, 2, '2025-01-29T03:36:08.976570+00:00');