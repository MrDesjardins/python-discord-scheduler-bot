from datetime import datetime
import pytz


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
