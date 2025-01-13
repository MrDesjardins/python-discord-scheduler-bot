""" Test Functions """

from typing import Dict, List
from datetime import datetime, timezone
from unittest.mock import patch
import pytz
from deps.functions import (
    get_current_hour_eastern,
    get_daily_string_message,
    get_empty_votes,
    get_reactions,
    get_sha,
    get_supported_time_time_label,
    get_time_choices,
    get_url_user_profile_main,
    get_url_user_profile_overview,
    get_url_user_ranked_matches,
    get_url_api_ranked_matches,
    most_common,
)
from deps.models import SimpleUser, TimeLabel
from deps.values import COMMAND_SCHEDULE_ADD, MSG_UNIQUE_STRING


def test_most_common_no_tie():
    """Return the most frequent element"""
    list1 = [1, 2, 2]
    result = most_common(list1)
    assert result == 2


def test_most_common_tie():
    """Return the first most common"""
    list1 = [2, 2, 3, 3]
    result = most_common(list1)
    assert result == 2


def test_get_empty_votes():
    """Return an object with empty list of user for each time"""
    result = get_empty_votes()
    assert result == {
        "3pm": [],
        "4pm": [],
        "5pm": [],
        "6pm": [],
        "7pm": [],
        "8pm": [],
        "9pm": [],
        "10pm": [],
        "11pm": [],
        "12am": [],
        "1am": [],
        "2am": [],
    }


def test_get_reactions():
    """Return of all the emojis that can be used to vote"""
    result = get_reactions()
    assert result == ["3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟", "🕚", "🕛", "1️⃣", "2️⃣"]


def test_get_supported_time_time_label():
    """Return a list of TimeLabel objects that represent the supported times"""
    result = get_supported_time_time_label()
    assert result == [
        TimeLabel("3pm", "3pm", "3pm Eastern Time"),
        TimeLabel("4pm", "4pm", "4pm Eastern Time"),
        TimeLabel("5pm", "5pm", "5pm Eastern Time"),
        TimeLabel("6pm", "6pm", "6pm Eastern Time"),
        TimeLabel("7pm", "7pm", "7pm Eastern Time"),
        TimeLabel("8pm", "8pm", "8pm Eastern Time"),
        TimeLabel("9pm", "9pm", "9pm Eastern Time"),
        TimeLabel("10pm", "10pm", "10pm Eastern Time"),
        TimeLabel("11pm", "11pm", "11pm Eastern Time"),
        TimeLabel("12am", "12am", "12am Eastern Time"),
        TimeLabel("1am", "1am", "1am Eastern Time"),
        TimeLabel("2am", "2am", "2am Eastern Time"),
    ]


@patch("deps.functions.datetime")
def test_get_current_hour_eastern_time(mock_datetime):
    """Return the current hour in Eastern Time"""
    # Mock the current time in UTC (11:10am UTC)
    mock_utc_time = datetime(2024, 11, 25, 11, 10, 0, tzinfo=timezone.utc)

    # Convert to Eastern Time (US/Eastern)
    eastern = pytz.timezone("US/Eastern")
    mock_eastern_time = mock_utc_time.astimezone(eastern)

    # Set the mocked time to the Eastern Time
    mock_datetime.now.return_value = mock_eastern_time

    # Call the function
    result = get_current_hour_eastern()

    # Ensure that the mock datetime.now() was called exactly once
    mock_datetime.now.assert_called_once()

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result == "6am"


@patch("deps.functions.datetime")
def test_get_current_hour_eastern_time_plus_hour(mock_datetime):
    """Return the current hour in Eastern Time"""
    # Mock the current time in UTC (11:10am UTC)
    mock_utc_time = datetime(2024, 11, 25, 11, 10, 0, tzinfo=timezone.utc)

    # Convert to Eastern Time (US/Eastern)
    eastern = pytz.timezone("US/Eastern")
    mock_eastern_time = mock_utc_time.astimezone(eastern)

    # Set the mocked time to the Eastern Time
    mock_datetime.now.return_value = mock_eastern_time

    # Call the function
    result = get_current_hour_eastern(1)

    # Ensure that the mock datetime.now() was called exactly once
    mock_datetime.now.assert_called_once()

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result == "7am"


@patch("deps.functions.datetime")
def test_get_current_hour_eastern_time_plus_hour_double_digit(mock_datetime):
    """Return the current hour in Eastern Time"""
    # Mock the current time in UTC (11:10am UTC)
    mock_utc_time = datetime(2024, 11, 25, 20, 10, 0, tzinfo=timezone.utc)

    # Convert to Eastern Time (US/Eastern)
    eastern = pytz.timezone("US/Eastern")
    mock_eastern_time = mock_utc_time.astimezone(eastern)

    # Set the mocked time to the Eastern Time
    mock_datetime.now.return_value = mock_eastern_time

    # Call the function
    result = get_current_hour_eastern(1)

    # Ensure that the mock datetime.now() was called exactly once
    mock_datetime.now.assert_called_once()

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result == "4pm"


def test_get_sha():
    """Test to see if we can access the subprocess of git"""
    sha = get_sha()
    assert len(sha) > 8


@patch("deps.functions.date")
def test_daily_message(mock_date):
    """Test the construction of the daily message with emoji"""
    mock_date.today.return_value = datetime(2024, 11, 30)
    votes: Dict[str, List[SimpleUser]] = {
        "3pm": [SimpleUser("1", "user1", ":Copper:")],
        "4pm": [SimpleUser("2", "user2", ":Gold:"), SimpleUser("3", "user3", ":Silver:")],
        "5pm": [],
    }
    msg = get_daily_string_message(votes)
    assert (
        msg
        == f"{MSG_UNIQUE_STRING} today **Saturday, November 30, 2024**?\n\n**Schedule**\n3pm: :Copper:user1\n4pm: :Gold:user2,:Silver:user3\n5pm: -\n"
        + f"\n⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nYou can use `/{COMMAND_SCHEDULE_ADD}` to set recurrent day and hours or click the emoji corresponding to your time:"
    )


def test_profile_url():
    """Test the URL for the user profile"""
    url = get_url_user_profile_main("user1")
    assert url == "https://r6.tracker.network/r6siege/profile/uplay/user1"


def test_profile_overview_url():
    """Test the URL for the user profile overview"""
    url = get_url_user_profile_overview("user1")
    assert url == "https://r6.tracker.network/r6siege/profile/uplay/user1/overview"


def test_get_url_user_ranked_matches():
    """Test the URL for the user rank page"""
    url = get_url_user_ranked_matches("user1")
    assert url == "https://r6.tracker.network/r6siege/profile/uplay/user1/matches?playlist=ranked"


def test_get_url_user_ranked_matches_api():
    """Test the URL for the user rank API"""
    url = get_url_api_ranked_matches("user1")
    assert url == "https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/user1?gamemode=pvp_ranked"


def test_choices_items():
    """Assert the number of choices for time"""
    choices = get_time_choices()
    assert len(choices) == 12
    assert choices[0].value == "3pm"
    assert choices[0].name == "3pm"
    assert choices[11].value == "2am"
    assert choices[11].name == "2am"
