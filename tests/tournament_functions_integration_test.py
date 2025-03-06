"""Test the integration with the database to create, join and apply lost/win to matches"""

from datetime import datetime, timezone
from typing import List, Union
from unittest.mock import patch
import pytest
from deps.bet.bet_data_class import BetLedgerEntry, BetUserTournament
from deps.bet.bet_functions import place_bet_for_game
from deps.bet.bet_data_access import (
    data_access_fetch_bet_games_by_tournament_id,
    data_access_get_bet_ledger_entry_for_tournament,
    data_access_get_bet_user_wallet_for_tournament,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager
from deps.tournaments.tournament_data_access import (
    data_access_insert_tournament,
    fetch_tournament_games_by_tournament_id,
    fetch_tournament_open_registration,
)
from deps.tournaments.tournament_functions import (
    build_tournament_tree,
    register_for_tournament,
    report_lost_tournament,
    fetch_tournament_by_id,
    start_tournament,
)
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.tournaments.tournament_visualizer import plot_tournament_bracket
from tests.mock_model import mock_user1, mock_user2, mock_user3, mock_user4, mock_user5, mock_user6

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
USER6_ID = 6


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


async def test_full_registration_tournament() -> None:
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

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True
    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    await start_tournament(tournament)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    node1_user1 = tournament_tree.next_game1.user1_id  # Will lose
    node1_user2 = tournament_tree.next_game1.user2_id  # Will win, then lose
    node2_user1 = tournament_tree.next_game2.user1_id  # Will win, then win (winner of the tournament)
    node2_user2 = tournament_tree.next_game2.user2_id  # Will win
    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = await report_lost_tournament(tournament_id, node1_user1, "7-5")
        assert report_result.is_successful is True, report_result.text
        report_result = await report_lost_tournament(tournament_id, node2_user2, "5-2")
        assert report_result.is_successful is True, report_result.text
        report_result = await report_lost_tournament(tournament_id, node1_user2, "6-9")

    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    assert tournament_tree.user_winner_id == node2_user1


async def test_partial_one_registration_tournament() -> None:
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

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True

    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    await start_tournament(tournament)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    node1_user1 = tournament_tree.next_game1.user1_id  # Will lose
    node1_user2 = tournament_tree.next_game1.user2_id  # Will win, then lose
    node2_user1 = tournament_tree.next_game2.user1_id  # Will win, then win (winner of the tournament)
    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = await report_lost_tournament(tournament_id, node1_user1, "7-5")
        assert report_result.is_successful is True, report_result.text
        report_result = await report_lost_tournament(tournament_id, node1_user2, "8-7")
        assert report_result.is_successful is True, report_result.text

    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    assert tournament_tree.user_winner_id == node2_user1


async def test_very_small_participation_reduce_tournament_size() -> None:
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
    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True

    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    await start_tournament(tournament)  # Need to reduce the tournament to the closest power of 2 which is 4 (2^2)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    node1_user1 = tournament_tree.next_game1.user1_id  # Will lose
    node1_user2 = tournament_tree.next_game1.user2_id  # Will win, then lose
    node2_user1 = tournament_tree.next_game2.user1_id  # Will win, then win (winner of the tournament)
    node2_user2 = tournament_tree.next_game2.user2_id  # Will lose
    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = await report_lost_tournament(tournament_id, node1_user1, "7-5")
        assert report_result.is_successful is True
        report_result = await report_lost_tournament(tournament_id, node2_user2, "4-5")
        assert report_result.is_successful is True
        report_result = await report_lost_tournament(tournament_id, node1_user2, "1-5")
        assert report_result.is_successful is True
    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    assert tournament_tree.user_winner_id == node2_user1


async def test_partial_registration_tournament_report_not_in_tournament() -> None:
    """
    Test if someone not in the tournament report a lost
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

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
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

    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    await start_tournament(tournament)

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = await report_lost_tournament(tournament_id, 1111111111222222, "7-5")
        assert report_result.is_successful is False


async def test_reporting_if_already_lost() -> None:
    """
    Test if someone cannot report a lost because already lost
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

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
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

    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    await start_tournament(tournament)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    node1_user2 = tournament_tree.next_game1.next_game1.user2_id

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = await report_lost_tournament(tournament_id, node1_user2, "7-5")
        assert report_result.is_successful is True, report_result.text
        report_result = await report_lost_tournament(tournament_id, node1_user2, "7-5")
        assert report_result.is_successful is False, report_result.text


async def test_partial_registration_tournament_two_level_lost() -> None:
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

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
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

    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    await start_tournament(tournament)

    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    node1_user1 = tournament_tree.next_game1.next_game1.user1_id
    node1_user2 = tournament_tree.next_game1.next_game1.user2_id
    node2_user1 = tournament_tree.next_game1.next_game2.user1_id
    node2_user2 = tournament_tree.next_game1.next_game2.user2_id
    node3_user1 = tournament_tree.next_game2.next_game1.user1_id

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = date_start
        report_result = await report_lost_tournament(tournament_id, node1_user2, "7-5")
        assert report_result.is_successful is True
        report_result = await report_lost_tournament(tournament_id, node2_user2, "7-5")
        assert report_result.is_successful is True
        report_result = await report_lost_tournament(tournament_id, node2_user1, "7-5")
        assert report_result.is_successful is True
        report_result = await report_lost_tournament(tournament_id, node1_user1, "7-5")
    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    assert tournament_tree.user_winner_id == node3_user1
    assert tournament_tree.next_game1.user_winner_id == node1_user1
    assert tournament_tree.next_game2.user_winner_id == node3_user1
    assert tournament_tree.next_game1.next_game1.user_winner_id == node1_user1
    assert tournament_tree.next_game1.next_game2.user_winner_id == node2_user1


async def test_daily_registration_message_no_tournament_available() -> None:
    """
    Create few tournament and make sure the command to retrieve the registration works
    """
    before_all_registration = datetime(2024, 10, 31, 12, 30, 0, tzinfo=timezone.utc)
    register_date_start = datetime(2024, 11, 1, 12, 30, 0, tzinfo=timezone.utc)
    register_date_start2 = datetime(2024, 11, 2, 12, 30, 0, tzinfo=timezone.utc)
    date_start = datetime(2024, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
    date_start2 = datetime(2024, 11, 3, 10, 30, 0, tzinfo=timezone.utc)
    date_end = datetime(2024, 11, 3, 20, 30, 0, tzinfo=timezone.utc)
    date_end2 = datetime(2024, 11, 4, 20, 30, 0, tzinfo=timezone.utc)
    data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        9,
        2,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )

    data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start2,
        date_start2,
        date_end2,
        9,
        2,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )
    with patch("deps.tournaments.tournament_data_access.datetime") as mock_datetime:
        mock_datetime.now.return_value = before_all_registration
        list_tournaments = fetch_tournament_open_registration(GUILD_ID)
        assert len(list_tournaments) == 0


