"""
Tournament Unit Tests using pytest
"""

import asyncio
import copy
from typing import List
from unittest.mock import patch
from datetime import datetime, timezone

import pytest
from deps.bet import bet_functions
from deps.tournaments.tournament_functions import (
    assign_people_to_games,
    auto_assign_winner,
    build_tournament_tree,
    can_register_to_tournament,
    clean_maps_input,
    get_leader_from_teammates,
    get_tournament_final_result_positions,
    has_node_without_user,
    next_power_of_two,
    register_for_tournament,
    report_lost_tournament,
    resize_tournament,
    return_leader,
    start_tournament,
)
from deps.tournaments import tournament_functions
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.models import Reason
from deps.tournaments import tournament_data_access
from tests.mock_model import (
    mock_user1,
    mock_user2,
    mock_user3,
    mock_user4,
    mock_user5,
    mock_user6,
    mock_user7,
    mock_user8,
)

lock = asyncio.Lock()

t1 = datetime(2024, 11, 23, 12, 30, 0, tzinfo=timezone.utc)
t2 = datetime(2024, 11, 24, 12, 30, 0, tzinfo=timezone.utc)
t3 = datetime(2024, 11, 25, 12, 30, 0, tzinfo=timezone.utc)
t4 = datetime(2024, 11, 26, 12, 30, 0, tzinfo=timezone.utc)
t5 = datetime(2024, 11, 27, 12, 30, 0, tzinfo=timezone.utc)
t6 = datetime(2024, 11, 28, 12, 30, 0, tzinfo=timezone.utc)

fake_tournament = Tournament(1, 1, "Test", t2, t4, t6, 3, 4, "Map 1,Map 2,Map 3", False, False, 0, 1)


def test_build_tournament_tree_without_game() -> None:
    """
    Build a tournament tree without game returns None
    """
    tree = build_tournament_tree([])
    assert tree is None


def test_build_tournament_tree_full_first_round() -> None:
    """Test to generate the tree from a list"""
    #                        [7]
    #                       /   \
    #                    [5]    [6]
    #                   / \    /  \
    #               [1]  [2] [3] [4]
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, 7, 8, None, None, None, now_date, None, None),
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    tree = build_tournament_tree(list_tournament_games)
    assert tree is not None
    assert tree.id == 7  # Root node
    assert tree.next_game1 is not None
    assert tree.next_game1.id == 5
    assert tree.next_game2 is not None
    assert tree.next_game2.id == 6
    assert tree.next_game1.next_game1 is not None
    assert tree.next_game1.next_game1.id == 1
    assert tree.next_game1.next_game2 is not None
    assert tree.next_game1.next_game2.id == 2
    assert tree.next_game2.next_game1 is not None
    assert tree.next_game2.next_game1.id == 3
    assert tree.next_game2.next_game2 is not None
    assert tree.next_game2.next_game2.id == 4
    assert tree.next_game1.next_game1.next_game1 is None
    assert tree.next_game1.next_game1.next_game2 is None
    assert tree.next_game1.next_game2.next_game1 is None
    assert tree.next_game1.next_game2.next_game2 is None
    assert tree.next_game2.next_game1.next_game1 is None
    assert tree.next_game2.next_game1.next_game2 is None
    assert tree.next_game2.next_game2.next_game1 is None
    assert tree.next_game2.next_game2.next_game2 is None


def test_build_tournament_tree_partial_first_round() -> None:
    """Test to generate the tree from a list that does not have enough participants"""
    #                        [7]
    #                       /   \
    #                    [5]    [6]
    #                   / \    /  \
    #               [1]  [2] [3] [4]
    now_date = datetime(2024, 11, 25, 11, 30, 0, tzinfo=timezone.utc)
    list_tournament_games: List[TournamentGame] = [
        TournamentGame(1, 1, 1, 2, None, None, None, now_date, None, None),
        TournamentGame(2, 1, 3, 4, None, None, None, now_date, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, now_date, None, None),
        TournamentGame(4, 1, None, None, None, None, None, now_date, None),  # Missing participants
        TournamentGame(5, 1, None, None, None, None, None, now_date, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, now_date, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, now_date, 5, 6),
    ]
    tree = build_tournament_tree(list_tournament_games)
    assert tree is not None
    assert tree.id == 7  # Root node
    assert tree.next_game1 is not None
    assert tree.next_game1.id == 5
    assert tree.next_game2 is not None
    assert tree.next_game2.id == 6
    assert tree.next_game1.next_game1 is not None
    assert tree.next_game1.next_game1.id == 1
    assert tree.next_game1.next_game2 is not None
    assert tree.next_game1.next_game2.id == 2
    assert tree.next_game2.next_game1 is not None
    assert tree.next_game2.next_game1.id == 3
    assert tree.next_game2.next_game2 is not None
    assert tree.next_game2.next_game2.id == 4
    assert tree.next_game1.next_game1.next_game1 is None
    assert tree.next_game1.next_game1.next_game2 is None
    assert tree.next_game1.next_game2.next_game1 is None
    assert tree.next_game1.next_game2.next_game2 is None
    assert tree.next_game2.next_game1.next_game1 is None
    assert tree.next_game2.next_game1.next_game2 is None
    assert tree.next_game2.next_game2.next_game1 is None
    assert tree.next_game2.next_game2.next_game2 is None


