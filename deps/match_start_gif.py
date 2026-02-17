"""
Match Start GIF Generation

Generates animated GIFs showing player statistics when a ranked match starts.

First frame: "Good luck to..." with all player avatars and names
Individual frames display each player's stats:
- Discord avatar and display name
- Siege rank and timezone/local time
- Ranked K/D ratio and win rate percentage
- Recent win/loss record (last 10 matches)
- Total hours played on server
- Top 3 most-played attackers and defenders (last 30 days)
"""

from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
from datetime import datetime, timedelta, date, timezone as dt_timezone
from typing import List, Optional
import discord
import pytz
from deps.analytic_leaderboard_data_access import data_access_fetch_users_operators
from deps.analytic_data_access import (
    data_access_fetch_recent_win_loss,
    data_access_fetch_user_full_user_info,
    fetch_user_info_by_user_id,
)
from deps.analytic_profile_data_access import data_access_fetch_total_hours
from deps.operator_mapping import get_operator_role
from deps.siege import get_user_rank_emoji
from deps.log import print_error_log, print_log


async def generate_match_start_gif(members: List[discord.Member], guild_id: int, guild_emoji: dict) -> Optional[bytes]:
    """
    Generate animated GIF with player stats.

    Args:
        members: List of Discord members in the voice channel
        guild_id: Guild ID for fetching stats
        guild_emoji: Dictionary of guild emojis for rank display

    Returns:
        GIF bytes, or None if generation fails or no members
    """
    if not members:
        return None

    # Limit to 5 members to keep GIF size manageable
    members = members[:5]

    # Fetch operator stats for last 30 days
    from_date = date.today() - timedelta(days=30)
    all_operator_stats = data_access_fetch_users_operators(from_date)

    # Group by user display name
    user_operator_map = {}
    for stat in all_operator_stats:
        if stat.user not in user_operator_map:
            user_operator_map[stat.user] = []
        user_operator_map[stat.user].append(stat)

    # Create frames
    frames = []

    # First frame: "Good luck to..." with all players
    try:
        good_luck_frame = await _create_good_luck_frame(members)
        frames.append(good_luck_frame)
    except Exception as e:
        print_error_log(f"generate_match_start_gif: Failed to create good luck frame: {e}")

    # Individual player frames
    for member in members:
        try:
            frame = await _create_player_frame(member, user_operator_map, guild_id, guild_emoji)
            frames.append(frame)
        except Exception as e:
            print_error_log(f"generate_match_start_gif: Failed to create frame for {member.display_name}: {e}")
            continue

    # Combine into animated GIF
    if not frames:
        return None

    try:
        output = io.BytesIO()
        frames[0].save(
            output,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=4000,  # 4 seconds per frame
            loop=0,  # Infinite loop
        )
        output.seek(0)
        return output.getvalue()
    except Exception as e:
        print_error_log(f"generate_match_start_gif: Failed to save GIF: {e}")
        return None


