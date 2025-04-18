"""Unit tests for the analytic_gatherer module"""

from datetime import datetime
from typing import Dict, List, Tuple, Union
from unittest.mock import patch
from pandas import Index, Series
import pandas.testing as pdt
import pytest
from deps.analytic_models import UserInfoWithCount
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT
from deps.data_access_data_class import UserActivity, UserInfo
from deps.analytic_functions import (
    calculate_overlap,
    calculate_user_connections,
    compute_users_weights,
    computer_users_voice_in_out,
    compute_users_voice_channel_time_sec,
    times_by_months,
    user_times_by_month,
    users_by_weekday,
    users_last_played_over_day,
)

from tests.mock_model import mock_user1, mock_user2, mock_user3


def test_full_overlap() -> None:
    """Test full overlap between two time intervals"""
    start1 = datetime(2024, 9, 20, 13, 18, 0, 6318)
    end1 = datetime(2024, 9, 20, 13, 20, 0, 6318)
    start2 = datetime(2024, 9, 20, 13, 18, 0, 6318)
    end2 = datetime(2024, 9, 20, 13, 20, 0, 6318)
    result = calculate_overlap(start1, end1, start2, end2)
    assert result == 120


def test_no_overlap() -> None:
    """Test no overlap between two time intervals"""
    start1 = datetime(2024, 9, 20, 13, 18, 0, 6318)
    end1 = datetime(2024, 9, 20, 13, 20, 0, 6318)
    start2 = datetime(2024, 9, 20, 14, 18, 0, 6318)
    end2 = datetime(2024, 9, 20, 14, 20, 0, 6318)
    result = calculate_overlap(start1, end1, start2, end2)
    assert result == 0


def test_partial_overlap() -> None:
    """Test partial overlap between two time intervals"""
    start1 = datetime(2024, 9, 20, 13, 0, 0, 6318)
    end1 = datetime(2024, 9, 20, 13, 0, 20, 6318)
    start2 = datetime(2024, 9, 20, 13, 0, 10, 6318)
    end2 = datetime(2024, 9, 20, 13, 0, 50, 6318)
    result = calculate_overlap(start1, end1, start2, end2)
    assert result == 10


def test_two_users_connection_with_single_connect_disconnect() -> None:
    """Test two users connection with single connect and disconnect"""
    activity_data = [
        UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=2, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:1.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:3.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=2, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:4.6318", guild_id=1),
    ]
    result = calculate_user_connections(activity_data)
    assert result == {
        1: {
            1: [[datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 18, 3, 631800)]],
            2: [[datetime(2024, 9, 20, 13, 18, 1, 631800), datetime(2024, 9, 20, 13, 18, 4, 631800)]],
        }
    }


def test_two_users_connection_with_many_connect_disconnect() -> None:
    """Test two users connection with many connect and disconnect"""
    activity_data = [
        UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=2, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:1.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:3.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=2, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:18:4.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:20:1.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:20:10.6318", guild_id=1),
    ]
    result = calculate_user_connections(activity_data)
    assert result == {
        1: {
            1: [
                [datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 18, 3, 631800)],
                [datetime(2024, 9, 20, 13, 20, 1, 631800), datetime(2024, 9, 20, 13, 20, 10, 631800)],
            ],
            2: [[datetime(2024, 9, 20, 13, 18, 1, 631800), datetime(2024, 9, 20, 13, 18, 4, 631800)]],
        }
    }


