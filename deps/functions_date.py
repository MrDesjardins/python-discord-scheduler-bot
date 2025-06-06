"""
Function related to date manipulation
"""

from datetime import datetime, timezone
from typing import Optional, Union
import pytz


def get_now_eastern() -> datetime:
    """
    Returns the current hour in Eastern Time. In the format 3am or 3pm.
    """
    eastern = pytz.timezone("US/Eastern")
    # Get the current time in Eastern timezone once
    current_time_eastern = datetime.now(eastern)

    return current_time_eastern


def get_current_hour_eastern(add_hour: Optional[int] = None) -> str:
    """
    Returns the current hour in Eastern Time. In the format 3am or 3pm.
    """

    # Get the current time in Eastern timezone once
    current_time_eastern = get_now_eastern()

    if add_hour:
        # Adjust the hour by the add_hour parameter
        current_time_eastern = current_time_eastern.replace(hour=current_time_eastern.hour + add_hour)

    # Strip leading zero by converting the hour to an integer before formatting
    return (
        current_time_eastern.strftime("%-I%p").lower()
        if hasattr(current_time_eastern, "strftime")
        else current_time_eastern.strftime("%I%p").lstrip("0").lower()
    )


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is in UTC.
    - If naive, assume it's in the local timezone and convert to UTC.
    - If timezone-aware, convert to UTC if needed.
    """
    if dt.tzinfo is None:
        # Assume naive datetime is in the local timezone
        local_dt = dt.replace(tzinfo=timezone.utc).astimezone()
        return local_dt.astimezone(timezone.utc)
    # Convert to UTC if not already in UTC
    return dt.astimezone(timezone.utc)


def convert_to_datetime(date_str: Optional[str]) -> Union[datetime, None]:
    """Convert a date string to a timezone-aware datetime object (UTC)"""
    if not date_str:  # Handle None or empty string
        return None
    # Parse the date string and assume it's in UTC if no timezone is provided
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)  # Make the datetime UTC-aware
    return dt


def is_today(date_time: datetime) -> bool:
    """Check if the given datetime is on the same day as today in Eastern Time"""
    # Define the Eastern timezone
    eastern_tz = pytz.timezone("US/Eastern")

    # Convert the provided datetime to Eastern Time
    # Assuming date_time is in UTC, adjust accordingly if it's not
    date_time_eastern = date_time.astimezone(eastern_tz)

    # Get today's date in Eastern Time
    eastern_today = datetime.now(eastern_tz).date()

    # Compare the date portion
    return date_time_eastern.date() == eastern_today


def iso_to_gregorian(year: int, week: int) -> datetime:
    """Convert ISO year and week to the starting date of that ISO week (Monday) in UTC."""
    dt = datetime.strptime(f"{year}-W{week}-1", "%G-W%V-%u")
    return dt.replace(tzinfo=timezone.utc)
