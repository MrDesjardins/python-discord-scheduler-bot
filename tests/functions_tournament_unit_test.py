"""
Tournament Unit Tests using pytest
"""

import asyncio
import copy
from unittest.mock import patch
from datetime import datetime, timezone
from deps.data_access_data_class import UserInfo
from deps.tournament_functions import build_tournament_tree, can_register_to_tournament, register_for_tournament
from deps.tournament_data_class import Tournament, TournamentGame
from deps.models import Reason

lock = asyncio.Lock()

t1 = datetime(2024, 11, 23, 12, 30, 0, tzinfo=timezone.utc)
t2 = datetime(2024, 11, 24, 12, 30, 0, tzinfo=timezone.utc)
t3 = datetime(2024, 11, 25, 12, 30, 0, tzinfo=timezone.utc)
t4 = datetime(2024, 11, 26, 12, 30, 0, tzinfo=timezone.utc)
t5 = datetime(2024, 11, 27, 12, 30, 0, tzinfo=timezone.utc)
t6 = datetime(2024, 11, 28, 12, 30, 0, tzinfo=timezone.utc)

fake_tournament = Tournament(1, 1, "Test", t2, t4, t6, 3, 4, ["Map 1", "Map 2", "Map 3"], False)

fake_user_1 = UserInfo(1, "User 1", "Rank 1", "User 1", "EASTERN")
fake_user_2 = UserInfo(2, "User 2", "Rank 1", "User 2", "EASTERN")
fake_user_3 = UserInfo(3, "User 3", "Rank 1", "User 3", "EASTERN")
fake_user_4 = UserInfo(4, "User 4", "Rank 1", "User 4", "EASTERN")
fake_user_5 = UserInfo(5, "User 5", "Rank 1", "User 5", "EASTERN")


def test_build_tournament_tree_full_first_round():
    """Test to generate the tree from a list"""
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, now_date),
        TournamentGame(2, 1, 3, 4, None, now_date),
        TournamentGame(3, 1, 5, 6, None, now_date),
        TournamentGame(4, 1, 7, 8, None, now_date),
        TournamentGame(5, 1, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, now_date, 5, 6),
    ]
    tree = build_tournament_tree(list_tournament_games)
    assert tree is not None
    assert tree.id == 7  # Root node
    assert tree.next_game1.id == 5
    assert tree.next_game2.id == 6
    assert tree.next_game1.next_game1.id == 1
    assert tree.next_game1.next_game2.id == 2
    assert tree.next_game2.next_game1.id == 3
    assert tree.next_game2.next_game2.id == 4
    assert tree.next_game1.next_game1.next_game1 is None
    assert tree.next_game1.next_game1.next_game2 is None
    assert tree.next_game1.next_game2.next_game1 is None
    assert tree.next_game1.next_game2.next_game2 is None
    assert tree.next_game2.next_game1.next_game1 is None
    assert tree.next_game2.next_game1.next_game2 is None
    assert tree.next_game2.next_game2.next_game1 is None
    assert tree.next_game2.next_game2.next_game2 is None


def test_build_tournament_tree_partial_first_round():
    """Test to generate the tree from a list that does not have enough participants"""
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: TournamentGame = [
        TournamentGame(1, 1, 1, 2, None, now_date),
        TournamentGame(2, 1, 3, 4, None, now_date),
        TournamentGame(3, 1, 5, 6, None, now_date),
        TournamentGame(4, 1, None, None, None, now_date),  # Missing participants
        TournamentGame(5, 1, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, now_date, 5, 6),
    ]
    tree = build_tournament_tree(list_tournament_games)
    assert tree is not None
    assert tree.id == 7  # Root node
    assert tree.next_game1.id == 5
    assert tree.next_game2.id == 6
    assert tree.next_game1.next_game1.id == 1
    assert tree.next_game1.next_game2.id == 2
    assert tree.next_game2.next_game1.id == 3
    assert tree.next_game2.next_game2.id == 4
    assert tree.next_game1.next_game1.next_game1 is None
    assert tree.next_game1.next_game1.next_game2 is None
    assert tree.next_game1.next_game2.next_game1 is None
    assert tree.next_game1.next_game2.next_game2 is None
    assert tree.next_game2.next_game1.next_game1 is None
    assert tree.next_game2.next_game1.next_game2 is None
    assert tree.next_game2.next_game2.next_game1 is None
    assert tree.next_game2.next_game2.next_game2 is None