@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__, return_value=None)
def test_can_register_tournament_does_not_exist(mock_fetch_tournament_by_id) -> None:
    """Test to check if a user can register for a tournament that does not exist"""
    mock_fetch_tournament_by_id.return_value = None
    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is False
    assert reason.text == "The tournament does not exist."


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__)
def test_can_register_tournament_has_started(mock_tournament, mock_datetime) -> None:
    """Test to check if a user can register for a tournament when registration has not started"""
    mock_datetime.now.return_value = t1
    fake_tournament2 = copy.copy(fake_tournament)
    fake_tournament2.has_started = True
    mock_tournament.has_started = True

    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is False
    assert reason.text == "The tournament has already started."


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__)
def test_can_register_tournament_registration_not_started(mock_tournament, mock_datetime) -> None:
    """Test to check if a user can register for a tournament when registration has not started"""
    mock_datetime.now.return_value = t1
    fake_tournament2 = copy.copy(fake_tournament)
    mock_tournament.return_value = fake_tournament2

    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is False
    assert reason.text == "Registration is not open yet."


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__)
def test_can_register_tournament_registration_closed(mock_tournament, mock_datetime) -> None:
    """Test to check if a user can register for a tournament when registration is closed"""
    mock_datetime.now.return_value = t5
    fake_tournament2 = copy.copy(fake_tournament)
    mock_tournament.return_value = fake_tournament2
    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is False
    assert reason.text == "Registration is closed."


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__)
@patch.object(tournament_functions, tournament_functions.get_people_registered_for_tournament.__name__)
def test_can_register_tournament_tournament_full(mock_get_people, mock_tournament, mock_datetime) -> None:
    """Test to check if a user can register for a tournament when it is full"""
    mock_datetime.now.return_value = t3
    fake_tournament2 = copy.copy(fake_tournament)
    mock_tournament.return_value = fake_tournament2
    mock_get_people.return_value = [mock_user1, mock_user2, mock_user3, mock_user4, mock_user5]
    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is False
    assert reason.text == "The tournament is full."


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__)
@patch.object(tournament_functions, tournament_functions.get_people_registered_for_tournament.__name__)
def test_can_register_tournament_already_registered(mock_get_people, mock_tournament, mock_datetime) -> None:
    """Test to check if a user can register for a tournament when they are already registered"""
    mock_datetime.now.return_value = t3
    fake_tournament2 = copy.copy(fake_tournament)
    mock_tournament.return_value = fake_tournament2
    mock_get_people.return_value = [mock_user1]
    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is False
    assert reason.text == "You are already registered for the tournament."


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__)
@patch.object(tournament_functions, tournament_functions.get_people_registered_for_tournament.__name__)
def test_can_register_tournament_success(mock_get_people, mock_tournament, mock_datetime) -> None:
    """Test to check if a user can register for a tournament successfully"""
    mock_datetime.now.return_value = t3
    fake_tournament2 = copy.copy(fake_tournament)
    mock_tournament.return_value = fake_tournament2
    mock_get_people.return_value = []
    reason: Reason = can_register_to_tournament(1, 1)
    assert reason.is_successful is True
    assert reason.text is None


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.register_user_for_tournament.__name__)
@patch.object(tournament_functions, tournament_functions.can_register_to_tournament.__name__)
def test_register_for_tournament_only_register_when_can_register(
    mock_can_register_to_tournament, mock_register_user_for_tournament, mock_datetime
) -> None:
    """Test to check if a user can register for a tournament when they are already registered"""
    mock_can_register_to_tournament.return_value = Reason(True)
    mock_register_user_for_tournament.return_value = None
    mock_datetime.now.return_value = t2

    reason: Reason = register_for_tournament(1, 2)
    mock_register_user_for_tournament.assert_called()
    mock_register_user_for_tournament.assert_called_with(1, 2, t2)
    assert reason.is_successful is True


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_functions.register_user_for_tournament.__name__)
@patch.object(tournament_functions, tournament_functions.can_register_to_tournament.__name__)
def test_register_for_tournament_only_register_when_cannot_register(
    mock_can_register_to_tournament, mock_register_user_for_tournament, mock_datetime
) -> None:
    """Test to check if we return the rason of the can_register and dont call register"""
    mock_can_register_to_tournament.return_value = Reason(False, "Reason from can_register")
    mock_register_user_for_tournament.return_value = None
    mock_datetime.now.return_value = t2
    reason: Reason = register_for_tournament(1, 2)
    mock_register_user_for_tournament.assert_not_called()
    assert reason.is_successful is False
    assert reason.text == "Reason from can_register"


