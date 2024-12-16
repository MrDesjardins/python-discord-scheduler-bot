""" Test the integration with the database to create, join and apply lost/win to matches """

from typing import List
from unittest.mock import patch
import pytest
from datetime import datetime, timezone
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.tournament_data_access import (
    data_access_insert_tournament,
    delete_all_tournament_tables,
    fetch_tournament_games_by_tournament_id,
)
from deps.tournament_functions import (
    build_tournament_tree,
    register_for_tournament,
    report_lost_tournament,
    start_tournaments,
)
from deps.tournament_data_class import TournamentGame


CHANNEL1_ID = 100
CHANNEL2_ID = 200
GUILD_ID = 1000
register_date_start = datetime(2024, 11, 1, 12, 30, 0, tzinfo=timezone.utc)
after_register_date_start = datetime(2024, 11, 2, 13, 30, 0, tzinfo=timezone.utc)
date_start = datetime(2024, 11, 23, 10, 30, 0, tzinfo=timezone.utc)
date_end = datetime(2024, 11, 23, 20, 30, 0, tzinfo=timezone.utc)
USER1_ID = 1
USER2_ID = 2
USER3_ID = 3
USER4_ID = 4
USER5_ID = 5


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    delete_all_tournament_tables()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


def test_full_registration_tournament():
    """
    Create and start a tournament with 4 players (full registration).
    Get the bracket
    Then get the player to report lost.
    """
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        5,
        4,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True

    start_tournaments(date_start)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    node1_user1 = tournament_tree.next_game1.user1_id  # Will lose
    node1_user2 = tournament_tree.next_game1.user2_id  # Will win, then lose
    node2_user1 = tournament_tree.next_game2.user1_id  # Will win, then win (winner of the tournament)
    node2_user2 = tournament_tree.next_game2.user2_id  # Will win
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = report_lost_tournament(tournament_id, node1_user1)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node2_user2)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node1_user2)

    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    assert tournament_tree.user_winner_id == node2_user1


def test_partial_one_registration_tournament():
    """
    Create and start a tournament with 4 players (full registration).
    Get the bracket
    Then get the player to report lost.
    """
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        5,
        4,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True

    start_tournaments(date_start)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    node1_user1 = tournament_tree.next_game1.user1_id  # Will lose
    node1_user2 = tournament_tree.next_game1.user2_id  # Will win, then lose
    node2_user1 = tournament_tree.next_game2.user1_id  # Will win, then win (winner of the tournament)
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = report_lost_tournament(tournament_id, node1_user1)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node1_user2)
        assert report_result.is_successful is True

    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    assert tournament_tree.user_winner_id == node2_user1


def test_very_small_participation_reduce_tournament_size():
    """
    Create and start a tournament with 2 players (but very large tournament, so many node will never have anyone).
    Get the bracket
    Then get the player to report lost.
    """
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        5,
        16,  # Very large, 16 places but only 4 registrations
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True

    start_tournaments(date_start)  # Need to reduce the tournament to the closest power of 2 which is 4 (2^2)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    node1_user1 = tournament_tree.next_game1.next_game1.next_game1.user1_id  # Will lose
    node1_user2 = tournament_tree.next_game1.user2_id  # Will win, then lose
    node2_user1 = tournament_tree.next_game2.user1_id  # Will win, then win (winner of the tournament)
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = report_lost_tournament(tournament_id, node1_user1)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node1_user2)
        assert report_result.is_successful is True

    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    assert tournament_tree.user_winner_id == node2_user1


def test_partial_registration_tournament_two_level_boost():
    """
    Create and start a tournament with 5 players while the tournament is 8 players.
    Get the bracket
    Then get the player to report lost.
    """
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        5,
        8,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )
    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER5_ID)
        assert register_result.is_successful is True

    start_tournaments(date_start)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    node1_user1 = tournament_tree.next_game1.next_game1.user1_id
    node1_user2 = tournament_tree.next_game1.next_game1.user2_id
    node2_user1 = tournament_tree.next_game1.next_game2.user1_id
    node2_user2 = tournament_tree.next_game1.next_game2.user2_id
    node3_user1 = tournament_tree.next_game2.next_game1.user1_id

    with patch("deps.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = report_lost_tournament(tournament_id, node1_user2)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node2_user2)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node2_user1)
        assert report_result.is_successful is True
        report_result = report_lost_tournament(tournament_id, node1_user1)
    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    assert tournament_tree.user_winner_id == node3_user1
    assert tournament_tree.next_game1.user_winner_id == node1_user1
    assert tournament_tree.next_game2.user_winner_id == node3_user1
    assert tournament_tree.next_game1.next_game1.user_winner_id == node1_user1
    assert tournament_tree.next_game1.next_game2.user_winner_id == node2_user1