async def _create_good_luck_frame(members: List[discord.Member]) -> Image.Image:
    """
    Create the first "Good luck to..." frame showing all players.

    Args:
        members: List of Discord members

    Returns:
        PIL Image object
    """
    # Frame size - increase height for 4+ members to fit team stats
    width = 800
    height = 650 if len(members) > 3 else 600
    img = Image.new("RGB", (width, height), color="#2C2F33")
    draw = ImageDraw.Draw(img)

    # Load font
    font_path = "./fonts/Minecraft.ttf"
    try:
        font_title = ImageFont.truetype(font_path, 36)
        font_name = ImageFont.truetype(font_path, 20)
        font_stats = ImageFont.truetype(font_path, 18)
    except Exception as e:
        print_error_log(f"_create_good_luck_frame: Failed to load font: {e}")
        font_title = ImageFont.load_default()
        font_name = ImageFont.load_default()
        font_stats = ImageFont.load_default()

    # Title
    title = "Good luck to"
    draw.text((width // 2, 50), title, fill="#FFD700", font=font_title, anchor="mm")

    # Calculate layout for avatars and names
    num_members = len(members)
    if num_members <= 3:
        # Single row
        avatar_size = 120
        spacing = 180
        start_x = (width - (num_members * spacing - 60)) // 2
        y_position = 150
    else:
        # Two rows for 4-5 members
        avatar_size = 100
        spacing = 150
        start_x = (width - (min(3, num_members) * spacing - 50)) // 2
        y_position = 130

    # Download avatars and place them
    row = 0
    col = 0
    for i, member in enumerate(members):
        if num_members > 3 and i == 3:
            # Start second row
            row = 1
            col = 0
            # Center the second row if fewer than 3 in it
            remaining = num_members - 3
            start_x = (width - (remaining * spacing - 50)) // 2

        x = start_x + col * spacing
        y = y_position + row * 220

        # Download and place avatar
        avatar = await _download_avatar(member)
        avatar = avatar.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)
        img.paste(avatar, (x, y))

        # Draw name below avatar
        name = member.display_name
        if len(name) > 12:
            name = name[:12] + "..."
        draw.text((x + avatar_size // 2, y + avatar_size + 10), name, fill="white", font=font_name, anchor="mt")

        col += 1

    # Fetch and display team stats if we have 2-5 players
    if 2 <= num_members <= 5:
        from deps.analytic_leaderboard_data_access import data_access_fetch_team_stats

        try:
            user_ids = [member.id for member in members]
            team_stats = data_access_fetch_team_stats(user_ids)

            if team_stats is not None:
                games_played, win_rate = team_stats
                win_rate_pct = win_rate * 100  # Convert to percentage

                # Position stats below the last row of players
                # For 4-5 members (two rows), position with more margin
                if num_members > 3:
                    stats_y = y_position + (row + 1) * 220 + 50  # Extra margin for two rows
                else:
                    stats_y = y_position + (row + 1) * 220 + 30

                # Format stats text
                stats_text = f"Team: {games_played} games | {win_rate_pct:.1f}% win rate"

                # Draw stats centered
                draw.text((width // 2, stats_y), stats_text, fill="#00FF00", font=font_stats, anchor="mm")
        except Exception as e:
            # Don't fail the entire frame if stats fetch fails
            print_error_log(f"_create_good_luck_frame: Failed to fetch team stats: {e}")

    return img


async def _create_player_frame(
    member: discord.Member, user_operator_map: dict, guild_id: int, guild_emoji: dict
) -> Image.Image:
    """
    Create single frame for one player.

    Args:
        member: Discord member
        user_operator_map: Dictionary mapping display names to operator stats
        guild_id: Guild ID
        guild_emoji: Dictionary of guild emojis

    Returns:
        PIL Image object
    """
    # Frame size
    width, height = 800, 600
    img = Image.new("RGB", (width, height), color="#2C2F33")  # Discord dark theme color
    draw = ImageDraw.Draw(img)

    # Load font
    font_path = "./fonts/Minecraft.ttf"
    try:
        font_large = ImageFont.truetype(font_path, 28)
        font_medium = ImageFont.truetype(font_path, 20)
        font_small = ImageFont.truetype(font_path, 16)
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to load font: {e}")
        # Fallback to default font
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Download and paste avatar
    avatar = await _download_avatar(member)
    img.paste(avatar, (20, 20))

    # Player name
    draw.text((140, 30), f"{member.display_name}", fill="white", font=font_large)

    # Rank emoji (text representation)
    rank_emoji_str = get_user_rank_emoji(guild_emoji, member)
    draw.text((140, 65), f"Rank: {rank_emoji_str}", fill="#7289DA", font=font_medium)

    # Get user profile info for timezone
    user_profile = await fetch_user_info_by_user_id(member.id)
    if user_profile and user_profile.time_zone:
        try:
            tz = pytz.timezone(user_profile.time_zone)
            current_time = datetime.now(tz)
            time_str = current_time.strftime("%I:%M %p")
            draw.text((140, 95), f"{user_profile.time_zone} - {time_str}", fill="#99AAB5", font=font_small)
        except Exception as e:
            print_error_log(f"_create_player_frame: Failed to get timezone for {member.display_name}: {e}")

    # Get full user stats
    try:
        user_info = data_access_fetch_user_full_user_info(member.id)
        overall_kd = user_info.rank_kd_ratio if user_info and user_info.rank_kd_ratio else 0.0
        win_rate = user_info.rank_win_percentage if user_info and user_info.rank_win_percentage else 0.0
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to fetch user stats for {member.display_name}: {e}")
        overall_kd = 0.0
        win_rate = 0.0

    # Get recent match stats
    try:
        wins, losses = data_access_fetch_recent_win_loss(member.id, 10)
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to fetch recent W/L for {member.display_name}: {e}")
        wins, losses = 0, 0

    # Get total hours played on server
    try:
        total_hours = data_access_fetch_total_hours(member.id)
    except Exception as e:
        print_error_log(f"_create_player_frame: Failed to fetch total hours for {member.display_name}: {e}")
        total_hours = 0

    # Stats display
    draw.text((20, 140), f"Ranked K/D: {overall_kd:.2f}", fill="white", font=font_medium)
    draw.text((400, 140), f"Win Rate: {win_rate:.1f}%", fill="white", font=font_medium)
    draw.text((20, 170), f"Last 10: {wins}W - {losses}L", fill="white", font=font_medium)
    draw.text((400, 170), f"Time on Server: {total_hours}h", fill="white", font=font_medium)

    # Get operator stats for this user
    operators = user_operator_map.get(member.display_name, [])

    # Classify and sort
    attackers = [op for op in operators if get_operator_role(op.operator_name) == "attacker"]
    defenders = [op for op in operators if get_operator_role(op.operator_name) == "defender"]

    attackers.sort(key=lambda x: x.count, reverse=True)
    defenders.sort(key=lambda x: x.count, reverse=True)

    # Top 3 attackers
    y = 220
    draw.text((20, y), "TOP ATTACKERS (Last 30 Days)", fill="#FF8C00", font=font_medium)
    y += 40

    if attackers:
        for i, op in enumerate(attackers[:3]):
            draw.text((40, y), f"{i+1}. {op.operator_name}", fill="white", font=font_small)
            draw.text((400, y), f"{op.count} rounds", fill="#99AAB5", font=font_small)
            y += 30
    else:
        draw.text((40, y), "No recent data", fill="#99AAB5", font=font_small)
        y += 30

    # Top 3 defenders
    y += 20
    draw.text((20, y), "TOP DEFENDERS (Last 30 Days)", fill="#43B581", font=font_medium)
    y += 40

    if defenders:
        for i, op in enumerate(defenders[:3]):
            draw.text((40, y), f"{i+1}. {op.operator_name}", fill="white", font=font_small)
            draw.text((400, y), f"{op.count} rounds", fill="#99AAB5", font=font_small)
            y += 30
    else:
        draw.text((40, y), "No recent data", fill="#99AAB5", font=font_small)

    return img


async def _download_avatar(member: discord.Member) -> Image.Image:
    """
    Download and resize Discord avatar to 100x100.

    Args:
        member: Discord member

    Returns:
        PIL Image object (100x100 pixels)
    """
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(str(avatar_url)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    avatar = Image.open(io.BytesIO(data))
                    avatar = avatar.resize((100, 100), Image.Resampling.LANCZOS)
                    return avatar
    except Exception as e:
        print_error_log(f"_download_avatar: Failed to download avatar for {member.display_name}: {e}")

    # Fallback: gray placeholder
    return Image.new("RGB", (100, 100), "#23272A")
