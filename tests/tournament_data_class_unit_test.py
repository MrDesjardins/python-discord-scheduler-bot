""" Unit tests for the TournamentData class """

from deps.tournaments.tournament_data_class import Tournament
from deps.functions_date import convert_to_datetime


def test_from_db_row_all_fields() -> None:
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
    assert tournament.registered_user_count == 8
