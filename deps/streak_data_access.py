"""
Streak Data Access

Functions to query user play days from the user_activity table.
A "play day" is any UTC calendar date where a user had at least one voice
'connect' event in a guild.
A "streak" is the number of consecutive play days ending on today or yesterday.
"""

from datetime import date, timedelta

from deps.system_database import database_manager

# Streak lengths that trigger a public milestone announcement.
STREAK_MILESTONES = {3, 7, 14, 30}


def fetch_distinct_play_dates(user_id: int, guild_id: int) -> list[date]:
    """
    Return all distinct UTC calendar dates the user had at least one voice
    connect event in the guild, sorted newest first.
    """
    rows = (
        database_manager.get_cursor()
        .execute(
            """
            SELECT DISTINCT DATE(timestamp) AS play_date
            FROM user_activity
            WHERE user_id = ? AND guild_id = ? AND event = 'connect'
            ORDER BY play_date DESC
            """,
            (user_id, guild_id),
        )
        .fetchall()
    )
    return [date.fromisoformat(row[0]) for row in rows]


def compute_current_streak(play_dates: list[date]) -> int:
    """
    Given play dates sorted newest-first, return the length of the consecutive
    streak ending on today or yesterday.

    Returns 0 if the user has not played recently enough to have an active streak.
    The streak is "active" only when the most recent play day is today or yesterday —
    missing a full calendar day resets it to 0.
    """
    if not play_dates:
        return 0

    today = date.today()
    most_recent = play_dates[0]

    # If the user last played more than one day ago, the streak is broken.
    if most_recent < today - timedelta(days=1):
        return 0

    streak = 1
    for i in range(1, len(play_dates)):
        # Each date in the list must be exactly one day before the previous one.
        if play_dates[i] == play_dates[i - 1] - timedelta(days=1):
            streak += 1
        else:
            break

    return streak


def fetch_user_ids_active_on_date(guild_id: int, target_date: date) -> list[int]:
    """
    Return user IDs that had at least one voice connect event in the guild
    on the given UTC calendar date.
    """
    rows = (
        database_manager.get_cursor()
        .execute(
            """
            SELECT DISTINCT user_id
            FROM user_activity
            WHERE guild_id = ? AND event = 'connect' AND DATE(timestamp) = ?
            """,
            (guild_id, target_date.isoformat()),
        )
        .fetchall()
    )
    return [row[0] for row in rows]
