"""
Match Start GIF Generation

Generates animated GIFs showing player statistics when a ranked match starts.

Frames (all ``FRAME_WIDTH`` x ``FRAME_HEIGHT``):
1. "Good luck to..." with all player avatars, names and player value
2. Map frame (only when the map is known): map artwork + every player's win rate on that map and
   their top 5 operators there
3. One frame per player:
   - Discord avatar and display name
   - Siege rank and timezone/local time
   - Ranked K/D ratio and win rate percentage, total hours played on server
   - Colored form strip of the last 10 matches
   - Win rate and top 5 operators on the current map (when known)
   - Top 3 most-played attackers and defenders (last 30 days)
4. Optional result frame (live LEADING/TRAILING/TIED or final Won/Loss)
"""

from PIL import Image, ImageDraw, ImageEnhance, ImageFont
import io
from datetime import datetime, timedelta, date
from functools import lru_cache
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
import discord
import pytz
from deps.analytic_leaderboard_data_access import data_access_fetch_team_stats, data_access_fetch_users_operators
from deps.analytic_models import UserMapStats, UserOperatorCount
from deps.analytic_data_access import (
    data_access_fetch_user_full_user_info,
    fetch_user_info_by_user_id,
)
from deps.analytic_match_data_access import data_access_fetch_recent_results, data_access_fetch_user_map_stats
from deps.analytic_profile_data_access import data_access_fetch_total_hours
from deps.map_images import load_map_image
from deps.operator_mapping import get_operator_role
from deps.player_value_display import (
    PLAYER_VALUE_LEGEND,
    build_player_value_lookup,
    download_avatar,
    format_player_value_line,
)
from deps.siege import StatsCcRankedMatchEndResult, get_user_rank_emoji
from deps.log import print_error_log

FRAME_DURATION_MS = 4000
RESULT_FRAME_DURATION_MS = 7000

# Every frame shares one canvas size so a frame always fully overwrites the previous one.
FRAME_WIDTH = 1000
FRAME_HEIGHT = 800
AVATAR_SOURCE_SIZE = 160

FONT_PATH = "./fonts/Minecraft.ttf"
COLOR_BG = "#2C2F33"
COLOR_BG_RESULT = "#1E2124"
COLOR_MUTED = "#99AAB5"
COLOR_GOLD = "#FFD700"
COLOR_WIN = "#3BA55D"
COLOR_LOSS = "#ED4245"
COLOR_TIE = "#FEE75C"

BANNER_HEIGHT = 300
MAP_TOP_OPERATORS = 5
RECENT_FORM_MATCHES = 10

PlayerValueLookup = Dict[int, Tuple[int, int, float]]


def match_result_live_status_display(result: StatsCcRankedMatchEndResult) -> tuple[str, str]:
    """In-progress score line: ahead / behind / tied in rounds (not final match outcome)."""
    if result.is_tie:
        return "TIED", COLOR_TIE
    if result.won:
        return "LEADING", COLOR_WIN
    return "TRAILING", COLOR_LOSS


def match_result_final_plain_summary(
    result: StatsCcRankedMatchEndResult, *, spaced_hyphen: bool = True
) -> tuple[str, str]:
    """
    Final outcome text with score: ``Won 4 - 1``, ``Loss 1 - 4``, ``Tie 2 - 2`` (ASCII only).

    ``spaced_hyphen`` uses ``' - '`` for PNG/Minecraft font; use ``False`` for compact Discord text.
    """
    sep = " - " if spaced_hyphen else "-"
    score_part = f"{result.our_score}{sep}{result.their_score}"
    if result.is_tie:
        return f"Tie {score_part}", COLOR_TIE
    if result.won:
        return f"Won {score_part}", COLOR_WIN
    return f"Loss {score_part}", COLOR_LOSS


@lru_cache(maxsize=None)
def _font(size: int) -> Any:
    """Minecraft font at ``size`` px, falling back to PIL's default font when the file is missing."""
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception as e:
        print_error_log(f"match_start_gif: Failed to load font {FONT_PATH}: {e}")
        return ImageFont.load_default()


def _fit_font(text: str, max_width: int, size: int, min_size: int = 14) -> Any:
    """Largest font up to ``size`` px in which ``text`` is at most ``max_width`` px wide."""
    while size > min_size and _font(size).getlength(text) > max_width:
        size -= 1
    return _font(size)


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "..."