@patch("deps.tournaments.tournament_functions.random.shuffle")
def test_assign_people_to_games_where_one_participant_alone(mock_shuffle) -> None:
    """Test to assign people to games when there are the maximum number of participants"""
    tournament = fake_tournament
    tournament_games = [
        TournamentGame(1, 1, None, None, None, None, None, None, None, None),
        TournamentGame(2, 1, None, None, None, None, None, None, None, None),
        TournamentGame(3, 1, None, None, None, None, None, None, None, None),
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, None, None, None, None, None, None, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),
    ]
    people = [mock_user1, mock_user2, mock_user3, mock_user4, mock_user5]

    mock_shuffle.side_effect = lambda x: None  # No-op: does not shuffle the list
    result: List[TournamentGame] = assign_people_to_games(tournament, tournament_games, people)
    # Assertions
    assert len(result) == 5  # Should only include enough leaf nodes for people
    assert result[0].user1_id == 1
    assert result[0].user2_id == 2
    assert result[0].map is not None
    assert result[1].user1_id == 3
    assert result[1].user2_id == 4
    assert result[1].map is not None
    assert result[2].user1_id == 5
    assert result[2].user2_id is None
    assert result[2].map is None
    assert result[3].user1_id is None
    assert result[3].user2_id is None
    assert result[3].map is None
    # Ensure random.shuffle was called once
    mock_shuffle.assert_called_once_with(people)


@patch("deps.tournaments.tournament_functions.random.shuffle")
def test_assign_people_to_games_when_full_participant(mock_shuffle) -> None:
    """Test to assign people to games when there are the maximum number of participants"""
    tournament = fake_tournament
    tournament_games = [
        TournamentGame(1, 1, None, None, None, None, None, None, None, None),
        TournamentGame(2, 1, None, None, None, None, None, None, None, None),
        TournamentGame(3, 1, None, None, None, None, None, None, None, None),
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, None, None, None, None, None, None, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),
    ]
    people = [mock_user1, mock_user2, mock_user3, mock_user4, mock_user5, mock_user6, mock_user7, mock_user8]

    mock_shuffle.side_effect = lambda x: None  # No-op: does not shuffle the list
    result: List[TournamentGame] = assign_people_to_games(tournament, tournament_games, people)
    # Assertions
    assert len(result) == 4  # Should only include enough leaf nodes for people
    assert result[0].user1_id == 1
    assert result[0].user2_id == 2
    assert result[0].map is not None
    assert result[1].user1_id == 3
    assert result[1].user2_id == 4
    assert result[1].map is not None
    assert result[2].user1_id == 5
    assert result[2].user2_id == 6
    assert result[2].map is not None
    assert result[3].user1_id == 7
    assert result[3].user2_id == 8
    assert result[3].map is not None
    # Ensure random.shuffle was called once
    mock_shuffle.assert_called_once_with(people)


def test_find_people_in_and_out_team_size_1() -> None:
    """Test to find people in and out when team size is 1"""
    people = [mock_user1, mock_user2, mock_user3, mock_user4]
    team_size = 1
    people_in, people_out = tournament_functions.find_people_in_and_out(people, team_size)
    assert len(people_in) == 4
    assert len(people_out) == 0


def test_find_people_in_and_out_team_size_2_even_number() -> None:
    """Test to find people in and out when team size is 2"""
    people = [mock_user1, mock_user2, mock_user3, mock_user4, mock_user5, mock_user6]
    team_size = 2
    people_in, people_out = tournament_functions.find_people_in_and_out(people, team_size)
    assert len(people_in) == 6
    assert len(people_out) == 0


def test_find_people_in_and_out_team_size_2_odd_number() -> None:
    """Test to find people in and out when team size is 2 and odd number of participants"""
    people = [mock_user1, mock_user2, mock_user3, mock_user4, mock_user5]
    team_size = 2
    people_in, people_out = tournament_functions.find_people_in_and_out(people, team_size)
    assert len(people_in) == 4  # Only 4 can be in the tournament
    assert len(people_out) == 1  # One person is left out


def test_resize_tournament_already_full_no_resize() -> None:
    """Test when no resize needed"""
    new_size = resize_tournament(4, 4)
    assert new_size == 4


def test_resize_tournament_no_full_but_good_size_no_resize() -> None:
    """Test a minimum resize"""
    new_size = resize_tournament(3, 4)
    assert new_size == 4


def test_resize_tournament_no_full_but_good_size_no_resize2() -> None:
    """Test a large resize"""
    new_size = resize_tournament(16, 4)
    assert new_size == 4


def test_auto_assign_winner_on_small_tree() -> None:
    """
    Test to auto assign the winner on a tree with not leaf nodes
    """
    #                            [3:U1=?, U2=?]
    #                            /           \
    #              [1:U1=2, U2=3]            [2:U1=1, U2=?]
    tournament_games = [
        TournamentGame(1, 1, 2, 3, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, None, None, None, None, None, None, None),
        TournamentGame(3, 1, 3, None, None, None, None, None, 1, 2),
    ]
    nodes = auto_assign_winner(tournament_games)
    assert len(nodes) == 2
    assert nodes[0].id == 2  # Node 2
    assert nodes[0].user_winner_id == 1  # User 1 auto-win
    assert nodes[1].id == 3  # Node 2
    assert nodes[1].user1_id == 3
    assert nodes[1].user2_id == 1


