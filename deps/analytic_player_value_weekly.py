"""
Weekly player value leaderboard: an image posted every Saturday in the AI channel
with the top players active in the last 30 days, their current value, and how it
moved since the previous week.
"""

import io
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import discord
from PIL import Image, ImageDraw, ImageFont

from deps.analytic_activity_data_access import fetch_user_info_by_user_id_list
from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
from deps.analytic_player_value_data_access import data_access_fetch_all_user_ids_with_matches
from deps.analytic_player_value_functions import compute_value_time_decayed
from deps.data_access import data_access_get_ai_text_channel_id, data_access_get_channel
from deps.log import print_error_log, print_log
from deps.models import UserFullMatchStats

WEEKLY_VALUE_ACTIVE_DAYS = 30
WEEKLY_VALUE_TOP_COUNT = 30
WEEKLY_VALUE_DELTA_DAYS = 7

font_path = os.path.abspath("./fonts/Minecraft.ttf")
font_title = ImageFont.truetype(font_path, 24)
font_row = ImageFont.truetype(font_path, 18)

COLOR_BACKGROUND = (24, 26, 33)
COLOR_TITLE = (240, 240, 240)
COLOR_ROW = (220, 220, 220)
COLOR_ROW_ALTERNATE_BG = (33, 36, 45)
COLOR_GAIN = (80, 200, 120)
COLOR_LOSS = (230, 90, 90)
COLOR_NEUTRAL = (150, 150, 150)
COLOR_NEW = (90, 170, 230)


@dataclass
class WeeklyValueRow:
    """One displayed leaderboard entry"""

    rank: int  # Rank among ALL users, so displayed ranks can skip inactive users
    display_name: str
    value: float
    previous_value: Optional[float]  # None when the user had no history a week ago


def build_weekly_value_rows(
    matches_by_user: Dict[int, List[UserFullMatchStats]],
    display_names_by_id: Dict[int, str],
    now: datetime,
) -> List[WeeklyValueRow]:
    """
    Rank every user by their current value, then keep only the users active in
    the last 30 days (their global rank is preserved, so numbers can skip) and
    return the top entries with the change versus one week ago.
    """
    previous_cutoff = now - timedelta(days=WEEKLY_VALUE_DELTA_DAYS)
    active_cutoff = now - timedelta(days=WEEKLY_VALUE_ACTIVE_DAYS)

    computed = []
    for user_id, matches in matches_by_user.items():
        current = compute_value_time_decayed(matches, now)
        if current is None or current.last_match_timestamp is None:
            continue
        previous_matches = [m for m in matches if m.match_timestamp <= previous_cutoff]
        previous = compute_value_time_decayed(previous_matches, previous_cutoff)
        computed.append((user_id, current, previous))

    computed.sort(key=lambda entry: entry[1].value, reverse=True)

    rows: List[WeeklyValueRow] = []
    for rank, (user_id, current, previous) in enumerate(computed, start=1):
        if current.last_match_timestamp is None or current.last_match_timestamp < active_cutoff:
            continue  # Inactive users keep their rank number but are not displayed
        rows.append(
            WeeklyValueRow(
                rank=rank,
                display_name=display_names_by_id.get(user_id, str(user_id)),
                value=current.value,
                previous_value=previous.value if previous is not None else None,
            )
        )
        if len(rows) >= WEEKLY_VALUE_TOP_COUNT:
            break
    return rows


def generate_weekly_value_image(rows: List[WeeklyValueRow], now: datetime) -> bytes:
    """Render the leaderboard rows into a PNG image"""
    width = 640
    header_height = 70
    row_height = 30
    margin = 16
    height = header_height + row_height * len(rows) + margin

    image = Image.new("RGB", (width, height), COLOR_BACKGROUND)
    draw = ImageDraw.Draw(image)
    draw.text((margin, 14), "Player Value - Top 30", font=font_title, fill=COLOR_TITLE)
    draw.text(
        (margin, 44),
        f"Active last {WEEKLY_VALUE_ACTIVE_DAYS} days - {now.strftime('%Y-%m-%d')}",
        font=font_row,
        fill=COLOR_NEUTRAL,
    )

    for index, row in enumerate(rows):
        top = header_height + index * row_height
        if index % 2 == 1:
            draw.rectangle([(0, top), (width, top + row_height)], fill=COLOR_ROW_ALTERNATE_BG)
        draw.text((margin, top + 6), f"#{row.rank}", font=font_row, fill=COLOR_NEUTRAL)
        draw.text((margin + 60, top + 6), row.display_name[:24], font=font_row, fill=COLOR_ROW)
        draw.text((430, top + 6), f"{row.value:.1f}", font=font_row, fill=COLOR_ROW)
        if row.previous_value is None:
            draw.text((520, top + 6), "new", font=font_row, fill=COLOR_NEW)
        else:
            delta = row.value - row.previous_value
            if delta >= 0.05:
                draw.text((520, top + 6), f"+{delta:.1f}", font=font_row, fill=COLOR_GAIN)
            elif delta <= -0.05:
                draw.text((520, top + 6), f"{delta:.1f}", font=font_row, fill=COLOR_LOSS)
            else:
                draw.text((520, top + 6), "=", font=font_row, fill=COLOR_NEUTRAL)

    with io.BytesIO() as buffer:
        image.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


async def send_weekly_player_value_to_a_guild(guild: discord.Guild, now: datetime) -> None:
    """Build and post the weekly player value leaderboard image in the AI channel"""
    channel_id = await data_access_get_ai_text_channel_id(guild.id)
    if channel_id is None:
        print_error_log(
            f"send_weekly_player_value_to_a_guild: AI text channel not set for guild {guild.name}. Skipping."
        )
        return
    channel = await data_access_get_channel(channel_id)
    if channel is None:
        print_error_log(f"send_weekly_player_value_to_a_guild: Channel not found for guild {guild.name}. Skipping.")
        return

    user_ids = data_access_fetch_all_user_ids_with_matches()
    matches_by_user = data_access_fetch_user_matches_in_time_range(user_ids, None, None)
    users_info = fetch_user_info_by_user_id_list(user_ids)
    display_names_by_id = {user.id: user.display_name for user in users_info if user is not None}

    rows = build_weekly_value_rows(matches_by_user, display_names_by_id, now)
    if not rows:
        print_log(f"send_weekly_player_value_to_a_guild: No active user to show for guild {guild.name}. Skipping.")
        return

    image_bytes = generate_weekly_value_image(rows, now)
    file = discord.File(fp=io.BytesIO(image_bytes), filename="player_values.png")
    await channel.send(
        content="📊 **Weekly Player Value** — top 30 players active in the last 30 days, "
        "with the change since last week. Values update every night based on your ranked matches.",
        file=file,
    )