def test_can_register_tournament_does_not_exist():
    """Test to check if a user can register for a tournament that does not exist"""
    with patch("deps.tournament_functions.fetch_tournament_by_id", return_value=None):
        reason: Reason = can_register_to_tournament(1, 1)
        assert reason.is_successful is False
        assert reason.text == "The tournament does not exist."


@patch("deps.tournament_functions.datetime")
def test_can_register_tournament_has_started(mock_datetime):
    """Test to check if a user can register for a tournament when registration has not started"""
    mock_datetime.now.return_value = t1
    fake_tournament2 = copy.copy(fake_tournament)
    fake_tournament2.has_started = 1
    with patch(
        "deps.tournament_functions.fetch_tournament_by_id",
        return_value=fake_tournament2,
    ):
        reason: Reason = can_register_to_tournament(1, 1)
        assert reason.is_successful is False
        assert reason.text == "The tournament has already started."


@patch("deps.tournament_functions.datetime")
def test_can_register_tournament_registration_not_started(mock_datetime):
    """Test to check if a user can register for a tournament when registration has not started"""
    mock_datetime.now.return_value = t1
    with patch(
        "deps.tournament_functions.fetch_tournament_by_id",
        return_value=fake_tournament,
    ):
        reason: Reason = can_register_to_tournament(1, 1)
        assert reason.is_successful is False
        assert reason.text == "Registration is not open yet."


@patch("deps.tournament_functions.datetime")
def test_can_register_tournament_registration_closed(mock_datetime):
    """Test to check if a user can register for a tournament when registration is closed"""
    mock_datetime.now.return_value = t5
    with patch(
        "deps.tournament_functions.fetch_tournament_by_id",
        return_value=fake_tournament,
    ):
        reason: Reason = can_register_to_tournament(1, 1)
        assert reason.is_successful is False
        assert reason.text == "Registration is closed."


@patch("deps.tournament_functions.datetime")
def test_can_register_tournament_tournament_full(mock_datetime):
    """Test to check if a user can register for a tournament when it is full"""
    mock_datetime.now.return_value = t3
    with patch(
        "deps.tournament_functions.fetch_tournament_by_id",
        return_value=fake_tournament,
    ):
        with patch(
            "deps.tournament_functions.get_people_registered_for_tournament",
            return_value=[fake_user_2, fake_user_3, fake_user_4, fake_user_5],
        ):
            reason: Reason = can_register_to_tournament(1, 1)
            assert reason.is_successful is False
            assert reason.text == "The tournament is full."


@patch("deps.tournament_functions.datetime")
def test_can_register_tournament_already_registered(mock_datetime):
    """Test to check if a user can register for a tournament when they are already registered"""
    mock_datetime.now.return_value = t3
    with patch(
        "deps.tournament_functions.fetch_tournament_by_id",
        return_value=fake_tournament,
    ):
        with patch("deps.tournament_functions.get_people_registered_for_tournament", return_value=[fake_user_1]):
            reason: Reason = can_register_to_tournament(1, 1)
            assert reason.is_successful is False
            assert reason.text == "You are already registered for the tournament."


@patch("deps.tournament_functions.datetime")
def test_can_register_tournament_success(mock_datetime):
    """Test to check if a user can register for a tournament successfully"""
    mock_datetime.now.return_value = t3
    with patch(
        "deps.tournament_functions.fetch_tournament_by_id",
        return_value=fake_tournament,
    ):
        with patch("deps.tournament_functions.get_people_registered_for_tournament", return_value=[]):
            reason: Reason = can_register_to_tournament(1, 1)
            assert reason.is_successful is True
            assert reason.text is None


def test_register_for_tournament_only_register_when_can_register():
    """Test to check if a user can register for a tournament when they are already registered"""
    with patch("deps.tournament_functions.can_register_to_tournament", return_value=Reason(True)):
        with patch("deps.tournament_functions.register_user_for_tournament", return_value=True) as mock_register:
            reason: Reason = register_for_tournament(1, 2)
            mock_register.assert_called()
            mock_register.assert_called_with(1, 2)
            assert reason.is_successful is True


def test_register_for_tournament_only_register_when_cannot_register():
    """Test to check if we return the rason of the can_register and dont call register"""
    with patch(
        "deps.tournament_functions.can_register_to_tournament", return_value=Reason(False, "Reason from can_register")
    ):
        with patch("deps.tournament_functions.register_user_for_tournament", return_value=True) as mock_register:
            reason: Reason = register_for_tournament(1, 2)
            mock_register.assert_not_called()
            assert reason.is_successful is False
            assert reason.text == "Reason from can_register"