def test_auto_assign_winner_on_tree_with_not_leaf_should_auto_win_left_side() -> None:
    """
    Test to auto assign the winner on a tree with not leaf nodes
    """
    #                            [7:U1=?, U2=?]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=?, U2=?]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=?] [4:U1=?, U2=?] <-------------- Should have U1 auto-winner to User #5 from node #3
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, None, None, None, None, None, None, None),  # Still alone should be promoted
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, None, None, None, None, 1, 2),
        TournamentGame(6, 1, 5, None, None, None, None, None, 3, 4),  # Was set in the startup of the tournament
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),  # Should have 5
    ]
    nodes = auto_assign_winner(tournament_games)
    assert len(nodes) == 2
    assert nodes[0].id == 3
    assert nodes[0].user_winner_id == 5
    assert nodes[1].id == 6
    assert nodes[1].user1_id == 5


def test_auto_assign_winner_on_tree_with_not_leaf_should_auto_win_right_side() -> None:
    """
    Test to auto assign the winner on a tree with not leaf nodes
    """
    #                            [7:U1=?, U2=?]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=?, U2=7]  <-------------- Should have U1 to User #5 from node #3
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=?, U2=5] [4:U1=7, U2=8]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, None, 5, None, None, None, None, None, None),  # Still alone should be promoted
        TournamentGame(4, 1, 7, 8, None, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, None, None, None, None, 1, 2),
        TournamentGame(
            6, 1, None, 7, None, None, None, None, 3, 4
        ),  # User 7 won from the game #4, should match user #5 from auto-win
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),  # Should have 5
    ]
    nodes = auto_assign_winner(tournament_games)
    assert len(nodes) == 2
    assert nodes[0].id == 3
    assert nodes[0].user_winner_id == 5
    assert nodes[1].id == 6  # Node id to auto-winner
    assert nodes[1].user1_id == 5  # Auto-winner
    assert nodes[1].user2_id == 7  # Already defined as winner of this side of the bracket


def test_auto_assign_should_happen_with_auto_win_and_assignment() -> None:
    """
    Test that should not auto assign in a situation one side of the tree is way above the other: should just wait
    Tree is like this one:
    """
    #                            [7:U1=?, U2=?]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=?, U2=?]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=6] [4:U1=?, U2=?]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, None, None, None),
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, 3, None, None, None, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),  # Was set in the startup of the tournament
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),  # Should have 5
    ]
    nodes = auto_assign_winner(tournament_games)
    assert len(nodes) == 0


def test_auto_assign_should_not_happen_team_late_to_report() -> None:
    """
    Test that should assign a winner on node 6 because oinly one of its child (3) has one player 5 while the other
    branch 4 has no player
    """
    #                            [7:U1=?, U2=?]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=?, U2=?]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=6] [4:U1=7, U2=8]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, None, None, None),  # Should be promoted
        TournamentGame(4, 1, 7, 8, None, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, 2, None, None, None, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),  # Should get the promotion (parent)
        TournamentGame(7, 1, 2, None, None, None, None, None, 5, 6),  # Should have 5 has one user
    ]
    nodes = auto_assign_winner(tournament_games)
    assert len(nodes) == 0


def test_has_node_without_user_no() -> None:
    """
    Test that should not auto assign in a situation one side of the tree is way above the other: should just wait
    The graph is like this one:
    """
    #                         [7]
    #                       /   \
    #                     [5]    [6]
    #                    / \    /  \
    #                [1]  [2] [3] [4]
    tournament_games = {
        1: TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        2: TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        3: TournamentGame(3, 1, 5, 6, None, None, None, None, None, None),
        4: TournamentGame(4, 1, 7, 8, None, None, None, None, None, None),
        5: TournamentGame(5, 1, 3, 2, 3, None, None, None, 1, 2),
        6: TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),  # Was set in the startup of the tournament
        7: TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),  # Should have 5
    }
    # Leaf at the bottom
    has_branch = has_node_without_user(tournament_games, tournament_games[1])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[2])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[3])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[4])
    assert has_branch is False
    # Level 1
    has_branch = has_node_without_user(tournament_games, tournament_games[5])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[6])
    assert has_branch is False
    # Level 2 (root)
    has_branch = has_node_without_user(tournament_games, tournament_games[7])
    assert has_branch is False


def test_has_node_without_user_one_level_yes() -> None:
    """
    Test that should not auto assign in a situation one side of the tree is way above the other: should just wait
    The graph is like this one:
    """
    #                        [7]
    #                       /   \
    #                    [5]    [6]
    #                   / \    /  \
    #               [1]  [2] [3] [4]
    tournament_games = {
        1: TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        2: TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        3: TournamentGame(3, 1, 5, None, None, None, None, None, None, None),
        4: TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        5: TournamentGame(5, 1, None, None, None, None, None, None, 1, 2),
        6: TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),
        7: TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),
    }
    # Leaf at the bottom
    has_branch = has_node_without_user(tournament_games, tournament_games[1])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[2])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[3])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[4])
    assert has_branch is True
    # Level 1
    has_branch = has_node_without_user(tournament_games, tournament_games[5])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[6])
    assert has_branch is False