async def test_daily_registration_message_tournament_available() -> None:
    """
    Create few tournament and make sure the command to retrieve the registration works
    """
    register_date_start = datetime(2024, 11, 1, 12, 30, 0, tzinfo=timezone.utc)
    register_date_start2 = datetime(2024, 11, 2, 12, 30, 0, tzinfo=timezone.utc)
    date_start = datetime(2024, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
    date_start2 = datetime(2024, 11, 3, 10, 30, 0, tzinfo=timezone.utc)
    date_end = datetime(2024, 11, 3, 20, 30, 0, tzinfo=timezone.utc)
    date_end2 = datetime(2024, 11, 4, 20, 30, 0, tzinfo=timezone.utc)
    data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        9,
        2,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )

    data_access_insert_tournament(
        GUILD_ID,
        "My Tournament 2",
        register_date_start2,
        date_start2,
        date_end2,
        9,
        2,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )
    with patch("deps.tournaments.tournament_data_access.datetime") as mock_datetime:
        mock_datetime.now.return_value = register_date_start
        list_tournaments = fetch_tournament_open_registration(GUILD_ID)
        assert len(list_tournaments) == 1


async def test_daily_registration_message_tournament_available_but_no_space() -> None:
    """
    Create few tournament and make sure the command to retrieve the registration works
    """
    register_date_start = datetime(2024, 11, 1, 12, 30, 0, tzinfo=timezone.utc)
    date_start = datetime(2024, 11, 2, 10, 30, 0, tzinfo=timezone.utc)
    date_end = datetime(2024, 11, 3, 20, 30, 0, tzinfo=timezone.utc)
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        9,
        2,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )

    with patch("deps.tournaments.tournament_data_access.datetime") as mock_datetime:
        with patch("deps.tournaments.tournament_functions.datetime") as mock_datetime2:
            mock_datetime.now.return_value = register_date_start
            mock_datetime2.now.return_value = register_date_start

            register_result = register_for_tournament(tournament_id, USER1_ID)
            assert register_result.is_successful is True, register_result.text

            list_tournaments = fetch_tournament_open_registration(GUILD_ID)
            assert len(list_tournaments) == 1

            register_result = register_for_tournament(tournament_id, USER2_ID)
            assert register_result.is_successful is True, register_result.text

            list_tournaments = fetch_tournament_open_registration(GUILD_ID)
            assert len(list_tournaments) == 0  # Because we accept only 2 people in this tournament


