""" Test Functions """

from datetime import datetime, timezone
from unittest.mock import patch
import pytz
from deps.functions_date import convert_to_datetime, ensure_utc, get_current_hour_eastern, get_now_eastern


@patch("deps.functions_date.datetime")
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


@patch("deps.functions_date.datetime")
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


@patch("deps.functions_date.datetime")
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


@patch("deps.functions_date.datetime")
def test_get_now_eastern(mock_datetime):
    """Return the current hour in Eastern Time"""

    # Set the mocked time to the Eastern Time
    mock_datetime.now.return_value = datetime(2024, 11, 25, 20, 10, 0, tzinfo=pytz.timezone("US/Eastern"))

    # Call the function
    result = get_now_eastern()

    # Ensure that the mock datetime.now() was called exactly once
    mock_datetime.now.assert_called_once()

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result.hour == 20
    assert result.minute == 10


def test_ensure_utc_when_not_utc():
    """Return the current hour in Eastern Time"""

    # Set the mocked time to the Eastern Time
    dt = datetime(2024, 11, 25, 20, 10, 0, tzinfo=pytz.timezone("US/Eastern"))

    # Call the function
    result = ensure_utc(dt)

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result.tzinfo == timezone.utc


def test_ensure_utc_when_utc():
    """Return the current hour in Eastern Time"""

    # Set the mocked time to the Eastern Time
    dt = datetime(2024, 11, 25, 20, 10, 0, 0, timezone.utc)

    # Call the function
    result = ensure_utc(dt)

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result.tzinfo == timezone.utc


def test_ensure_utc_when_time_zone_none():
    """Return the current hour in Eastern Time"""

    # Set the mocked time without timezone
    dt = datetime(2024, 11, 25, 20, 10, 0, tzinfo=None)
    # Call the function
    result = ensure_utc(dt)

    # Assert the result is as expected (6am Eastern Time from 11:10am UTC)
    assert result.tzinfo == timezone.utc


def test_convert_to_datetime_when_null():
    """
    Convert to date when input is null
    """
    result = convert_to_datetime(None)
    assert result is None


def test_convert_to_datetime_when_no_time_zone():
    """
    Convert to date when a datetime without timezone
    """
    dt = datetime(2024, 11, 25, 20, 10, 0, tzinfo=None).isoformat()
    result = convert_to_datetime(dt)
    assert result.tzinfo == timezone.utc


def test_convert_to_datetime_when_time_zone_utc():
    """
    Convert to date when a datetime without timezone
    """
    dt = datetime(2024, 11, 25, 20, 10, 0, tzinfo=timezone.utc).isoformat()
    result = convert_to_datetime(dt)
    assert result.tzinfo == timezone.utc


def test_convert_to_datetime_when_time_zone_east():
    """
    Convert to date when a datetime without timezone
    """
    dt = datetime(2024, 11, 25, 20, 10, 0, tzinfo=pytz.timezone("US/Eastern")).isoformat()
    result = convert_to_datetime(dt)
    assert isinstance(result, datetime)
