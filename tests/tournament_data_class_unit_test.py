"""Unit tests for the TournamentData class"""

from datetime import datetime, timezone
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.functions_date import convert_to_datetime


def test_tournament_from_db_row_all_fields() -> None:
    """Test loading using the database static method"""
    tournament: Tournament = Tournament.from_db_row(
        (
            1,
            123,
            "Tournament 1",
            "2021-01-01 12:00:00",
            "2021-01-02 12:00:00",
            "2021-01-03 12:00:00",
            3,
            16,
            "Oregon,Clubhouse",
            1,
            0,
            1,
            8,
        )
    )
    assert tournament.id == 1
    assert tournament.guild_id == 123
    assert tournament.name == "Tournament 1"
    assert tournament.registration_date == convert_to_datetime("2021-01-01 12:00:00")
    assert tournament.start_date == convert_to_datetime("2021-01-02 12:00:00")
    assert tournament.end_date == convert_to_datetime("2021-01-03 12:00:00")
    assert tournament.best_of == 3
    assert tournament.max_players == 16
    assert tournament.maps == "Oregon,Clubhouse"
    assert tournament.has_started is True
    assert tournament.has_finished is False
    assert tournament.registered_user_count == 8  # Always last
    assert tournament.team_size == 1


def test_tournament_game_from_db_row_all_fields() -> None:
    """Test loading using the tournament game from the database using a static method"""
    game: TournamentGame = TournamentGame.from_db_row(
        (
            1,
            123,
            8001,
            8002,
            8001,
            "3-1",
            "Oregon",
            datetime(2021, 1, 2, 12, 0, 0, 0, tzinfo=timezone.utc).isoformat(),
            7000,
            70001,
            1,
        )
    )
    assert game.id == 1
    assert game.tournament_id == 123
    assert game.user1_id == 8001
    assert game.user2_id == 8002
    assert game.user_winner_id == 8001
    assert game.score == "3-1"
    assert game.map == "Oregon"
    assert game.timestamp == datetime(2021, 1, 2, 12, 0, 0, 0, tzinfo=timezone.utc)
    assert game.next_game1_id == 7000
    assert game.next_game2_id == 70001