async def test_full_tournament() -> None:
    """
    Create a tournament that is not full and perform the operations that user would do until
    the end of the tournament
    """
    #                            [7:U1=3, U2=6]
    #                            /           \
    #              [5:U1=2, U2=3]            [6:U1=6, U2=?]
    #                /        \                 /         \
    #    [1:U1=1, U2=2] [2:U1=3, U2=4] [3:U1=5, U2=6] [4:U1=?, U2=?]
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        3,
        16,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER5_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER6_ID)
        assert register_result.is_successful is True, register_result.text

    with patch("random.shuffle") as mock_shuffle:
        mock_shuffle.side_effect = lambda x: None  # No-op: does not shuffle the list
        tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
        if tournament is None:
            assert False, "Tournament is None"
        await start_tournament(tournament)
    bet_games_to_assert = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert len(bet_games_to_assert) == 3
    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    u1 = (
        tournament_tree.next_game1.next_game1.user1_id
        if tournament_tree.next_game1 and tournament_tree.next_game1.next_game1
        else None
    )
    u2 = tournament_tree.next_game1.next_game1.user2_id
    u3 = tournament_tree.next_game1.next_game2.user1_id
    u4 = tournament_tree.next_game1.next_game2.user2_id
    u5 = tournament_tree.next_game2.next_game1.user1_id
    u6 = tournament_tree.next_game2.next_game1.user2_id
    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        with patch("deps.tournaments.tournament_visualizer.fetch_user_info") as mock_fetch_user_info:
            mock_tournament_functions_datetime.now.return_value = date_start
            mock_fetch_user_info.return_value = {
                1: mock_user1,
                2: mock_user2,
                3: mock_user3,
                4: mock_user4,
                5: mock_user5,
                6: mock_user6,
            }
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_1.png",
            )
            report_result = await report_lost_tournament(tournament_id, u1, "7-5")
            assert report_result.is_successful is True, report_result.text
            bet_games_to_assert = data_access_fetch_bet_games_by_tournament_id(tournament_id)
            assert len([b for b in bet_games_to_assert if not b.bet_distributed]) == 2
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_2.png",
            )
            report_result = await report_lost_tournament(tournament_id, u4, "5-2")
            assert report_result.is_successful is True, report_result.text
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_3.png",
            )
            report_result = await report_lost_tournament(tournament_id, u2, "2-4")
            assert report_result.is_successful is True, report_result.text
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_4.png",
            )
            report_result = await report_lost_tournament(tournament_id, u5, "1-2")
            assert report_result.is_successful is True, report_result.text
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_5.png",
            )
            report_result = await report_lost_tournament(tournament_id, u6, "5-2")
            assert report_result.is_successful is True, report_result.text
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_6.png",
            )
    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    assert tournament_tree.user_winner_id == u3
    bet_games_to_assert = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert len([b for b in bet_games_to_assert if not b.bet_distributed]) == 0


