"""
Streak Functions

Business logic for announcing streak milestones in a guild's main text channel.
Called once per day (late evening) after users have had a full day to play.
"""

from datetime import date

import discord

from deps.data_access import data_access_get_ai_text_channel_id, data_access_get_channel
from deps.log import print_error_log, print_log
from deps.streak_data_access import (
    STREAK_MILESTONES,
    compute_current_streak,
    fetch_distinct_play_dates,
    fetch_user_ids_active_on_date,
)

# Messages shown in the channel when a user hits a milestone streak.
# Only these exact streak lengths trigger an announcement.
_MILESTONE_MESSAGES = {
    3: "**{name}** is on a **3-day streak**! Getting warmed up.",
    7: "**{name}** is on a **7-day streak**! Solid dedication.",
    14: "**{name}** is on a **14-day streak**! True grinder.",
    30: "**{name}** is on a **30-day streak**! Absolute legend.",
}


async def announce_streak_milestones_for_guild(guild: discord.Guild) -> None:
    """
    Check every user who was active today in this guild.
    If their current streak lands exactly on a milestone, post a message
    in the guild's main text channel.
    """
    channel_id = await data_access_get_ai_text_channel_id(guild.id)
    if channel_id is None:
        return

    channel = await data_access_get_channel(channel_id)
    if channel is None:
        return

    today = date.today()
    user_ids_today = fetch_user_ids_active_on_date(guild.id, today)

    milestone_lines: list[str] = []
    for user_id in user_ids_today:
        play_dates = fetch_distinct_play_dates(user_id, guild.id)
        streak = compute_current_streak(play_dates)

        if streak not in STREAK_MILESTONES:
            continue

        member = guild.get_member(user_id)
        name = member.display_name if member else str(user_id)
        milestone_lines.append(_MILESTONE_MESSAGES[streak].format(name=name))
        print_log(f"announce_streak_milestones_for_guild: {name} hit a {streak}-day streak in {guild.name}")

    if not milestone_lines:
        return

    try:
        await channel.send(content="\n".join(milestone_lines))
    except discord.HTTPException as e:
        print_error_log(f"announce_streak_milestones_for_guild: Failed to send milestone message in {guild.name}: {e}")
