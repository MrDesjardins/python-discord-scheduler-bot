"""Shared day-range presets for the analytics visualizations.

`botadmin.py` (local terminal) and the `/modplot` Discord command must resolve a
preset to the same `from_day`/`to_day` offsets, otherwise the same label shows a
different window depending on where it is started. Keep the presets and the
resolution logic here so both entry points stay identical.
"""

from datetime import date, datetime, timedelta
from typing import Optional

PERIOD_LABELS: tuple[str, ...] = (
    "Last 30 days",
    "Current month",
    "Last month",
    "Last 3 months",
    "Since beginning of the year",
    "Since September 21, 2024",
)

PERIOD_LAST_30_DAYS = 0
PERIOD_CURRENT_MONTH = 1
PERIOD_LAST_MONTH = 2
PERIOD_LAST_3_MONTHS = 3
PERIOD_YEAR_TO_DATE = 4
PERIOD_SINCE_BOT_START = 5


def get_from_to_days(period_index: int) -> tuple[int, int]:  # pylint: disable=too-many-return-statements
    """Resolve a preset index to a `(from_day, to_day)` pair.

    `from_day` counts backwards from today, `to_day` is normally 0 (today). The
    indices are the historical order of the botadmin menu; the Discord command
    stores the same index so both produce the same window.
    """
    if period_index == PERIOD_LAST_30_DAYS:
        return (30, 0)
    if period_index == PERIOD_CURRENT_MONTH:
        # Calendar month to date (not "last N days where N = day-of-month")
        today = datetime.now().date()
        first_of_month = date(today.year, today.month, 1)
        return (max((today - first_of_month).days, 1), 0)
    if period_index == PERIOD_LAST_MONTH:
        current_date = datetime.now()
        first_day_of_this_month = datetime(current_date.year, current_date.month, 1)
        last_month_last_day = first_day_of_this_month - timedelta(days=1)
        last_month_first_day = datetime(last_month_last_day.year, last_month_last_day.month, 1)
        return (
            (current_date - last_month_first_day).days,
            (current_date - last_month_last_day).days,
        )
    if period_index == PERIOD_LAST_3_MONTHS:
        current_date = datetime.now()
        three_months_ago = current_date - timedelta(days=90)
        first_day_three_months_ago = datetime(three_months_ago.year, three_months_ago.month, 1)
        return ((current_date - first_day_three_months_ago).days, 0)
    if period_index == PERIOD_YEAR_TO_DATE:
        return ((datetime.now() - datetime(datetime.now().year, 1, 1)).days, 0)
    if period_index == PERIOD_SINCE_BOT_START:
        return ((datetime.now() - datetime(2024, 9, 21)).days, 0)
    return (0, 0)


def resolve_day_range(
    period_index: int,
    from_day_ago: Optional[int] = None,
    to_day_ago: Optional[int] = None,
) -> tuple[int, int]:
    """Resolve a preset, then apply the optional explicit day offsets.

    Either offset overrides its preset counterpart, so `/modplot` can offer both a
    simple preset list and a custom range without a second command.
    """
    from_day, to_day = get_from_to_days(period_index)
    if from_day_ago is not None:
        from_day = from_day_ago
    if to_day_ago is not None:
        to_day = to_day_ago
    if from_day < 0 or to_day < 0:
        raise ValueError("Days ago must be zero or positive.")
    if from_day < to_day:
        raise ValueError("The start (from_day_ago) must be older than the end (to_day_ago).")
    return (from_day, to_day)
