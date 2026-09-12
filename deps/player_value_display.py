"""
Shared helpers for rendering a player's nightly-computed value (MMR / rank / value)
and Discord avatar into PIL images. Used by the match-start GIF and the daily AI
summary banner so both stay visually consistent and share one code path.
"""

import io
from typing import Dict, Tuple, cast

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


async def download_avatar(member: discord.Member) -> Image.Image:
    """
    Download and resize a Discord member's avatar to 100x100.

    Args:
        member: Discord member

    Returns:
        PIL Image object (100x100 pixels), gray placeholder on failure
    """
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    avatar_img = cast(Image.Image, Image.open(io.BytesIO(data)))
                    return avatar_img.resize((100, 100), Image.Resampling.LANCZOS)
    except Exception as e:
        print_error_log(f"download_avatar: Failed to download avatar for {member.display_name}: {e}")

    return Image.new("RGB", (100, 100), "#23272A")
