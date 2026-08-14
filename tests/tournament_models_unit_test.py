from deps.tournaments.tournament_models import FirstTo


def test_first_to_values_represent_rounds_needed_to_win():
    assert [option.value for option in FirstTo] == [3, 5, 7, 9, 12, 16]
