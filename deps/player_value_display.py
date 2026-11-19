"""
Shared helpers for rendering a player's nightly-computed value (MMR / rank / value)
and Discord avatar into PIL images. Used by the match-start GIF and the daily AI
summary banner so both stay visually consistent and share one code path.
"""

import io
from typing import Dict, Optional, Tuple, cast

import aiohttp
import discord
from PIL import Image

from deps.analytic_player_value_data_access import data_access_fetch_player_values_and_ratings_by_algorithm
from deps.models import PlayerValueAlgorithm
from deps.log import print_error_log

# One-line legend explaining the "MMR | #rank | value" triplet shown under each player.
PLAYER_VALUE_LEGEND = (
    "MMR = decayed peak rank points   #rank = value rank among all players   last number = player value"
)


def build_player_value_lookup() -> Dict[int, Tuple[int, int, float]]:
    """
    user_id -> (mmr, position, value) for the nightly-computed TIME_DECAYED player value.

    mmr is the decayed peak rank points (rating), position is the 1-based rank among
    all users with a computed value (highest value = #1), sorted descending by value.
    """
    values_and_ratings = data_access_fetch_player_values_and_ratings_by_algorithm(PlayerValueAlgorithm.TIME_DECAYED)
    ordered = sorted(values_and_ratings.items(), key=lambda entry: entry[1][0], reverse=True)
    return {
        user_id: (round(rating), position, value)
        for position, (user_id, (value, rating)) in enumerate(ordered, start=1)
    }


def format_player_value_line(lookup: Dict[int, Tuple[int, int, float]], user_id: int) -> str:
    """Render the ``MMR | #rank | value`` line, or a placeholder when never computed."""
    entry = lookup.get(user_id)
    if entry is None:
        return "MMR -- | #-- | --"
    mmr, position, value = entry
    return f"MMR {mmr} | #{position} | {value:.1f}"


async def download_avatar(member: discord.Member, size: int = 100) -> Image.Image:
    """
    Download and resize a Discord member's avatar to ``size`` x ``size`` (100x100 by default).

    Args:
        member: Discord member
        size: Side of the square result in pixels

    Returns:
        PIL Image object (``size`` x ``size`` pixels), gray placeholder on failure
    """
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    avatar_img = cast(Image.Image, Image.open(io.BytesIO(data)))
                    return avatar_img.resize((size, size), Image.Resampling.LANCZOS)
    except Exception as e:
        print_error_log(f"download_avatar: Failed to download avatar for {member.display_name}: {e}")

    return Image.new("RGB", (size, size), "#23272A")


# Custom emojis never change once uploaded, so each id is downloaded once per process.
_emoji_bytes_cache: Dict[str, bytes] = {}


async def download_custom_emoji(emoji_id: str, size: int = 64) -> Optional[Image.Image]:
    """A Discord custom emoji (e.g. a rank icon) as an RGBA image, or None when it cannot be downloaded."""
    key = str(emoji_id)
    if key not in _emoji_bytes_cache:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"https://cdn.discordapp.com/emojis/{key}.png?size=128") as resp:
                    if resp.status != 200:
                        return None
                    _emoji_bytes_cache[key] = await resp.read()
        except Exception as e:
            print_error_log(f"download_custom_emoji: Failed to download emoji {key}: {e}")
            return None
    image = cast(Image.Image, Image.open(io.BytesIO(_emoji_bytes_cache[key]))).convert("RGBA")
    return image.resize((size, size), Image.Resampling.LANCZOS)