async def test_full_tournament_many_winning_bet_and_one_lost() -> None:
    """
    Create a tournament that is not full and perform the operations that user would do until
    the end of the tournament
    """
    #                            [7:U1=3, U2=6]
    #                            /           \
    #              [5:U1=2, U2=3]            [6:U1=6, U2=?]
    #                /        \                 /         \
    #    [1:U1=1, U2=2] [2:U1=3, U2=4] [3:U1=5, U2=6] [4:U1=?, U2=?]
    tournament_id = data_access_insert_tournament(
        GUILD_ID,
        "My Tournament",
        register_date_start,
        date_start,
        date_end,
        3,
        16,
        "villa,clubhouse,consulate,chalet,oregon,coastline,border",
    )

    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        mock_tournament_functions_datetime.now.return_value = after_register_date_start
        register_result = register_for_tournament(tournament_id, USER1_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER2_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER3_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER4_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER5_ID)
        assert register_result.is_successful is True, register_result.text
        register_result = register_for_tournament(tournament_id, USER6_ID)
        assert register_result.is_successful is True, register_result.text

    with patch("random.shuffle") as mock_shuffle:
        mock_shuffle.side_effect = lambda x: None  # No-op: does not shuffle the list
        tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
        if tournament is None:
            assert False, "Tournament is None"
        await start_tournament(tournament)
    bet_games_to_assert = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert len(bet_games_to_assert) == 3
    tournament: Union[Tournament, None] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        assert False, "Tournament is None"
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    u1 = tournament_tree.next_game1.next_game1.user1_id
    u2 = tournament_tree.next_game1.next_game1.user2_id
    u3 = tournament_tree.next_game1.next_game2.user1_id
    u4 = tournament_tree.next_game1.next_game2.user2_id
    u5 = tournament_tree.next_game2.next_game1.user1_id
    u6 = tournament_tree.next_game2.next_game1.user2_id
    with patch("deps.tournaments.tournament_functions.datetime") as mock_tournament_functions_datetime:
        with patch("deps.tournaments.tournament_visualizer.fetch_user_info") as mock_fetch_user_info:
            mock_tournament_functions_datetime.now.return_value = date_start
            mock_fetch_user_info.return_value = {
                1: mock_user1,
                2: mock_user2,
                3: mock_user3,
                4: mock_user4,
                5: mock_user5,
                6: mock_user6,
            }
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_1.png",
            )
            place_bet_for_game(tournament_id, bet_games_to_assert[0].id, mock_user4.id, 50, u2)
            place_bet_for_game(tournament_id, bet_games_to_assert[0].id, mock_user5.id, 200, u2)
            place_bet_for_game(tournament_id, bet_games_to_assert[0].id, mock_user6.id, 500, u1)
            report_result = await report_lost_tournament(tournament_id, u1, "7-5")
            assert report_result.is_successful is True, report_result.text
            bet_games_to_assert = data_access_fetch_bet_games_by_tournament_id(tournament_id)
            assert len([b for b in bet_games_to_assert if not b.bet_distributed]) == 2
            bet_user_games_to_assert: List[BetLedgerEntry] = data_access_get_bet_ledger_entry_for_tournament(
                tournament_id
            )
            assert bet_user_games_to_assert[0].amount == 100
            assert bet_user_games_to_assert[1].amount == pytest.approx(363.636, abs=1e-3)
            assert bet_user_games_to_assert[2].amount == 0
            wallet: Union[BetUserTournament, None] = data_access_get_bet_user_wallet_for_tournament(
                tournament_id, mock_user4.id
            )
            if wallet is None:
                assert False, "Wallet is None"
            assert wallet.amount == 1050
            wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, mock_user5.id)
            if wallet is None:
                assert False, "Wallet is None"
            assert wallet.amount == pytest.approx(1163.636, abs=1e-3)
            wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, mock_user6.id)
            if wallet is None:
                assert False, "Wallet is None"
            assert wallet.amount == 500
            tree = build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id))
            if tree is None:
                assert False, "Tree is None"
            plot_tournament_bracket(
                tournament,
                tree,
                True,
                "./tests/generated_contents/bracket_2.png",
            )
            report_result = await report_lost_tournament(tournament_id, u4, "5-2")
            assert report_result.is_successful is True, report_result.text
            tree = build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id))
            if tree is None:
                assert False, "Tree is None"
            plot_tournament_bracket(
                tournament,
                tree,
                True,
                "./tests/generated_contents/bracket_3.png",
            )
            report_result = await report_lost_tournament(tournament_id, u2, "2-4")
            assert report_result.is_successful is True, report_result.text
            tree = build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id))
            if tree is None:
                assert False, "Tree is None"
            plot_tournament_bracket(
                tournament,
                tree,
                True,
                "./tests/generated_contents/bracket_4.png",
            )
            report_result = await report_lost_tournament(tournament_id, u5, "1-2")
            assert report_result.is_successful is True, report_result.text
            tree = build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id))
            if tree is None:
                assert False, "Tree is None"
            plot_tournament_bracket(
                tournament,
                tree,
                True,
                "./tests/generated_contents/bracket_5.png",
            )
            report_result = await report_lost_tournament(tournament_id, u6, "5-2")
            assert report_result.is_successful is True, report_result.text
            plot_tournament_bracket(
                tournament,
                build_tournament_tree(fetch_tournament_games_by_tournament_id(tournament_id)),
                True,
                "./tests/generated_contents/bracket_6.png",
            )
    # The tournament is over, get the winner
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_tree = build_tournament_tree(tournament_games)
    if tournament_tree is None:
        assert False, "Tournament tree is None"
    assert tournament_tree.user_winner_id == u3
    bet_games_to_assert = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    assert len([b for b in bet_games_to_assert if not b.bet_distributed]) == 0
