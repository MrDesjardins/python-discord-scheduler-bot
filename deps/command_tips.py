"""Daily command spotlights for the configured general channel."""

from datetime import datetime
from zoneinfo import ZoneInfo

import discord

from deps.cache import ALWAYS_TTL, get_cache, set_cache
from deps.data_access import data_access_get_main_text_channel_id
from deps.values import (
    COMMAND_ACTIVE_RANK_USER_ACCOUNT,
    COMMAND_CUSTOM_GAME_LFG,
    COMMAND_CUSTOM_GAME_MAKE_TEAM,
    COMMAND_CUSTOM_GAME_SEE_SUBSCRIPTIONS,
    COMMAND_CUSTOM_GAME_SUBSCRIBE,
    COMMAND_CUSTOM_GAME_UNSUBSCRIBE,
    COMMAND_FOLLOW_USER,
    COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL,
    COMMAND_GET_USER_TIME_ZONE,
    COMMAND_INIT_USER,
    COMMAND_LFG,
    COMMAND_MAX_RANK_USER_ACCOUNT,
    COMMAND_MY_STREAK,
    COMMAND_PRIVATE_CHANNEL,
    COMMAND_PRIVATE_CHANNEL_INVITE,
    COMMAND_SCHEDULE_ADD,
    COMMAND_SCHEDULE_REMOVE,
    COMMAND_SCHEDULE_SEE,
    COMMAND_SEE_FOLLOWED_USERS,
    COMMAND_SET_USER_TIME_ZONE,
    COMMAND_TOURNAMENT_REGISTER_TOURNAMENT,
    COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT,
    COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT,
    COMMAND_UNFOLLOW_USER,
)

COMMAND_TIPS = (
    (
        COMMAND_INIT_USER,
        "Set up your profile and link your Ubisoft account.",
        "Start here so the bot knows which Siege player you are.",
    ),
    (
        COMMAND_LFG,
        "Find players in your current voice channel.",
        "Join a voice channel, then use this when you want more teammates.",
    ),
    (COMMAND_SCHEDULE_ADD, "Add or update your availability schedule.", "Let the server know when you plan to play."),
    (COMMAND_SCHEDULE_REMOVE, "Remove your schedule.", "Plans changed? Clear your availability so others know."),
    (COMMAND_SCHEDULE_SEE, "View your current schedule.", "Check the availability you have already shared."),
    (COMMAND_SET_USER_TIME_ZONE, "Set your time zone.", "Set this before sharing your availability."),
    (
        COMMAND_GET_USER_TIME_ZONE,
        "View a member's time zone.",
        "Check a teammate's local time before planning a session.",
    ),
    (
        COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL,
        "View the time zones of members in a voice channel.",
        "Find a time that works for everyone in the squad.",
    ),
    (
        COMMAND_MAX_RANK_USER_ACCOUNT,
        "Set the Ubisoft account used to track your highest rank.",
        "Choose the account that represents your peak rank.",
    ),
    (
        COMMAND_ACTIVE_RANK_USER_ACCOUNT,
        "Set the Ubisoft account used for live stats tracking.",
        "Switch this when you start playing on a different account.",
    ),
    (
        COMMAND_TOURNAMENT_REGISTER_TOURNAMENT,
        "Register for a tournament.",
        "Use this when tournament registration is open.",
    ),
    (
        COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT,
        "Report a tournament loss and score.",
        "Finished a tournament match? The losing side can report the result.",
    ),
    (
        COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT,
        "View or regenerate the tournament bracket.",
        "Check your next matchup and follow the tournament's progress.",
    ),
    (COMMAND_MY_STREAK, "View your daily play streak.", "See how your streak is coming along."),
    (COMMAND_PRIVATE_CHANNEL, "Create a private voice channel.", "Make a space for your squad."),
    (
        COMMAND_PRIVATE_CHANNEL_INVITE,
        "Invite a member to your private voice channel.",
        "Bring a teammate into the private channel you created.",
    ),
    (COMMAND_FOLLOW_USER, "Follow a server member.", "Keep up with the teammates you like playing with."),
    (COMMAND_UNFOLLOW_USER, "Stop following a member.", "Update who you follow whenever you like."),
    (COMMAND_SEE_FOLLOWED_USERS, "View the members you follow.", "Check your current follow list."),
    (
        COMMAND_CUSTOM_GAME_SUBSCRIBE,
        "Subscribe to custom-game notifications.",
        "Sign up if you want to hear when a custom game needs players.",
    ),
    (
        COMMAND_CUSTOM_GAME_UNSUBSCRIBE,
        "Unsubscribe from custom-game notifications.",
        "Take a break from custom-game notifications.",
    ),
    (
        COMMAND_CUSTOM_GAME_SEE_SUBSCRIPTIONS,
        "View custom-game subscribers.",
        "See who is interested in joining custom games.",
    ),
    (
        COMMAND_CUSTOM_GAME_LFG,
        "Notify subscribed members that a custom game is available.",
        "Use this when you are gathering players for a custom lobby.",
    ),
    (
        COMMAND_CUSTOM_GAME_MAKE_TEAM,
        "Create teams and select a map for a full 10-man game.",
        "Gather all 10 players before making teams.",
    ),
)


def build_command_tip(index: int) -> discord.Embed:
    """Build a compact, consistent command lesson."""
    command, description, hint = COMMAND_TIPS[index % len(COMMAND_TIPS)]
    embed = discord.Embed(
        title="\U0001f4a1 Command of the day",
        description=f"## /{command}\n{description}",
        color=0x5865F2,
    )
    embed.add_field(name="When to use it", value=hint, inline=False)
    embed.add_field(name="Give it a try", value=f"Type `/{command}` in chat and follow the prompts.", inline=False)
    embed.set_footer(text=f"Tip {index % len(COMMAND_TIPS) + 1} of {len(COMMAND_TIPS)} \u2022 A new command every day")
    return embed


async def send_daily_command_tip(guild: discord.Guild) -> None:
    """Send one lesson per Pacific calendar day, retaining rotation across restarts."""
    channel_id = await data_access_get_main_text_channel_id(guild.id)
    if not channel_id:
        return
    channel = guild.get_channel(channel_id)
    if channel is None:
        return
    key = f"DailyCommandTip:{guild.id}"
    state = await get_cache(False, key) or {}
    today = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    # Persist the day to prevent duplicate lessons after a restart or cog reload.
    if state.get("date") == today:
        return
    index = state.get("next_index", 0)
    await channel.send(embed=build_command_tip(index), allowed_mentions=discord.AllowedMentions.none())
    # Advance only after sending so missing permissions do not skip a lesson.
    set_cache(False, key, {"date": today, "next_index": (index + 1) % len(COMMAND_TIPS)}, ALWAYS_TTL)