def test_has_node_without_user_two_level_yes() -> None:
    """
    Test that should not auto assign in a situation one side of the tree is way above the other: should just wait
    """
    #    The graph is like this one:
    #                         [7]
    #                        /   \
    #                     [5]    [6]
    #                    / \    /  \
    #                [1]  [2] [3]   [4]
    #                        /  \   /  \
    #                    [8]   [9] [10][11]
    # The node 11 doesnt not have users, makike the user of node 10 (user #8) to auto go to node 4 and 6
    tournament_games = {
        1: TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        2: TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        3: TournamentGame(3, 1, 5, None, None, None, None, None, 8, 9),
        4: TournamentGame(4, 1, None, None, None, None, None, None, 10, 11),
        5: TournamentGame(5, 1, None, None, None, None, None, None, 1, 2),
        6: TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),
        7: TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),
        8: TournamentGame(8, 1, 6, 7, None, None, None, None, None, None),
        9: TournamentGame(9, 1, 9, 10, None, None, None, None, None, None),
        10: TournamentGame(10, 1, 8, None, None, None, None, None, None, None),
        11: TournamentGame(11, 1, None, None, None, None, None, None, None, None),
    }
    # Leaf at the bottom
    has_branch = has_node_without_user(tournament_games, tournament_games[1])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[2])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[8])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[9])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[10])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[11])
    assert has_branch is True
    # Level 1
    has_branch = has_node_without_user(tournament_games, tournament_games[5])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[6])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[3])
    assert has_branch is False
    has_branch = has_node_without_user(tournament_games, tournament_games[4])
    assert has_branch is False


def test_auto_assign_set_the_root_user() -> None:
    """
    Test that should not auto assign in a situation one side of the tree is way above the other: should just wait
    Tree is like this one:
    """
    #                            [7:U1=?, U2=?]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=6, U2=?]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=6] [4:U1=?, U2=?]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, 6, None, None, None, None, None, None),
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, 3, None, None, None, 1, 2),
        TournamentGame(6, 1, 6, None, None, None, None, None, 3, 4),  # Was set in the startup of the tournament
        TournamentGame(7, 1, 3, None, None, None, None, None, 5, 6),  # Should have 5
    ]
    nodes = auto_assign_winner(tournament_games)
    assert len(nodes) == 2
    assert nodes[0].id == 6
    assert nodes[0].user_winner_id == 6
    assert nodes[1].id == 7
    assert nodes[1].user1_id == 3
    assert nodes[1].user2_id == 6


def test_get_tournament_final_result_positions_when_tournament_completed() -> None:
    """
    Test the result of the tournament when it is completed
    """
    #                            [7:U1=3, U2=6]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=6, U2=8]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=6] [4:U1=7, U2=8]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, 6, 6, None, None, None, None, None),
        TournamentGame(4, 1, 7, 8, 8, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, 3, None, None, None, 1, 2),
        TournamentGame(6, 1, 6, 8, 6, None, None, None, 3, 4),
        TournamentGame(7, 1, 3, 6, 3, None, None, None, 5, 6),
    ]
    root = build_tournament_tree(tournament_games)
    if root is None:
        assert False
    results = get_tournament_final_result_positions(root)
    if results is None:
        assert False
    assert results.first_place_user_id == 3
    assert results.second_place_user_id == 6
    assert results.third_place_user_id_1 == 2
    assert results.third_place_user_id_2 == 8


def test_get_tournament_final_result_positions_final_match_not_done() -> None:
    """
    Test the result of the tournament when it is completed
    """
    #                            [7:U1=3, U2=6]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=6, U2=8]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=6] [4:U1=7, U2=8]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, 6, 6, None, None, None, None, None),
        TournamentGame(4, 1, 7, 8, 8, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, 3, None, None, None, 1, 2),
        TournamentGame(6, 1, 6, 8, 6, None, None, None, 3, 4),
        TournamentGame(7, 1, 3, 6, None, None, None, None, 5, 6),  # None for the winner
    ]
    root = build_tournament_tree(tournament_games)
    if root is None:
        assert False
    results = get_tournament_final_result_positions(root)
    assert results is None


def test_get_tournament_final_result_positions_semi_final_match_not_done() -> None:
    """
    Test the result of the tournament when it is completed
    """
    #                            [7:U1=3, U2=6]
    #                            /           \
    #              [5:U1=3, U2=2]            [6:U1=6, U2=8]
    #                /        \                 /         \
    #    [1:U1=3, U2=4] [2:U1=1, U2=2] [3:U1=5, U2=6] [4:U1=7, U2=8]
    tournament_games = [
        TournamentGame(1, 1, 3, 4, 3, None, None, None, None, None),
        TournamentGame(2, 1, 1, 2, 2, None, None, None, None, None),
        TournamentGame(3, 1, 5, 6, 6, None, None, None, None, None),
        TournamentGame(4, 1, 7, 8, 8, None, None, None, None, None),
        TournamentGame(5, 1, 3, 2, None, None, None, None, 1, 2),
        TournamentGame(6, 1, 6, 8, None, None, None, None, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),  # None for the winner
    ]
    root = build_tournament_tree(tournament_games)
    if root is None:
        assert False
    results = get_tournament_final_result_positions(root)
    assert results is None


