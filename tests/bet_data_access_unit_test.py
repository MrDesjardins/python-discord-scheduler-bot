""" Test that touch the bet and the database """

from datetime import datetime
from unittest.mock import patch
import pytest

from deps.bet.bet_data_access import (
    data_access_create_bet_user_wallet_for_tournament,
    delete_all_bet_tables,
    data_access_get_bet_user_wallet_for_tournament,
)
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and Teardown for the test"""
    # Setup
    database_manager.set_database_name(DATABASE_NAME_TEST)
    delete_all_bet_tables()

    # Yield control to the test functions
    yield

    # Teardown
    database_manager.set_database_name(DATABASE_NAME)


def test_get_user_wallet_if_no_wallet() -> None:
    """Test that check if the user has no wallet"""
    # Arrange
    user_id = 1
    tournament_id = 1

    # Act
    wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, user_id)

    # Assert
    assert wallet is None


def test_create_and_get_wallet() -> None:
    """Test that create a wallet and then get it"""
    # Arrange
    user_id = 1
    tournament_id = 1
    initial_amount = 100

    # Act
    data_access_create_bet_user_wallet_for_tournament(tournament_id, user_id, initial_amount)
    wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, user_id)

    # Assert
    assert wallet is not None
    assert wallet.tournament_id == tournament_id
    assert wallet.user_id == user_id
    assert wallet.amount == initial_amount
