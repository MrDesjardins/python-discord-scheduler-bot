"""
Test the functions in functions_schedule.py
"""

from unittest.mock import patch
from deps.functions_schedule import get_adjust_reaction_votes
import deps.functions_schedule
from deps.functions_model import get_empty_votes
from deps.models import SimpleUser


@patch.object(deps.functions_schedule, deps.functions_schedule.data_access_get_reaction_message.__name__)
@patch.object(deps.functions_schedule, deps.functions_schedule.data_access_set_reaction_message.__name__)
async def test_get_adjust_reaction_votes_first_to_vote(
    mock_data_access_set_reaction_message, mock_data_access_get_reaction_message
):
    """
    Test adding 1 person into 1 time slot that has no one in it
    """
    mock_data_access_get_reaction_message.return_value = get_empty_votes()
    user = SimpleUser(1, "TestUserName", "Copper")
    result = await get_adjust_reaction_votes(guild_id=1, channel_id=1, message_id=1, user=user, time_clicked="1pm")
    assert len(result["1pm"]) == 1
    assert result["1pm"][0] == user
    mock_data_access_set_reaction_message.assert_called_once()


@patch.object(deps.functions_schedule, deps.functions_schedule.data_access_get_reaction_message.__name__)
@patch.object(deps.functions_schedule, deps.functions_schedule.data_access_set_reaction_message.__name__)
async def test_get_adjust_reaction_votes_second_to_vote(
    mock_data_access_set_reaction_message, mock_data_access_get_reaction_message
):
    """
    Test adding 1 person into 1 time slot that has already 1 person
    """
    existing_vote = get_empty_votes()
    user2 = SimpleUser(2, "TestUserName2", "Copper")
    existing_vote["1pm"].append(user2)
    mock_data_access_get_reaction_message.return_value = existing_vote
    user = SimpleUser(1, "TestUserName", "Copper")
    result = await get_adjust_reaction_votes(guild_id=1, channel_id=1, message_id=1, user=user, time_clicked="1pm")
    assert len(result["1pm"]) == 2
    assert result["1pm"][0] == user2
    assert result["1pm"][1] == user
    mock_data_access_set_reaction_message.assert_called_once()


@patch.object(deps.functions_schedule, deps.functions_schedule.data_access_get_reaction_message.__name__)
@patch.object(deps.functions_schedule, deps.functions_schedule.data_access_set_reaction_message.__name__)
async def test_get_adjust_reaction_votes_remove_one_user(
    mock_data_access_set_reaction_message, mock_data_access_get_reaction_message
):
    """
    Test with two people and removing one that was in the list
    """
    existing_vote = get_empty_votes()
    user1 = SimpleUser(1, "TestUserName", "Copper")
    user2 = SimpleUser(2, "TestUserName2", "Copper")
    existing_vote["1pm"].append(user1)
    existing_vote["1pm"].append(user2)
    mock_data_access_get_reaction_message.return_value = existing_vote
    result = await get_adjust_reaction_votes(guild_id=1, channel_id=1, message_id=1, user=user1, time_clicked="1pm")
    assert len(result["1pm"]) == 1
    assert result["1pm"][0] == user2

    mock_data_access_set_reaction_message.assert_called_once()