def test_clean_map_single_with_spaces() -> None:
    """
    Test to clean the map with spaces
    """
    map_r6 = "  map  "
    cleaned_map = clean_maps_input(map_r6)
    assert cleaned_map == "map"


def test_clean_map_many_with_spaces() -> None:
    """
    Test to clean the map with spaces
    """
    map_r6 = "map1, map2"
    cleaned_map = clean_maps_input(map_r6)
    assert cleaned_map == "map1,map2"


def test_clean_map_many_with_spaces_and_upper_case() -> None:
    """
    Test to clean the map with spaces
    """
    map_r6 = "map1, map2, Map3, MAP4"
    cleaned_map = clean_maps_input(map_r6)
    assert cleaned_map == "map1,map2,map3,map4"


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_data_access.get_people_registered_for_tournament.__name__)
@patch.object(tournament_functions, tournament_functions.resize_tournament.__name__)
@patch.object(tournament_functions, tournament_data_access.data_access_create_bracket.__name__)
@patch.object(tournament_functions, tournament_data_access.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(tournament_functions, tournament_functions.assign_people_to_games.__name__)
@patch.object(tournament_functions, tournament_functions.auto_assign_winner.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament_games.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament.__name__)
@patch.object(tournament_functions, bet_functions.system_generate_game_odd.__name__)
@patch.object(tournament_functions, tournament_data_access.register_user_teammate_to_leader.__name__)
async def test_start_tournament_success(
    mock_register_user_teammate_to_leader,
    mock_system_generate_game_odd,
    mock_save_tournament,
    mock_save_tournament_games,
    mock_auto_assign_winner,
    mock_assign_people_to_games,
    mock_fetch_games,
    mock_create_bracket,
    mock_resize,
    mock_get_people_registered_for_tournament,
    mock_datetime,
) -> None:
    """
    Test the start of a tournament when all the conditions are met
    """
    # Arrange
    tournament = fake_tournament
    mock_datetime.now.return_value = t3
    mock_get_people_registered_for_tournament.return_value = [mock_user1, mock_user2, mock_user3, mock_user4]
    mock_resize.return_value = 4
    mock_fetch_games.return_value = [
        TournamentGame(1, 1, None, None, None, None, None, None, None, None),
        TournamentGame(2, 1, None, None, None, None, None, None, None, None),
        TournamentGame(3, 1, None, None, None, None, None, None, None, None),
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, None, None, None, None, None, None, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),
    ]
    mock_assign_people_to_games.return_value = [
        TournamentGame(1, 1, None, None, None, None, None, None, 1, 2),
        TournamentGame(2, 1, None, None, None, None, None, None, 3, 4),
        TournamentGame(3, 1, None, None, None, None, None, None, 5, 6),
    ]
    mock_auto_assign_winner.return_value = []

    # Act
    await start_tournament(tournament)

    # Assert
    mock_get_people_registered_for_tournament.assert_called_once_with(tournament.id)
    mock_resize.assert_called_once_with(4, 4)
    mock_create_bracket.assert_called_once_with(tournament.id, 4)
    mock_fetch_games.assert_called_once_with(tournament.id)
    mock_assign_people_to_games.assert_called_once()
    mock_auto_assign_winner.assert_called_once()
    mock_save_tournament_games.assert_called_once()
    mock_save_tournament.assert_called_once()
    mock_system_generate_game_odd.assert_called_once()
    mock_register_user_teammate_to_leader.assert_not_called()


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_data_access.get_people_registered_for_tournament.__name__)
@patch.object(tournament_functions, tournament_functions.resize_tournament.__name__)
@patch.object(tournament_functions, tournament_data_access.data_access_create_bracket.__name__)
@patch.object(tournament_functions, tournament_data_access.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(tournament_functions, tournament_functions.assign_people_to_games.__name__)
@patch.object(tournament_functions, tournament_functions.auto_assign_winner.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament_games.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament.__name__)
@patch.object(tournament_functions, bet_functions.system_generate_game_odd.__name__)
@patch.object(tournament_functions, tournament_data_access.register_user_teammate_to_leader.__name__)
async def test_start_tournament_success_team_odd_participant(
    mock_register_user_teammate_to_leader,
    mock_system_generate_game_odd,
    mock_save_tournament,
    mock_save_tournament_games,
    mock_auto_assign_winner,
    mock_assign_people_to_games,
    mock_fetch_games,
    mock_create_bracket,
    mock_resize,
    mock_get_people_registered_for_tournament,
    mock_datetime,
) -> None:
    """
    Test the start of a tournament when all the conditions are met
    """
    # Arrange
    tournament = fake_tournament
    tournament.team_size = 2
    mock_datetime.now.return_value = t3
    mock_get_people_registered_for_tournament.return_value = [
        mock_user1,
        mock_user2,
        mock_user3,
        mock_user4,
        mock_user5,
    ]
    mock_resize.return_value = 4
    mock_fetch_games.return_value = [
        TournamentGame(1, 1, None, None, None, None, None, None, None, None),
        TournamentGame(2, 1, None, None, None, None, None, None, None, None),
        TournamentGame(3, 1, None, None, None, None, None, None, None, None),
        TournamentGame(4, 1, None, None, None, None, None, None, None, None),
        TournamentGame(5, 1, None, None, None, None, None, None, 1, 2),
        TournamentGame(6, 1, None, None, None, None, None, None, 3, 4),
        TournamentGame(7, 1, None, None, None, None, None, None, 5, 6),
    ]
    mock_assign_people_to_games.return_value = [
        TournamentGame(1, 1, None, None, None, None, None, None, 1, 2),
        TournamentGame(2, 1, None, None, None, None, None, None, 3, 4),
        TournamentGame(3, 1, None, None, None, None, None, None, 5, 6),
    ]
    mock_auto_assign_winner.return_value = []

    # Act
    people_in, people_out = await start_tournament(tournament)

    # Assert
    mock_get_people_registered_for_tournament.assert_called_once_with(tournament.id)
    mock_resize.assert_called_once_with(4, 2)  # 2 because we have team size of 2 (5/2 = 2.5, rounded to 4)
    mock_create_bracket.assert_called_once_with(tournament.id, 4)
    mock_fetch_games.assert_called_once_with(tournament.id)
    mock_assign_people_to_games.assert_called_once()
    mock_auto_assign_winner.assert_called_once()
    mock_save_tournament_games.assert_called_once()
    mock_save_tournament.assert_called_once()
    mock_system_generate_game_odd.assert_called_once()
    assert mock_register_user_teammate_to_leader.call_count == 2
    assert len(people_in) == 4
    assert len(people_out) == 1
    assert people_out[0].id == mock_user5.id


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_data_access.get_people_registered_for_tournament.__name__)
@patch.object(tournament_functions, tournament_functions.resize_tournament.__name__)
@patch.object(tournament_functions, tournament_data_access.data_access_create_bracket.__name__)
@patch.object(tournament_functions, tournament_data_access.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(tournament_functions, tournament_functions.assign_people_to_games.__name__)
@patch.object(tournament_functions, tournament_functions.auto_assign_winner.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament_games.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament.__name__)
@patch.object(tournament_functions, bet_functions.system_generate_game_odd.__name__)
@patch.object(tournament_functions, tournament_data_access.register_user_teammate_to_leader.__name__)
async def test_start_tournament_fail_team_not_enough_participant(
    mock_register_user_teammate_to_leader,
    mock_system_generate_game_odd,
    mock_save_tournament,
    mock_save_tournament_games,
    mock_auto_assign_winner,
    mock_assign_people_to_games,
    mock_fetch_games,
    mock_create_bracket,
    mock_resize,
    mock_get_people_registered_for_tournament,
    mock_datetime,
) -> None:
    """
    Test the start of a tournament when there are 3 people but team are of size 2 (thus minimum of 4 people)
    """
    # Arrange
    tournament = fake_tournament
    tournament.team_size = 2
    mock_datetime.now.return_value = t3
    mock_get_people_registered_for_tournament.return_value = [mock_user1, mock_user2, mock_user3]

    # Act
    with pytest.raises(
        ValueError, match="Not enough players for a tournament. At least 2 teams are required or two people for 1v1."
    ):
        await start_tournament(tournament)

    # Assert
    mock_get_people_registered_for_tournament.assert_called_once_with(tournament.id)
    mock_resize.assert_not_called()
    mock_create_bracket.assert_not_called()
    mock_fetch_games.assert_not_called()
    mock_assign_people_to_games.assert_not_called()
    mock_auto_assign_winner.assert_not_called()
    mock_save_tournament_games.assert_not_called()
    mock_save_tournament.assert_not_called()
    mock_system_generate_game_odd.assert_not_called()
    mock_register_user_teammate_to_leader.not_called()


@patch("deps.tournaments.tournament_functions.datetime")
@patch.object(tournament_functions, tournament_data_access.get_people_registered_for_tournament.__name__)
@patch.object(tournament_functions, tournament_functions.resize_tournament.__name__)
@patch.object(tournament_functions, tournament_data_access.data_access_create_bracket.__name__)
@patch.object(tournament_functions, tournament_data_access.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(tournament_functions, tournament_functions.assign_people_to_games.__name__)
@patch.object(tournament_functions, tournament_functions.auto_assign_winner.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament_games.__name__)
@patch.object(tournament_functions, tournament_data_access.save_tournament.__name__)
@patch.object(tournament_functions, bet_functions.system_generate_game_odd.__name__)
@patch.object(tournament_functions, tournament_data_access.register_user_teammate_to_leader.__name__)
async def test_start_tournament_not_yet_created(
    mock_register_user_teammate_to_leader,
    mock_system_generate_game_odd,
    mock_save_tournament,
    mock_save_tournament_games,
    mock_auto_assign_winner,
    mock_assign_people_to_games,
    mock_fetch_games,
    mock_create_bracket,
    mock_resize,
    mock_get_people_registered_for_tournament,
    mock_datetime,
) -> None:
    """
    Test the start of a tournament when all the conditions are met
    """
    # Arrange
    tournament = fake_tournament
    tournament.id = None
    mock_datetime.now.return_value = t3
    mock_get_people_registered_for_tournament.return_value = []
    mock_resize.return_value = 4
    mock_fetch_games.return_value = []
    mock_assign_people_to_games.return_value = []
    mock_auto_assign_winner.return_value = []

    # Act
    await start_tournament(tournament)

    # Assert
    mock_get_people_registered_for_tournament.assert_not_called()
    mock_resize.assert_not_called()
    mock_create_bracket.assert_not_called()
    mock_fetch_games.assert_not_called()
    mock_assign_people_to_games.assert_not_called()
    mock_auto_assign_winner.assert_not_called()
    mock_save_tournament_games.assert_not_called()
    mock_save_tournament.assert_not_called()
    mock_system_generate_game_odd.assert_not_called()
    mock_register_user_teammate_to_leader.not_called()


async def test_next_power_of_two() -> None:
    """
    Test to get the next power of two
    """
    assert next_power_of_two(0) == 1
    assert next_power_of_two(1) == 1
    assert next_power_of_two(2) == 2
    assert next_power_of_two(3) == 4
    assert next_power_of_two(4) == 4
    assert next_power_of_two(5) == 8
    assert next_power_of_two(6) == 8
    assert next_power_of_two(7) == 8
    assert next_power_of_two(8) == 8
    assert next_power_of_two(9) == 16


@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__, return_value=None)
async def test_report_lost_tournament_no_tournament(mock_fetch_tournament) -> None:
    """
    Test to report a lost tournament when the tournament does not exist
    """
    # Arrange
    tournament_id = 1
    user_id = 1
    score = "7-1"
    mock_fetch_tournament.return_value = None

    # Act
    result = await report_lost_tournament(tournament_id, user_id, score)

    # Assert
    assert result.is_successful is False
    assert result.text == "The tournament does not exist."


@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__, return_value=None)
@patch.object(tournament_functions, tournament_data_access.get_people_registered_for_tournament.__name__)
async def test_report_lost_tournament_user_not_in_tournament(
    mock_get_people_registered_for_tournament, mock_fetch_tournament
) -> None:
    """
    Test that a report was done by someone not in the tournament
    """
    # Arrange
    tournament_id = 1
    score = "7-1"
    mock_fetch_tournament.return_value = fake_tournament
    mock_get_people_registered_for_tournament.return_value = [mock_user2, mock_user3, mock_user4]

    # Act
    result = await report_lost_tournament(tournament_id, mock_user1.id, score)

    # Assert
    assert result.is_successful is False
    assert result.text == "User is not registered for the tournament."