def _paste_avatar(img: Image.Image, avatar: Image.Image, xy: Tuple[int, int], size: int) -> None:
    img.paste(avatar.convert("RGB").resize((size, size), Image.Resampling.LANCZOS), xy)


def _win_rate_color(win_rate: float) -> str:
    if win_rate >= 55:
        return COLOR_WIN
    if win_rate < 45:
        return COLOR_LOSS
    return "white"


def _format_operators(operators: Sequence[Tuple[str, int]]) -> str:
    """``[("Ash", 14), ("Mira", 9)]`` -> ``"Ash 14  Mira 9"``."""
    return "  ".join(f"{name} {count}" for name, count in operators)


def _format_map_record(stats: UserMapStats) -> str:
    return f"{stats.win_rate:.0f}% win | {stats.matches} games"


def _map_banner(map_name: str, size: Tuple[int, int]) -> Optional[Image.Image]:
    """Map artwork cropped to ``size`` with a darkened bottom strip, or None without artwork."""
    artwork = load_map_image(map_name)
    if artwork is None:
        return None
    width, height = size
    scale = max(width / artwork.width, height / artwork.height)
    artwork = artwork.resize((round(artwork.width * scale), round(artwork.height * scale)), Image.Resampling.LANCZOS)
    left = (artwork.width - width) // 2
    top = (artwork.height - height) // 2
    return artwork.crop((left, top, left + width, top + height))


