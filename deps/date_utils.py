from datetime import datetime, timezone


def is_today(date_time):
    """ Get today's date and check with UTC if the date is today """
    today_utc = datetime.now(timezone.utc).date()
    date_time_utc = date_time.date()

    return date_time_utc == today_utc
