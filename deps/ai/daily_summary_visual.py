"""
Rich rendering for the daily AI summary: a PIL banner image of the active roster
(avatar + MMR/rank/value) plus one Discord embed per user (avatar + AI-written recap).
"""

import io
from datetime import datetime
from typing import Any, List, Optional, Tuple

import discord
from PIL import Image, ImageDraw, ImageFont

from deps.ai.ai_functions import DailySummarySections
from deps.data_access_data_class import UserInfo
from deps.log import print_error_log
from deps.models import UserFullMatchStats
from deps.player_value_display import (
    PLAYER_VALUE_LEGEND,
    build_player_value_lookup,
    download_avatar,
    format_player_value_line,
)

MAX_EMBEDS_PER_MESSAGE = 10
MAX_BANNER_AVATARS = 15
BANNER_AVATARS_PER_ROW = 5

COLOR_WIN = 0x3BA55D
COLOR_LOSS = 0xED4245
COLOR_NEUTRAL = 0x99AAB5


def _resolve_member(guild: discord.Guild, user_id: int) -> Optional[discord.Member]:
    return guild.get_member(user_id)


def compute_user_win_loss(matches: List[UserFullMatchStats]) -> Tuple[int, int]:
    """(wins, losses) for one user's matches in the summarized window."""
    wins = sum(1 for match in matches if match.has_win)
    return wins, len(matches) - wins


async def build_daily_recap_banner(guild: discord.Guild, users: List[UserInfo]) -> Optional[bytes]:
    """
    Render one PNG: avatar + name + MMR/rank/value for each active user, capped at
    ``MAX_BANNER_AVATARS`` (a "+N more" note covers the rest), with a legend at the bottom.
    """
    if not users:
        return None

    shown_users = users[:MAX_BANNER_AVATARS]
    overflow_count = len(users) - len(shown_users)

    try:
        player_value_lookup = build_player_value_lookup()
    except Exception as e:
        print_error_log(f"build_daily_recap_banner: Failed to fetch player values: {e}")
        player_value_lookup = {}

    font_path = "./fonts/Minecraft.ttf"
    try:
        font_title: Any = ImageFont.truetype(font_path, 32)
        font_name: Any = ImageFont.truetype(font_path, 18)
        font_value: Any = ImageFont.truetype(font_path, 12)
        font_legend: Any = ImageFont.truetype(font_path, 13)
        font_overflow: Any = ImageFont.truetype(font_path, 16)
    except Exception as e:
        print_error_log(f"build_daily_recap_banner: Failed to load font: {e}")
        font_title = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_value = ImageFont.load_default()
        font_legend = ImageFont.load_default()
        font_overflow = ImageFont.load_default()

    avatar_size = 90
    col_spacing = 210
    row_spacing = 170
    num_rows = -(-len(shown_users) // BANNER_AVATARS_PER_ROW)  # Ceiling division
    grid_width = min(len(shown_users), BANNER_AVATARS_PER_ROW) * col_spacing
    legend_width = int(font_legend.getlength(PLAYER_VALUE_LEGEND)) + 40
    width = max(grid_width, legend_width, 500)
    top_margin = 90
    height = top_margin + num_rows * row_spacing + 50

    img = Image.new("RGB", (width, height), color="#2C2F33")
    draw = ImageDraw.Draw(img)

    title = f"Daily Recap - {datetime.now().strftime('%Y-%m-%d')}"
    draw.text((width // 2, 30), title, fill="#FFD700", font=font_title, anchor="mm")

    for index, user in enumerate(shown_users):
        row = index // BANNER_AVATARS_PER_ROW
        col = index % BANNER_AVATARS_PER_ROW
        members_in_row = min(BANNER_AVATARS_PER_ROW, len(shown_users) - row * BANNER_AVATARS_PER_ROW)
        row_start_x = (width - members_in_row * col_spacing) // 2
        x = row_start_x + col * col_spacing + col_spacing // 2
        y = top_margin + row * row_spacing

        member = _resolve_member(guild, user.id)
        avatar = await _download_member_avatar(member)
        avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        img.paste(avatar, (x - avatar_size // 2, y))

        name = user.display_name
        if len(name) > 14:
            name = name[:14] + "..."
        draw.text((x, y + avatar_size + 8), name, fill="white", font=font_name, anchor="mt")

        value_line = format_player_value_line(player_value_lookup, user.id)
        draw.text((x, y + avatar_size + 30), value_line, fill="#FFD700", font=font_value, anchor="mt")

    if overflow_count > 0:
        draw.text(
            (width // 2, top_margin + num_rows * row_spacing + 4),
            f"+{overflow_count} more played today",
            fill="#99AAB5",
            font=font_overflow,
            anchor="mm",
        )

    draw.text((width // 2, height - 16), PLAYER_VALUE_LEGEND, fill="#99AAB5", font=font_legend, anchor="mm")

    try:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print_error_log(f"build_daily_recap_banner: Failed to encode PNG: {e}")
        return None


async def _download_member_avatar(member: Optional[discord.Member]) -> Image.Image:
    """Same behavior as ``deps.player_value_display.download_avatar``, tolerant of a missing member."""
    if member is None:
        return Image.new("RGB", (100, 100), "#23272A")
    return await download_avatar(member)


def build_daily_summary_embeds(sections: DailySummarySections, guild: discord.Guild) -> List[List[discord.Embed]]:
    """
    Build one embed per user with a matched section, batched into groups of at most
    ``MAX_EMBEDS_PER_MESSAGE`` (Discord's per-message embed limit) so each batch maps to
    one ``channel.send()`` call.
    """
    embeds: List[discord.Embed] = []
    for user, text in sections.sections:
        wins, losses = compute_user_win_loss(sections.matches_by_user_id.get(user.id, []))
        color = COLOR_NEUTRAL
        if wins > losses:
            color = COLOR_WIN
        elif losses > wins:
            color = COLOR_LOSS

        embed = discord.Embed(description=text, color=color)
        member = _resolve_member(guild, user.id)
        icon_url = member.display_avatar.url if member else None
        embed.set_author(name=user.display_name, icon_url=icon_url)
        embed.set_footer(text=f"{wins}W - {losses}L")
        embeds.append(embed)

    return [embeds[i : i + MAX_EMBEDS_PER_MESSAGE] for i in range(0, len(embeds), MAX_EMBEDS_PER_MESSAGE)]
