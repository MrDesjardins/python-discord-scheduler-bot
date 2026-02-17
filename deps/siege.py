"""Information about Siege"""

from typing import List, Mapping, Optional, Union
import discord

from deps.models import ActivityTransition, SiegeActivityAggregation
from deps.mybot import MyBot
from deps.log import print_log

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


def get_user_rank_siege(user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    """
    if user is None:
        return "Copper"

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
    print_log(f"Checking activities for member {member.display_name}")
    for activity in member.activities:
        if isinstance(activity, discord.Activity):
            print_log(
                f"Activity found: {activity.name}, Details: {activity.details if activity.details else 'No details'}, State: {activity.state if activity.state else 'No state'}, Party: {activity.party if activity.party else 'No party'}, State: {activity.state if activity.state else 'No state'}, Type: {activity.type}"
            )
            if activity.name == "Rainbow Six Siege" or activity.name == "Tom Clancy's Rainbow Six Siege X":
                return activity
    return None


def get_aggregation_siege_activity(
    dict_users_activities: Mapping[int, Union[ActivityTransition, None]],
) -> SiegeActivityAggregation:
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
    looking_ranked_match = 0

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
        # Detect ranked match START: transition from "Looking for RANKED match" to "RANKED match"
        # This indicates the queue popped and the match actually started
        if (
            bef is not None
            and bef.startswith("Looking for RANKED match")
            and aft is not None
            and aft.startswith("RANKED match")
        ):
            looking_ranked_match += 1

    return SiegeActivityAggregation(
        count_in_menu,
        game_not_started,
        user_leaving,
        warming_up,
        done_warming_up_waiting_in_menu,
        done_match_waiting_in_menu,
        playing_rank,
        playing_standard,
        looking_ranked_match,
    )


def get_statscc_activity(member: discord.Member) -> Optional[discord.Activity]:
    """
    Get the stats.cc activity from the member's activities.
    stats.cc is a companion app that reports Siege activity via Discord Rich Presence
    with different detail string formats than the native game.
    """
    for activity in member.activities:
        if isinstance(activity, discord.Activity):
            if activity.name == "stats.cc":
                return activity
    return None


def get_any_siege_activity(member: discord.Member) -> Optional[discord.Activity]:
    """
    Get Siege activity from either native game or stats.cc.
    Tries native Siege first, then falls back to stats.cc.
    """
    return get_siege_activity(member) or get_statscc_activity(member)


_STATSCC_MAIN_MENU = ("At the Main Menu", "Idle - at Main Menu")

# Known stats.cc detail strings that are distinct from native Siege detail strings
_STATSCC_DETAILS = frozenset(
    [
        "At the Main Menu",
        "In Queue",
        "Match Started",
    ]
)

# Prefixes used by stats.cc for in-match details (e.g. "Picking Operators: Ranked on Villa")
_STATSCC_MATCH_PREFIXES = (
    "Picking Operators:",
    "Banning Operators:",
    "Prep Phase:",
    "In round:",
    "Match Ending:",
)

_STATSCC_WARMUP = ("SHOOTING RANGE", "Map Training", "ARCADE", "VERSUS AI")


def _is_statscc_detail(detail: Optional[str]) -> bool:
    """Return True if the detail string matches stats.cc patterns (distinct from native Siege patterns)."""
    if detail is None:
        return False
    if detail in _STATSCC_DETAILS:
        return True
    for prefix in _STATSCC_MATCH_PREFIXES:
        if detail.startswith(prefix):
            return True
    # stats.cc also uses bare "Ranked" and "Standard" as detail strings
    if detail in ("Ranked", "Standard"):
        return True
    return False


def _is_statscc_ranked_detail(detail: Optional[str]) -> bool:
    """Return True if the stats.cc detail indicates a ranked match."""
    if detail is None:
        return False
    if detail == "Ranked":
        return True
    if "Ranked" in detail and any(detail.startswith(p) for p in _STATSCC_MATCH_PREFIXES):
        return True
    return False


def _is_statscc_standard_detail(detail: Optional[str]) -> bool:
    """Return True if the stats.cc detail indicates a standard match."""
    if detail is None:
        return False
    if detail == "Standard":
        return True
    if "Standard" in detail and any(detail.startswith(p) for p in _STATSCC_MATCH_PREFIXES):
        return True
    return False


def _is_statscc_warmup(detail: Optional[str]) -> bool:
    """Return True if the stats.cc detail indicates a warmup activity."""
    if detail is None:
        return False

    return any(detail.startswith(p) for p in _STATSCC_WARMUP)


def get_aggregation_statscc_activity(
    dict_users_activities: Mapping[int, Union[ActivityTransition, None]],
) -> SiegeActivityAggregation:
    """
    From the before and after activity detail for stats.cc, get the count of users
    from different transitions to determine if we send a message or not.
    stats.cc detail strings:
        "At the Main Menu"
        "In Queue"
        "Match Started"
        "Ranked"
        "Picking Operators: Ranked on <map>"
        "Banning Operators: Ranked on <map>"
        "Prep Phase: Ranked on <map>"
        "In round: Ranked on <map>"
        "Match Ending: Ranked on <map>"
    """
    count_in_menu = 0
    game_not_started = 0
    user_leaving = 0
    warming_up = 0
    done_warming_up_waiting_in_menu = 0
    done_match_waiting_in_menu = 0
    playing_rank = 0
    playing_standard = 0
    looking_ranked_match = 0

    for user_id, activity_before_after in dict_users_activities.items():
        if activity_before_after is None:
            continue
        bef = activity_before_after.before
        aft = activity_before_after.after
        if bef is None and aft is None:
            game_not_started += 1
        if aft == "At the Main Menu":
            count_in_menu += 1
        if bef is not None and aft is None:
            user_leaving += 1
        # Ranked match done, back to menu
        if _is_statscc_ranked_detail(bef) and aft in _STATSCC_MAIN_MENU:
            done_match_waiting_in_menu += 1
        # Standard match done, back to menu
        if _is_statscc_standard_detail(bef) and aft in _STATSCC_MAIN_MENU:
            done_match_waiting_in_menu += 1

        # Warming up done
        if _is_statscc_warmup(bef) and aft in _STATSCC_MAIN_MENU:
            done_warming_up_waiting_in_menu += 1

        # Currently in a ranked match
        if _is_statscc_ranked_detail(aft):
            playing_rank += 1
        # Currently in a standard match
        if _is_statscc_standard_detail(aft):
            playing_standard += 1
        # Detect ranked match START: transition TO "Picking Operators: Ranked on..."
        # Only count as NEW match if coming from non-match states (queue, menu)
        # NOT from match states (Match Ending, In Round, etc.) which indicate new round
        if aft is not None and aft.startswith("Picking Operators: Ranked"):
            # Check if user was NOT already in a ranked match (new round vs new match)
            if bef is None or not (
                bef.startswith("Picking Operators: Ranked")
                or bef.startswith("In Round: Ranked")
                or bef.startswith("Match Ending: Ranked")
                or bef.startswith("Ranked on")  # Generic ranked state between rounds
                or bef.startswith("Banning Operators: Ranked")
                or bef.startswith("Prep Phase: Ranked")
            ):
                looking_ranked_match += 1
        # NOTE: We don't count "In Queue" as looking_ranked_match for stats.cc
        # because stats.cc doesn't specify which mode (ranked/standard/deathmatch/etc.)

    return SiegeActivityAggregation(
        count_in_menu,
        game_not_started,
        user_leaving,
        warming_up,
        done_warming_up_waiting_in_menu,
        done_match_waiting_in_menu,
        playing_rank,
        playing_standard,
        looking_ranked_match,
    )


def get_aggregation_all_activities(
    dict_users_activities: Mapping[int, Union[ActivityTransition, None]],
) -> SiegeActivityAggregation:
    """
    Combined aggregation that handles both native Siege and stats.cc detail strings.
    For each user, determines if the details are stats.cc format or Siege format
    and applies the appropriate logic, accumulating into a single SiegeActivityAggregation.
    """
    siege_users: dict[int, Union[ActivityTransition, None]] = {}
    statscc_users: dict[int, Union[ActivityTransition, None]] = {}

    for user_id, activity_before_after in dict_users_activities.items():
        if activity_before_after is None:
            siege_users[user_id] = None
            continue
        # Check if either detail string is a stats.cc pattern
        if _is_statscc_detail(activity_before_after.before) or _is_statscc_detail(activity_before_after.after):
            statscc_users[user_id] = activity_before_after
        else:
            siege_users[user_id] = activity_before_after

    siege_agg = get_aggregation_siege_activity(siege_users)
    statscc_agg = get_aggregation_statscc_activity(statscc_users)

    return SiegeActivityAggregation(
        siege_agg.count_in_menu + statscc_agg.count_in_menu,
        siege_agg.game_not_started + statscc_agg.game_not_started,
        siege_agg.user_leaving + statscc_agg.user_leaving,
        siege_agg.warming_up + statscc_agg.warming_up,
        siege_agg.done_warming_up_waiting_in_menu + statscc_agg.done_warming_up_waiting_in_menu,
        siege_agg.done_match_waiting_in_menu + statscc_agg.done_match_waiting_in_menu,
        siege_agg.playing_rank + statscc_agg.playing_rank,
        siege_agg.playing_standard + statscc_agg.playing_standard,
        siege_agg.looking_ranked_match + statscc_agg.looking_ranked_match,
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
