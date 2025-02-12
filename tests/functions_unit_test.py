""" Test Functions """

from datetime import datetime, timezone
from unittest.mock import patch
from deps.functions_model import get_empty_votes, get_supported_time_time_label
from deps.functions import (
    get_rotated_number_from_current_day,
    get_sha,
    get_time_choices,
    get_url_user_profile_main,
    get_url_user_profile_overview,
    get_url_user_ranked_matches,
    get_url_api_ranked_matches,
    most_common,
)
from deps.models import TimeLabel
import deps.functions


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
        "1pm": [],
        "2pm": [],
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
        "3am": [],
    }


def test_get_supported_time_time_label():
    """Return a list of TimeLabel objects that represent the supported times"""
    result = get_supported_time_time_label()
    assert result == [
        TimeLabel("1pm", "3pm", "1pm Eastern Time"),
        TimeLabel("2pm", "3pm", "2pm Eastern Time"),
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
        TimeLabel("3am", "2am", "3am Eastern Time"),
    ]


def test_get_sha():
    """Test to see if we can access the subprocess of git"""
    sha = get_sha()
    assert len(sha) > 8


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


def test_get_url_user_ranked_matches_api_with_name_with_dot():
    """Test the URL for the user rank API"""
    url = get_url_api_ranked_matches("GuyHero.")
    assert url == "https://api.tracker.gg/api/v2/r6siege/standard/matches/uplay/GuyHero.?gamemode=pvp_ranked"


def test_choices_items():
    """Assert the number of choices for time"""
    choices = get_time_choices()
    assert len(choices) == 15
    assert choices[0].value == "1pm"
    assert choices[0].name == "1pm"
    assert choices[14].value == "3am"
    assert choices[14].name == "3am"


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
def test_get_rotated_number_from_current_day_1(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(1)
    assert result == 0
    result = get_rotated_number_from_current_day(5)
    assert result == 0
    result = get_rotated_number_from_current_day(12)
    assert result == 0


@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
def test_get_rotated_number_from_current_day_2(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 10, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(1)
    assert result == 0
    result = get_rotated_number_from_current_day(5)
    assert result == 4
    result = get_rotated_number_from_current_day(6)
    assert result == 3
    result = get_rotated_number_from_current_day(12)
    assert result == 9

@patch.object(deps.functions, deps.functions.get_now_eastern.__name__)
def test_get_rotated_number_from_current_day_3(mock_get_now_eastern):
    """Test how the number rotates based on the current day"""
    mock_get_now_eastern.return_value = datetime(2024, 1, 1, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 0
    mock_get_now_eastern.return_value = datetime(2024, 1, 2, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 1
    mock_get_now_eastern.return_value = datetime(2024, 1, 3, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 2
    mock_get_now_eastern.return_value = datetime(2024, 1, 4, 10, 0, 0, 6318, timezone.utc)
    result = get_rotated_number_from_current_day(3)
    assert result == 0