@patch.object(tournament_functions, tournament_functions.fetch_tournament_by_id.__name__, return_value=None)
@patch.object(tournament_functions, tournament_data_access.get_people_registered_for_tournament.__name__)
@patch.object(tournament_functions, tournament_data_access.fetch_tournament_games_by_tournament_id.__name__)
@patch.object(tournament_functions, tournament_functions.build_tournament_tree.__name__)
async def test_report_lost_tournament_no_games_in_tournament(
    mock_build_tournament_tree,
    mock_fetch_tournament_games,
    mock_get_people_registered_for_tournament,
    mock_fetch_tournament,
) -> None:
    """
    Test that a report was done by someone not in the tournament
    """
    # Arrange
    tournament_id = 1
    score = "7-1"
    mock_fetch_tournament.return_value = fake_tournament
    mock_get_people_registered_for_tournament.return_value = [mock_user1, mock_user2, mock_user3, mock_user4]
    mock_fetch_tournament_games.return_value = []
    mock_build_tournament_tree.return_value = None

    # Act
    result = await report_lost_tournament(tournament_id, mock_user1.id, score)

    # Assert
    assert result.is_successful is False
    assert result.text == "The tournament tree is empty."


def test_get_leader_from_teammates() -> None:
    """
    Test the creation of the reverse index from the leader to teammates
    """
    leaders = {1: [10, 11, 12], 2: [20, 21]}
    rev_index = get_leader_from_teammates(leaders)
    assert rev_index[10] == 1
    assert rev_index[11] == 1
    assert rev_index[12] == 1
    assert rev_index[20] == 2
    assert rev_index[21] == 2


def test_return_leader_user_leader() -> None:
    """
    Test the leader if the user is a leader
    """
    leaders = {1: [10, 11, 12], 2: [20, 21]}
    assert return_leader(leaders, 1) == 1
    assert return_leader(leaders, 2) == 2


def test_return_leader_user_teammate() -> None:
    """
    Test to get the leader if the user is a teammate
    """
    leaders = {1: [10, 11, 12], 2: [20, 21]}
    assert return_leader(leaders, 10) == 1
    assert return_leader(leaders, 11) == 1
    assert return_leader(leaders, 12) == 1
    assert return_leader(leaders, 20) == 2
    assert return_leader(leaders, 21) == 2
