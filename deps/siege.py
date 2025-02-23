""" Information about Siege """

from typing import List, Mapping, Optional
import discord

from deps.models import ActivityTransition, SiegeActivityAggregation
from deps.mybot import MyBot

siege_ranks = [
    "Champion",
    "Diamond",
    "Emerald",
    "Platinum",
    "Gold",
    "Silver",
    "Bronze",
    "Copper",
]


def get_color_for_rank(member: discord.Member) -> int:
    """Return a color per rank"""
    color_map = {
        "Champion": 0xFFC0CB,  # Pink
        "Diamond": 0x800080,  # Purple
        "Emerald": 0x008000,  # Green
        "Platinum": 0x00FFFF,  # Cyan
        "Gold": 0xFFFF00,  # Yellow
        "Silver": 0x808080,  # Gray
        "Bronze": 0xD2691E,  # Dark Orange
        "Copper": 0x8B0000,  # Dark Red
    }
    for role in member.roles:
        if role.name in siege_ranks:
            return color_map.get(role.name, 0x8B0000)

    return color_map.get("Copper", 0x8B0000)


def get_user_rank_siege(guild_emoji: dict[str, str], user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    """
    if user is None:
        return get_guild_rank_emoji(guild_emoji, "Copper")

    for role in user.roles:
        if role.name in siege_ranks:
            return role.name
    return "Copper"


def get_user_rank_emoji(guild_emoji: dict[str, str], user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    The function assumes a specific 8 roles with 8 emojis which might not be the case for your server
    """
    if guild_emoji is None:
        # Should never happen
        guild_emoji = {}

    if user is None:
        return get_guild_rank_emoji(guild_emoji, "Copper")

    for role in user.roles:
        if role.name in siege_ranks:
            return get_guild_rank_emoji(guild_emoji, role.name)

    return get_guild_rank_emoji(guild_emoji, "Copper")


def get_guild_rank_emoji(guild_emoji: dict[str, str], emoji_name: str) -> str:
    """
    Extract the full emoji code for Discord to use from the emoji name and the guild emoji dictionary
    which contain the unique ID for the emoji
    """
    if guild_emoji is None:
        # Should never happen
        guild_emoji = {}

    if emoji_name in siege_ranks:
        if emoji_name in guild_emoji:
            emoji_id = guild_emoji[emoji_name]
            return f"<:{emoji_name}:{emoji_id}>"

    return f"<:Copper:{guild_emoji['Copper']}>" if "Copper" in guild_emoji else "N/A"


def get_siege_activity(member: discord.Member) -> Optional[discord.Activity]:
    """
    Get the siege activity from the member's activities
    The activity.detail will give information about where in the game the user is (e.g. in a match)
    """
    for activity in member.activities:
        if activity.name == "Rainbow Six Siege":
            return activity
    return None


def get_aggregation_siege_activity(dict_users_activities: Mapping[int, ActivityTransition]) -> SiegeActivityAggregation:
    """
    From the before and after activity detail, get the count of user from different transition to determine
    if we send a message or not
    Possible transition:
        CUSTOM_GAME match XXXXX
        RANKED match XXXXX
        Playing Map Training
        STANDARD match
        Looking for XXXXX match
        ARCADE match XXXXX
        VERSUS AI match XXXXX
        QUICK MATCH match XXXXX
    """
    count_in_menu = 0
    game_not_started = 0
    user_leaving = 0
    warming_up = 0
    done_warming_up_waiting_in_menu = 0
    done_match_waiting_in_menu = 0
    playing_rank = 0
    playing_standard = 0

    for user_id, activity_before_after in dict_users_activities.items():
        if activity_before_after is None:
            continue
        bef = activity_before_after.before
        aft = activity_before_after.after
        if bef is None and aft is None:
            game_not_started += 1
        if aft == "in MENU":
            count_in_menu += 1
        if aft is not None and (
            aft == "Playing Map Training"
            or aft == "Playing SHOOTING RANGE"
            or aft.startswith("ARCADE")
            or aft.startswith("VERSUS AI")
        ):
            warming_up += 1
        if bef is not None and aft is None:
            user_leaving += 1
        if (
            bef is not None
            and (
                bef == "Playing SHOOTING RANGE"
                or bef == "Playing Map Training"
                or bef.startswith("ARCADE")
                or bef.startswith("VERSUS AI")
            )
        ) and aft == "in MENU":
            done_warming_up_waiting_in_menu += 1
        if (
            bef is not None
            and (bef.startswith("RANKED match") or bef.startswith("STANDARD match"))
            and aft == "in MENU"
        ):
            done_match_waiting_in_menu += 1
        if aft is not None and aft.startswith("RANKED match"):
            playing_rank += 1
        if aft is not None and aft.startswith("STANDARD match"):
            playing_standard += 1

    return SiegeActivityAggregation(
        count_in_menu,
        game_not_started,
        user_leaving,
        warming_up,
        done_warming_up_waiting_in_menu,
        done_match_waiting_in_menu,
        playing_rank,
        playing_standard,
    )


def get_list_users_with_rank(bot: MyBot, members: List[discord.Member], guild_id: int) -> str:
    """
    Return a list of users with their rank in a voice channel
    """
    list_users = ""
    for member in members:
        rank = get_user_rank_emoji(bot.guild_emoji.get(guild_id, {}), member)
        list_users += f"{rank} {member.mention}, "
    list_users = list_users[:-2]
    return list_users