def _create_match_result_frame(result: StatsCcRankedMatchEndResult) -> Image.Image:
    """Final GIF frame: live LEADING/TRAILING or final Win/Loss line with score (stats.cc)."""
    width, height = FRAME_WIDTH, FRAME_HEIGHT
    img = Image.new("RGB", (width, height), color=COLOR_BG_RESULT)
    banner = _map_banner(result.map_name, (width, height)) if result.map_name else None
    if banner is not None:
        img.paste(ImageEnhance.Brightness(banner).enhance(0.3))
    draw = ImageDraw.Draw(img)

    if result.is_match_complete:
        headline, head_color = match_result_final_plain_summary(result, spaced_hyphen=True)
        draw.text((width // 2, height // 2 - 80), headline, fill=head_color, font=_font(92), anchor="mm")
        sub_y = height // 2 + 50
    else:
        headline, head_color = match_result_live_status_display(result)
        draw.text((width // 2, height // 2 - 110), headline, fill=head_color, font=_font(92), anchor="mm")
        score_text = f"{result.our_score}  -  {result.their_score}"
        draw.text((width // 2, height // 2 + 20), score_text, fill="white", font=_font(78), anchor="mm")
        sub_y = height // 2 + 120

    sub = f"Map: {result.map_name}" if result.map_name else "Ranked match result (stats.cc)"
    draw.text((width // 2, sub_y), sub, fill="#DCDDDE", font=_font(36), anchor="mm")

    return img


async def generate_match_end_static_summary(
    members: List[discord.Member],
    result: StatsCcRankedMatchEndResult,
) -> Optional[bytes]:
    """
    Single static PNG: participant avatars + display names and final score (no animation).

    Used when stats.cc reports ``Match Ending:`` so the Discord post stops cycling GIF frames.
    """
    if not members:
        return None
    members = members[:5]
    width = 800
    row_top = 200
    avatar_size = 72 if len(members) >= 4 else 88
    spacing = 140 if len(members) <= 3 else 118
    height = max(540, row_top + avatar_size + 60)

    img = Image.new("RGB", (width, height), color=COLOR_BG_RESULT)
    draw = ImageDraw.Draw(img)
    font_path = "./fonts/Minecraft.ttf"
    try:
        font_head: Any = ImageFont.truetype(font_path, 54)
        font_sub: Any = ImageFont.truetype(font_path, 24)
        font_name: Any = ImageFont.truetype(font_path, 20)
    except Exception as e:
        print_error_log(f"generate_match_end_static_summary: Failed to load font: {e}")
        font_head = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_name = ImageFont.load_default()

    headline, head_color = match_result_final_plain_summary(result, spaced_hyphen=True)
    draw.text((width // 2, 52), headline, fill=head_color, font=font_head, anchor="mm")
    sub = "Ranked match result (stats.cc)"
    if result.map_name:
        sub = f"Map: {result.map_name}"
    draw.text((width // 2, 128), sub, fill="#B9BBBE", font=font_sub, anchor="mm")

    total_w = (len(members) - 1) * spacing + avatar_size
    start_x = (width - total_w) // 2
    for i, member in enumerate(members):
        x = start_x + i * spacing
        try:
            av = await download_avatar(member)
            av = av.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
            if av.mode == "RGBA":
                img.paste(av, (x, row_top), av)
            else:
                img.paste(av, (x, row_top))
        except Exception as e:
            print_error_log(f"generate_match_end_static_summary: avatar for {member.display_name}: {e}")
        name = member.display_name
        if len(name) > 14:
            name = name[:14] + "..."
        draw.text((x + avatar_size // 2, row_top + avatar_size + 8), name, fill="white", font=font_name, anchor="mt")

    try:
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        buf.seek(0)
        return buf.getvalue()
    except Exception as e:
        print_error_log(f"generate_match_end_static_summary: Failed to encode PNG: {e}")
        return None


def _group_operators_by_user(from_date: date) -> dict[str, list[UserOperatorCount]]:
    """Operator usage since ``from_date`` grouped by user display name."""
    grouped: dict[str, list[UserOperatorCount]] = {}
    for stat in data_access_fetch_users_operators(from_date):
        grouped.setdefault(stat.user, []).append(stat)
    return grouped


def _fetch_map_stats(members: List[discord.Member], map_name: str) -> dict[int, UserMapStats]:
    """Each member's record on ``map_name``; a member whose lookup fails is simply left out."""
    stats: dict[int, UserMapStats] = {}
    for member in members:
        try:
            stats[member.id] = data_access_fetch_user_map_stats(member.id, map_name, MAP_TOP_OPERATORS)
        except Exception as e:
            print_error_log(f"generate_match_start_gif: Failed to fetch map stats for {member.display_name}: {e}")
    return stats


async def _download_avatars(members: List[discord.Member]) -> dict[int, Image.Image]:
    """Download every avatar once; all frames resize from these."""
    return {member.id: await download_avatar(member, AVATAR_SOURCE_SIZE) for member in members}


def _save_gif(frames: List[Image.Image], has_result_frame: bool) -> Optional[bytes]:
    try:
        output = io.BytesIO()
        n = len(frames)
        duration: Union[int, Sequence[int]]
        if has_result_frame and n >= 2:
            duration = [FRAME_DURATION_MS] * (n - 1) + [RESULT_FRAME_DURATION_MS]
        else:
            duration = FRAME_DURATION_MS
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=duration,
            loop=0,  # Infinite loop
        )
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        print_error_log(f"generate_match_start_gif: Failed to save GIF: {e}")
        return None


async def generate_match_start_gif(
    members: List[discord.Member],
    guild_id: int,
    guild_emoji: dict,
    match_result: Optional[StatsCcRankedMatchEndResult] = None,
    map_name: Optional[str] = None,
) -> Optional[bytes]:
    """
    Generate animated GIF with player stats.

    Args:
        members: List of Discord members in the voice channel
        guild_id: Guild ID for fetching stats
        guild_emoji: Dictionary of guild emojis for rank display
        match_result: When set, append a final frame: LEADING/TRAILING/TIED while in progress,
        Won/Loss/Tie only when ``result.is_match_complete`` (see ``deps.siege``).
        map_name: Map being played, when known. Defaults to ``match_result.map_name``. Adds the map
        frame and the per-map stats on the player frames.

    Returns:
        GIF bytes, or None if generation fails or no members
    """
    if not members:
        return None

    # Limit to 5 members to keep GIF size manageable
    members = members[:5]
    map_name = map_name or (match_result.map_name if match_result else None)

    user_operator_map = _group_operators_by_user(date.today() - timedelta(days=30))
    map_stats = _fetch_map_stats(members, map_name) if map_name else {}

    # Nightly-computed player value (MMR / rank / value), looked up once for all members
    try:
        player_value_lookup = build_player_value_lookup()
    except Exception as e:
        print_error_log(f"generate_match_start_gif: Failed to fetch player values: {e}")
        player_value_lookup = {}

    avatars = await _download_avatars(members)

    frames: List[Image.Image] = []

    try:
        frames.append(_create_good_luck_frame(members, avatars, player_value_lookup))
    except Exception as e:
        print_error_log(f"generate_match_start_gif: Failed to create good luck frame: {e}")

    if map_name:
        try:
            map_frame = _create_map_frame(map_name, members, avatars, map_stats)
            if map_frame is not None:
                frames.append(map_frame)
        except Exception as e:
            print_error_log(f"generate_match_start_gif: Failed to create map frame: {e}")

    for member in members:
        try:
            frames.append(
                await _create_player_frame(
                    member,
                    avatars[member.id],
                    user_operator_map,
                    guild_emoji,
                    player_value_lookup,
                    map_name,
                    map_stats.get(member.id),
                )
            )
        except Exception as e:
            print_error_log(f"generate_match_start_gif: Failed to create frame for {member.display_name}: {e}")

    has_result_frame = False
    if match_result is not None:
        try:
            frames.append(_create_match_result_frame(match_result))
            has_result_frame = True
        except Exception as e:
            print_error_log(f"generate_match_start_gif: Failed to create result frame: {e}")

    if not frames:
        return None
    return _save_gif(frames, has_result_frame)


def _create_good_luck_frame(
    members: List[discord.Member], avatars: dict[int, Image.Image], player_value_lookup: PlayerValueLookup
) -> Image.Image:
    """
    Create the first "Good luck to..." frame showing all players.

    Args:
        members: List of Discord members
        avatars: user_id -> downloaded avatar
        player_value_lookup: user_id -> (mmr, position, value), see ``build_player_value_lookup``

    Returns:
        PIL Image object
    """
    width, height = FRAME_WIDTH, FRAME_HEIGHT
    img = Image.new("RGB", (width, height), color=COLOR_BG)
    draw = ImageDraw.Draw(img)

    draw.text((width // 2, 60), "Good luck to", fill=COLOR_GOLD, font=_font(56), anchor="mm")

    num_members = len(members)
    # Spacing is the distance between avatar centers on a row; it must be wide enough that
    # neighboring "MMR xxxx | #xx | xxx.x" value lines never touch.
    if num_members <= 3:
        avatar_size, y_position, row_pitch = 170, 160, 0
    else:
        avatar_size, y_position, row_pitch = 130, 130, 280
    spacing = 300

    def _row_start_x(count: int) -> int:
        return (width - ((count - 1) * spacing + avatar_size)) // 2

    for i, member in enumerate(members):
        row, col = divmod(i, 3)
        row_count = min(3, num_members - row * 3)
        x = _row_start_x(row_count) + col * spacing
        y = y_position + row * row_pitch
        center_x = x + avatar_size // 2

        _paste_avatar(img, avatars[member.id], (x, y), avatar_size)
        draw.text(
            (center_x, y + avatar_size + 14),
            _truncate(member.display_name, 12),
            fill="white",
            font=_font(30),
            anchor="mt",
        )
        value_line = format_player_value_line(player_value_lookup, member.id)
        draw.text((center_x, y + avatar_size + 56), value_line, fill=COLOR_GOLD, font=_font(22), anchor="mt")

    _draw_team_stats(draw, members, width, 500 if num_members <= 3 else 700)

    # Legend explaining the MMR / rank / value triplet shown under each avatar
    draw.text((width // 2, height - 22), PLAYER_VALUE_LEGEND, fill=COLOR_MUTED, font=_font(15), anchor="mm")

    return img


def _draw_team_stats(draw: ImageDraw.ImageDraw, members: List[discord.Member], width: int, y: int) -> None:
    """Draw "Team: N games | X% win rate" for 2-5 players; skipped (not fatal) when unavailable."""
    if not 2 <= len(members) <= 5:
        return
    try:
        team_stats = data_access_fetch_team_stats([member.id for member in members])
        if team_stats is None:
            return
        games_played, win_rate = team_stats
        text = f"Team: {games_played} games | {win_rate * 100:.1f}% win rate"
        draw.text((width // 2, y), text, fill="#00FF00", font=_font(32), anchor="mm")
    except Exception as e:
        print_error_log(f"_create_good_luck_frame: Failed to fetch team stats: {e}")


def _create_map_frame(
    map_name: str,
    members: List[discord.Member],
    avatars: dict[int, Image.Image],
    map_stats: dict[int, UserMapStats],
) -> Optional[Image.Image]:
    """Map artwork with each player's win rate and top 5 operators on that map; None without artwork."""
    banner = _map_banner(map_name, (FRAME_WIDTH, BANNER_HEIGHT))
    if banner is None:
        return None
    img = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), color=COLOR_BG)
    img.paste(banner, (0, 0))
    draw = ImageDraw.Draw(img)

    # Dark strip behind the map name so it stays readable on any artwork
    strip = Image.new("RGB", (FRAME_WIDTH, 110), color="#000000")
    img.paste(
        Image.blend(img.crop((0, BANNER_HEIGHT - 110, FRAME_WIDTH, BANNER_HEIGHT)), strip, 0.6),
        (0, BANNER_HEIGHT - 110),
    )
    draw.text((30, BANNER_HEIGHT - 75), map_name.upper(), fill="white", font=_font(58))
    draw.text(
        (FRAME_WIDTH - 30, BANNER_HEIGHT - 28),
        "Ranked win rate and top operators (rounds)",
        fill="#DCDDDE",
        font=_font(20),
        anchor="rm",
    )

    row_height = (FRAME_HEIGHT - BANNER_HEIGHT - 20) // 5
    for i, member in enumerate(members):
        _draw_map_row(
            img, draw, member, avatars[member.id], map_stats.get(member.id), BANNER_HEIGHT + 10 + i * row_height
        )
    return img


def _draw_map_row(
    img: Image.Image,
    draw: ImageDraw.ImageDraw,
    member: discord.Member,
    avatar: Image.Image,
    stats: Optional[UserMapStats],
    y: int,
) -> None:
    _paste_avatar(img, avatar, (30, y + 6), 68)
    draw.text((116, y + 6), _truncate(member.display_name, 16), fill="white", font=_font(32))
    if stats is None or stats.matches == 0:
        draw.text((116, y + 46), "No ranked games on this map yet", fill=COLOR_MUTED, font=_font(22))
        return
    draw.text(
        (FRAME_WIDTH - 30, y + 24),
        _format_map_record(stats),
        fill=_win_rate_color(stats.win_rate),
        font=_font(30),
        anchor="rm",
    )
    operators = _format_operators(stats.top_operators)
    draw.text((116, y + 46), operators, fill=COLOR_MUTED, font=_fit_font(operators, FRAME_WIDTH - 146, 24))


def _draw_recent_form(draw: ImageDraw.ImageDraw, results: Sequence[bool], x: int, y: int) -> None:
    """Strip of W/L chips, oldest on the left so the latest match is at the right end."""
    chip, gap = 38, 8
    for i, won in enumerate(reversed(results)):
        left = x + i * (chip + gap)
        draw.rectangle((left, y, left + chip, y + chip), fill=COLOR_WIN if won else COLOR_LOSS)
        draw.text((left + chip // 2, y + chip // 2), "W" if won else "L", fill="white", font=_font(24), anchor="mm")


def _draw_player_header(
    draw: ImageDraw.ImageDraw,
    member: discord.Member,
    guild_emoji: dict,
    value_line: str,
    time_zone: Optional[str],
) -> None:
    draw.text((220, 30), _truncate(member.display_name, 18), fill="white", font=_font(46))
    draw.text((220, 92), f"Rank: {get_user_rank_emoji(guild_emoji, member)}", fill="#7289DA", font=_font(30))
    if time_zone:
        try:
            time_str = datetime.now(pytz.timezone(time_zone)).strftime("%I:%M %p")
            draw.text((220, 134), f"{time_zone} - {time_str}", fill=COLOR_MUTED, font=_font(26))
        except Exception as e:
            print_error_log(f"_create_player_frame: Failed to get timezone for {member.display_name}: {e}")
    draw.text((220, 172), value_line, fill=COLOR_GOLD, font=_font(28))


def _fetch_player_numbers(member: discord.Member) -> Tuple[float, float, int, List[bool]]:
    """(ranked K/D, win rate %, hours on server, last matches newest first); a failed lookup becomes 0 / []."""
    try:
        user_info = data_access_fetch_user_full_user_info(member.id)
        overall_kd = user_info.rank_kd_ratio if user_info and user_info.rank_kd_ratio else 0.0
        win_rate = user_info.rank_win_percentage if user_info and user_info.rank_win_percentage else 0.0
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to fetch user stats for {member.display_name}: {e}")
        overall_kd, win_rate = 0.0, 0.0
    try:
        total_hours = data_access_fetch_total_hours(member.id)
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to fetch total hours for {member.display_name}: {e}")
        total_hours = 0
    try:
        recent = data_access_fetch_recent_results(member.id, RECENT_FORM_MATCHES)
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to fetch recent results for {member.display_name}: {e}")
        recent = []
    return overall_kd, win_rate, total_hours, recent


def _draw_map_block(draw: ImageDraw.ImageDraw, map_name: str, stats: Optional[UserMapStats], y: int) -> int:
    """Win rate and top operators on the current map. Returns the y below the block."""
    draw.text((30, y), f"ON {map_name.upper()}", fill="#5DADE2", font=_font(30))
    if stats is None or stats.matches == 0:
        draw.text((30, y + 42), "No ranked games on this map yet", fill=COLOR_MUTED, font=_font(26))
        return y + 100
    draw.text((30, y + 42), _format_map_record(stats), fill=_win_rate_color(stats.win_rate), font=_font(28))
    operators = f"Top 5: {_format_operators(stats.top_operators)}"
    draw.text((30, y + 84), operators, fill="white", font=_fit_font(operators, FRAME_WIDTH - 60, 26))
    return y + 140


def _draw_operator_column(
    draw: ImageDraw.ImageDraw, title: str, color: str, operators: Sequence[UserOperatorCount], x: int, y: int
) -> None:
    draw.text((x, y), title, fill=color, font=_font(28))
    if not operators:
        draw.text((x + 10, y + 46), "No recent data", fill=COLOR_MUTED, font=_font(26))
        return
    for i, op in enumerate(operators[:3]):
        row_y = y + 46 + i * 40
        draw.text((x + 10, row_y), f"{i + 1}. {op.operator_name}", fill="white", font=_font(26))
        draw.text((x + 430, row_y), f"{op.count} rds", fill=COLOR_MUTED, font=_font(26), anchor="ra")


async def _create_player_frame(
    member: discord.Member,
    avatar: Image.Image,
    user_operator_map: dict,
    guild_emoji: dict,
    player_value_lookup: PlayerValueLookup,
    map_name: Optional[str],
    map_stats: Optional[UserMapStats],
) -> Image.Image:
    """
    Create single frame for one player.

    Args:
        member: Discord member
        avatar: Downloaded avatar
        user_operator_map: Dictionary mapping display names to operator stats
        guild_emoji: Dictionary of guild emojis
        player_value_lookup: user_id -> (mmr, position, value), see ``build_player_value_lookup``
        map_name: Map being played, when known
        map_stats: This player's record on ``map_name``

    Returns:
        PIL Image object
    """
    width, height = FRAME_WIDTH, FRAME_HEIGHT
    img = Image.new("RGB", (width, height), color=COLOR_BG)  # Discord dark theme color
    draw = ImageDraw.Draw(img)

    _paste_avatar(img, avatar, (30, 30), 170)
    user_profile = await fetch_user_info_by_user_id(member.id)
    _draw_player_header(
        draw,
        member,
        guild_emoji,
        format_player_value_line(player_value_lookup, member.id),
        user_profile.time_zone if user_profile else None,
    )

    overall_kd, win_rate, total_hours, recent = _fetch_player_numbers(member)
    draw.text((30, 230), f"Ranked K/D: {overall_kd:.2f}", fill="white", font=_font(30))
    draw.text((520, 230), f"Win Rate: {win_rate:.1f}%", fill="white", font=_font(30))
    draw.text((30, 276), f"Time on Server: {total_hours}h", fill="white", font=_font(30))
    wins = sum(recent)
    draw.text((520, 276), f"Last {len(recent)}: {wins}W - {len(recent) - wins}L", fill="white", font=_font(30))
    _draw_recent_form(draw, recent, 30, 326)

    y = 396
    if map_name:
        y = _draw_map_block(draw, map_name, map_stats, y)

    operators = user_operator_map.get(member.display_name, [])
    attackers = sorted(
        (op for op in operators if get_operator_role(op.operator_name) == "attacker"), key=lambda x: -x.count
    )
    defenders = sorted(
        (op for op in operators if get_operator_role(op.operator_name) == "defender"), key=lambda x: -x.count
    )
    y += 10
    _draw_operator_column(draw, "TOP ATTACKERS (30d)", "#FF8C00", attackers, 30, y)
    _draw_operator_column(draw, "TOP DEFENDERS (30d)", "#43B581", defenders, 520, y)

    # Legend explaining the MMR / rank / value triplet shown above
    draw.text((width // 2, height - 22), PLAYER_VALUE_LEGEND, fill=COLOR_MUTED, font=_font(15), anchor="mm")

    return img