def test_user_connect_in_two_different_channels() -> None:
    """Test user connect in two different channels"""
    activity_data = [
        UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
        UserActivity(channel_id=1, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:19:0.6318", guild_id=1),
        UserActivity(channel_id=2, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:28:3.6318", guild_id=1),
        UserActivity(channel_id=2, user_id=1, event=EVENT_DISCONNECT, timestamp="2024-09-20 13:29:3.6318", guild_id=1),
    ]

    result = calculate_user_connections(activity_data)
    assert result == {
        1: {
            1: [
                [datetime(2024, 9, 20, 13, 18, 0, 631800), datetime(2024, 9, 20, 13, 19, 0, 631800)],
            ],
        },
        2: {
            1: [
                [datetime(2024, 9, 20, 13, 28, 3, 631800), datetime(2024, 9, 20, 13, 29, 3, 631800)],
            ],
        },
    }


def test_user_connect_never_disconnected() -> None:
    """Test user connect but never disconnected"""
    activity_data = [
        UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
    ]
    result = calculate_user_connections(activity_data)
    assert result == {
        1: {
            1: [
                [datetime(2024, 9, 20, 13, 18, 0, 631800), None],
            ],
        }
    }


def test_user_connect_disconnected_two_different_channels() -> None:
    """Test user connect and disconnected in two different channels"""
    activity_data = [
        UserActivity(channel_id=1, user_id=1, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
        UserActivity(channel_id=2, user_id=2, event=EVENT_CONNECT, timestamp="2024-09-20 13:18:0.6318", guild_id=1),
    ]
    result = calculate_user_connections(activity_data)
    assert result == {
        1: {
            1: [
                [datetime(2024, 9, 20, 13, 18, 0, 631800), None],
            ],
        },
        2: {
            2: [
                [datetime(2024, 9, 20, 13, 18, 0, 631800), None],
            ],
        },
    }


@pytest.mark.parametrize(
    "activity_data_weight, expected_result_weight",
    [
        (  # Test two users in the same channel with single overlap
            [
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
                UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
                UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            ],
            {(1, 2, 100): 300},
        ),
        (  # Test two users in the same channel with many overlap
            [
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:30:0.6318", 1),
                UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
                UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:06:0.6318", 1),
                UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:15:0.6318", 1),
                UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:16:0.6318", 1),
            ],
            {(1, 2, 100): 120},
        ),
        (  # Test two users in different channels with no overlap
            [
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:30:0.6318", 1),
                UserActivity(2, 200, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
                UserActivity(2, 200, EVENT_DISCONNECT, "2024-09-20 13:06:0.6318", 1),
            ],
            {},
        ),
    ],
)
def test_compute_users_weights(activity_data_weight, expected_result_weight) -> None:
    """Test compute_users_weights function with different scenarios"""
    result = compute_users_weights(activity_data_weight)
    assert result == expected_result_weight


@pytest.mark.parametrize(
    "activity_data, expected_result",
    [
        (  # est single user in a single channel
            [
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:15:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:20:0.6318", 1),
            ],
            {
                1: [
                    (
                        datetime(2024, 9, 20, 13, 0, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                    (
                        datetime(2024, 9, 20, 13, 15, 0, 631800),
                        datetime(2024, 9, 20, 13, 20, 0, 631800),
                    ),
                ]
            },
        ),
        (  # Test many users in a single channel
            [
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
                UserActivity(2, 100, EVENT_CONNECT, "2024-09-20 13:05:0.6318", 1),
                UserActivity(2, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
            ],
            {
                1: [
                    (
                        datetime(2024, 9, 20, 13, 0, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                ],
                2: [
                    (
                        datetime(2024, 9, 20, 13, 5, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                ],
            },
        ),
        (  # Test single user in many channels
            [
                UserActivity(1, 100, EVENT_CONNECT, "2024-09-20 13:00:0.6318", 1),
                UserActivity(1, 100, EVENT_DISCONNECT, "2024-09-20 13:10:0.6318", 1),
                UserActivity(1, 200, EVENT_CONNECT, "2024-09-20 13:15:0.6318", 1),
                UserActivity(1, 200, EVENT_DISCONNECT, "2024-09-20 13:20:0.6318", 1),
            ],
            {
                1: [
                    (
                        datetime(2024, 9, 20, 13, 0, 0, 631800),
                        datetime(2024, 9, 20, 13, 10, 0, 631800),
                    ),
                    (
                        datetime(2024, 9, 20, 13, 15, 0, 631800),
                        datetime(2024, 9, 20, 13, 20, 0, 631800),
                    ),
                ]
            },
        ),
    ],
)
def test_computer_users_voice_in_out(activity_data, expected_result) -> None:
    """Test computer_users_voice_in_out function with different scenarios"""
    result = computer_users_voice_in_out(activity_data)
    assert result == expected_result


def test_single_user() -> None:
    """Test single user in a single channel"""
    users_in_out: Dict[int, List[Tuple[datetime, Union[datetime, None]]]] = {
        1: [
            (
                datetime(2024, 9, 20, 13, 0, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 20, 13, 15, 0, 631800),
                datetime(2024, 9, 20, 13, 20, 0, 631800),
            ),
        ]
    }
    result = compute_users_voice_channel_time_sec(users_in_out)
    assert result == {1: 900}


def test_many_users() -> None:
    """Test many users in a single channel"""
    users_in_out: Dict[int, List[Tuple[datetime, Union[datetime, None]]]] = {
        1: [
            (
                datetime(2024, 9, 20, 13, 0, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 20, 13, 15, 0, 631800),
                datetime(2024, 9, 20, 13, 20, 0, 631800),
            ),
        ],
        2: [
            (
                datetime(2024, 9, 20, 13, 5, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
        ],
    }
    result = compute_users_voice_channel_time_sec(users_in_out)
    assert result == {1: 900, 2: 300}


def test_single_user_without_disconnect() -> None:
    """Test single user in a single channel without disconnect"""
    users_in_out = {
        1: [
            (
                datetime(2024, 9, 20, 13, 0, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 20, 13, 15, 0, 631800),
                None,
            ),
        ]
    }
    result = compute_users_voice_channel_time_sec(users_in_out)
    assert result == {1: 600}


@pytest.fixture
def mock_datetime():
    """
    Mock date time for every tests
    """
    with patch("deps.analytic_functions.datetime") as mock:
        yield mock


def test_single_user_inactive(mock_datetime) -> None:
    """Test single user inactive for over a day"""
    mock_datetime.now.return_value = datetime(2024, 9, 22, 13, 30, 45)
    users_in_out: Dict[int, List[Tuple[datetime, Union[datetime, None]]]] = {
        1: [
            (
                datetime(2024, 9, 20, 13, 0, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 20, 13, 15, 0, 631800),
                datetime(2024, 9, 20, 13, 20, 0, 631800),
            ),
        ]
    }
    result = users_last_played_over_day(users_in_out)
    assert result == {1: 2}


def test_single_user_active(mock_datetime) -> None:
    """Test single user active"""
    mock_datetime.now.return_value = datetime(2024, 9, 21, 1, 30, 45)
    users_in_out: Dict[int, List[Tuple[datetime, Union[datetime, None]]]] = {
        1: [
            (
                datetime(2024, 9, 20, 13, 0, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 20, 13, 15, 0, 631800),
                datetime(2024, 9, 20, 13, 20, 0, 631800),
            ),
        ]
    }
    result = users_last_played_over_day(users_in_out)
    assert not result


def test_single_user_active_data_unordered_recent_last(mock_datetime) -> None:
    """Test single user active data unordered with recent last"""
    mock_datetime.now.return_value = datetime(2024, 9, 21, 1, 30, 45)
    users_in_out: Dict[int, List[Tuple[datetime, Union[datetime, None]]]] = {
        1: [
            (
                datetime(2024, 9, 10, 13, 0, 0, 631800),
                datetime(2024, 9, 10, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 20, 13, 15, 0, 631800),
                datetime(2024, 9, 20, 13, 20, 0, 631800),
            ),
        ]
    }
    result = users_last_played_over_day(users_in_out)
    assert not result


def test_single_user_active_data_unordered_recent_first(mock_datetime) -> None:
    """Test single user active data unordered with recent first"""
    mock_datetime.now.return_value = datetime(2024, 9, 21, 1, 30, 45)
    users_in_out: Dict[int, List[Tuple[datetime, Union[datetime, None]]]] = {
        1: [
            (
                datetime(2024, 9, 20, 13, 0, 0, 631800),
                datetime(2024, 9, 20, 13, 10, 0, 631800),
            ),
            (
                datetime(2024, 9, 10, 13, 15, 0, 631800),
                datetime(2024, 9, 10, 13, 20, 0, 631800),
            ),
        ]
    }
    result = users_last_played_over_day(users_in_out)
    assert not result


def test_many_users_same_day() -> None:
    """Test many users playing on the same day"""
    activity_data = [
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-09 13:00:00.6318", 1),
        UserActivity(2, 100, EVENT_CONNECT, "2024-10-09 13:00:00.6318", 1),
    ]
    user_id_names: Dict[int, UserInfo] = {
        1: mock_user1,
        2: mock_user2,
    }
    result = users_by_weekday(activity_data, user_id_names)
    expected_result = {
        2: [
            UserInfoWithCount(
                user=mock_user1,
                count=1,
            ),
            UserInfoWithCount(
                user=mock_user2,
                count=1,
            ),
        ]
    }
    assert result == expected_result


def test_single_user_many_weekday() -> None:
    """Test single user playing on many days"""
    activity_data = [
        UserActivity(2, 100, EVENT_CONNECT, "2024-10-09 13:00:00.6318", 1),  # Wednesday = 2
        UserActivity(3, 100, EVENT_CONNECT, "2024-10-10 13:00:00.6318", 1),  # Thursday = 3
        UserActivity(3, 100, EVENT_CONNECT, "2024-10-17 13:00:00.6318", 1),  # Thursday = 3
    ]
    user_id_names: Dict[int, UserInfo] = {
        1: mock_user1,
        2: mock_user2,
        3: mock_user3,
    }
    result = users_by_weekday(activity_data, user_id_names)
    expected_result = {
        2: [
            UserInfoWithCount(
                user=mock_user2,
                count=1,
            )
        ],
        3: [
            UserInfoWithCount(
                user=mock_user3,
                count=2,
            ),
        ],
    }
    assert result == expected_result


def test_many_user_many_weekday() -> None:
    """Test many users playing on many days"""
    activity_data = [
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-09 13:00:00.6318", 1),
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-10 13:00:00.6318", 1),
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-17 13:00:00.6318", 1),
        UserActivity(2, 100, EVENT_CONNECT, "2024-10-17 13:00:00.6318", 1),
    ]
    user_id_names: Dict[int, UserInfo] = {
        1: mock_user1,
        2: mock_user2,
    }
    result = users_by_weekday(activity_data, user_id_names)
    expected_result = {
        2: [
            UserInfoWithCount(
                user=mock_user1,
                count=1,
            )
        ],
        3: [
            UserInfoWithCount(
                user=mock_user1,
                count=2,
            ),
            UserInfoWithCount(
                user=mock_user2,
                count=1,
            ),
        ],
    }
    assert result == expected_result


def test_single_month_two_users() -> None:
    """Test single month with two users"""
    activity_data = [
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-09 13:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_DISCONNECT, "2024-10-09 14:00:00+00:00", 1),
        UserActivity(2, 100, EVENT_CONNECT, "2024-10-09 13:00:00+00:00", 1),
        UserActivity(2, 100, EVENT_DISCONNECT, "2024-10-09 18:00:00+00:00", 1),
    ]
    result = user_times_by_month(activity_data)
    expected_result = {
        "2024-10": {
            1: 3600,
            2: 18000,
        }
    }
    assert result == expected_result


def test_multiple_month_two_users() -> None:
    """Test multiple months with two users"""
    activity_data = [
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-09 13:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_DISCONNECT, "2024-10-09 14:00:00+00:00", 1),
        UserActivity(2, 100, EVENT_CONNECT, "2024-10-09 13:00:00+00:00", 1),
        UserActivity(2, 100, EVENT_DISCONNECT, "2024-10-09 18:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_CONNECT, "2024-11-09 13:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_DISCONNECT, "2024-11-09 15:00:00+00:00", 1),
    ]
    result = user_times_by_month(activity_data)
    expected_result = {
        "2024-10": {
            1: 3600,
            2: 18000,
        },
        "2024-11": {
            1: 7200,
        },
    }
    assert result == expected_result


def test_times_by_months() -> None:
    """Test multiple months with two users"""
    activity_data = [
        UserActivity(1, 100, EVENT_CONNECT, "2024-10-09 13:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_DISCONNECT, "2024-10-09 14:00:00+00:00", 1),
        UserActivity(2, 100, EVENT_CONNECT, "2024-10-09 13:00:00+00:00", 1),
        UserActivity(2, 100, EVENT_DISCONNECT, "2024-10-09 18:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_CONNECT, "2024-11-09 13:00:00+00:00", 1),
        UserActivity(1, 100, EVENT_DISCONNECT, "2024-11-09 15:00:00+00:00", 1),
    ]
    result = times_by_months(activity_data)
    expected_result = Series(
        data=[6, 2],
        index=Index(data=["2024-10", "2024-11"], dtype="object", name="month"),
        name="duration",
        dtype="float64",  # Explicitly set data dtype
    )
    pdt.assert_series_equal(result, expected_result)
