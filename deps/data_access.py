"""Access to the data is done throught this data access"""

from typing import Any, List, Optional, Union
from datetime import datetime, timedelta, timezone
import asyncio
import random
from time import sleep
import discord
from deps.browser_context_manager import BrowserContextManager
from deps.browser_exceptions import BrowserException
from deps.bot_singleton import BotSingleton
from deps.cache import (
    ALWAYS_TTL,
    ONE_DAY_TTL,
    ONE_HOUR_TTL,
    ONE_MONTH_TTL,
    THREE_DAY_TTL,
    TWO_HOUR_TTL,
    get_cache,
    remove_cache,
    reset_cache_by_prefixes,
    set_cache,
)
from deps.cache_data_access import get_value_with_presence
from deps.models import ActivityTransition, SimpleUser, SimpleUserHour, UserQueueForStats
from deps.log import print_error_log, print_log, print_warning_log
from deps.functions_date import get_now_eastern
from deps.system_database import database_manager

KEY_DAILY_MSG = "DailyMessageSentInChannel"
KEY_REACTION_USERS = "ReactionUsersV2"
KEY_GUILD_USERS_AUTO_SCHEDULE = "GuildUsersAutoScheduleByDay"
KEY_GUILD_SCHEDULE_TEXT_CHANNEL = "GuildAdminConfigTextChannel"
KEY_GUILD_USERNAME_TEXT_CHANNEL = "GuildAdminConfigUserNameTextChannel"
KEY_GUILD_GAMING_SESSION_TEXT_CHANNEL = "GuildAdminConfigGamingSessionTextChannel"
KEY_GUILD_NEW_USER_TEXT_CHANNEL = "GuildAdminConfigNewUserTextChannel"
KEY_GUILD_VOICE_CHANNELS = "GuildAdminConfigVoiceChannels"
KEY_MESSAGE = "Message"
KEY_USER = "User"
KEY_GUILD = "Guild"
KEY_MEMBER = "Member"
KEY_CHANNEL = "Channel"
KEY_GUILD_BOT_VOICE_FIRST_USER = "GuildBotVoiceFirstUser"
KEY_R6TRACKER = "R6Tracker"
KEY_R6TRACKER_CURRENT_SEASON_RANK = "R6TrackerCurrentSeasonRank"
KEY_GAMING_SESSION_LAST_ACTIVITY = "GamingSessionLastActivity"
KEY_QUEUE_USER_STATS = "QueueUserStats"
KEY_GUILD_TOURNAMENT_TEXT_CHANNEL = "GuildAdminConfigTournamentTextChannel"
KEY_GUILD_MAIN_TEXT_CHANNEL = "GuildMainSiegeTextChannel"
KEY_GUILD_AI_TEXT_CHANNEL = "GuildAITextChannel"
KEY_GUILD_ANALYTICS_REPORT_TEXT_CHANNEL = "GuildAnalyticsReportTextChannel"
KEY_GUILD_ANALYTICS_REPORT_SENT = "GuildAnalyticsReportSent"
KEY_GUILD_VOICE_CHANNEL_LIST_USER = "GuildVoiceChannelListUser"
KEY_GUILD_LAST_BOT_MESSAGE_MAIN_TEXT_CHANNEL = "GuildLastBotMessageMainTextChannel"
KEY_AI_COUNT = "AI_daily_Count"
KEY_GUILD_AI_CONTEXT = "GuildAIPermanentContext"
KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_LOBBY = "GuildCustomGameVoiceChannelLobby"
KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM1 = "GuildCustomGameVoiceChannelTeam1"
KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM2 = "GuildCustomGameVoiceChannelTeam2"
KEY_LAST_MATCH_START_GIF = "LastMatchStartGif"
KEY_PENDING_MATCH_START_GIF = "PendingMatchStartGif"
KEY_GUILD_PRIVATE_CHANNEL_CATEGORY = "GuildPrivateChannelCategory"
KEY_GUILD_ACTIVE_PRIVATE_CHANNEL = "GuildActivePrivateChannel"


async def data_access_get_guild(guild_id: int) -> Union[discord.Guild, None]:
    """Get the guild by the given guild"""

    async def fetch():
        return BotSingleton().bot.get_guild(guild_id)

    return await get_cache(True, f"{KEY_GUILD}:{guild_id}", fetch)


async def data_access_get_message(guild_id: int, channel_id: int, message_id: int) -> Union[discord.Message, None]:
    """Get the message by the given guild, channel and message id"""

    async def fetch():
        try:
            channel = await data_access_get_channel(channel_id)
            if channel is None:
                print_log(f"data_access_get_message: Channel {channel_id} not found for guild {guild_id}")
                return None
            return await channel.fetch_message(message_id)
        except discord.errors.HTTPException:
            # Can only occurs if we move the database from prod to dev (message id are not the same)
            return None

    return await get_cache(True, f"{KEY_MESSAGE}:{guild_id}:{channel_id}:{message_id}", fetch)


async def data_access_get_user(guild_id: int, user_id: int) -> Union[discord.User, None]:
    """Get the user by the given guild and user id"""

    async def fetch():
        return await BotSingleton().bot.fetch_user(user_id)

    return await get_cache(True, f"{KEY_USER}:{guild_id}:{user_id}", fetch)


async def data_access_get_member(guild_id: int, user_id: int) -> Union[discord.Member, None]:
    """Get the member by the given guild and user id"""
    if user_id is None:
        return None

    async def fetch() -> Union[discord.Member, None]:
        guild: Optional[discord.Guild] = await data_access_get_guild(guild_id)
        if guild is None:
            return None
        try:
            result = await guild.fetch_member(user_id)
            return result
        except discord.errors.NotFound:
            return None

    return await get_cache(True, f"{KEY_MEMBER}:{guild_id}:{user_id}", fetch)


async def data_access_get_channel(channel_id: int) -> Union[discord.TextChannel, None]:
    """Get the channel by the given channel id"""

    async def fetch() -> Any:
        return BotSingleton().bot.get_channel(channel_id)

    return await get_cache(True, f"{KEY_CHANNEL}:{channel_id}", fetch)


async def data_access_get_reaction_message(
    guild_id: int, channel_id: int, message_id: int
) -> Union[dict[str, list[SimpleUser]], None]:
    """Get the users reactions for a specific mesage"""
    key = f"{KEY_REACTION_USERS}:{guild_id}:{channel_id}:{message_id}"
    return await get_cache(False, key)


def data_access_set_reaction_message(
    guild_id: int, channel_id: int, message_id: int, message_votes: dict[str, list[SimpleUser]]
) -> None:
    """
    Set the reaction for a specific message
    We store already the user_activity, the manual ones are not needed above 1 month since we are not allowing people after 24h (give more leeway)
    """
    key = f"{KEY_REACTION_USERS}:{guild_id}:{channel_id}:{message_id}"
    set_cache(False, key, message_votes, ONE_MONTH_TTL)


async def data_access_get_users_auto_schedule(
    guild_id: int, day_of_week_number: int
) -> Union[List[SimpleUserHour], None]:
    """Get users schedule for a specific day of the week"""
    return await get_cache(False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}:{day_of_week_number}")


def data_access_set_users_auto_schedule(guild_id: int, day_of_week_number: int, users: List[SimpleUserHour]) -> None:
    """Configure the users schedule for a specific day of the week"""
    set_cache(
        False,
        f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}:{day_of_week_number}",
        users,
        ALWAYS_TTL,
    )


async def data_access_get_guild_schedule_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_SCHEDULE_TEXT_CHANNEL}:{guild_id}")


def data_access_set_guild_schedule_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_SCHEDULE_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_guild_voice_channel_ids(
    guild_id: int,
) -> Union[List[int], None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_VOICE_CHANNELS}:{guild_id}")


def data_access_set_guild_voice_channel_ids(guild_id: int, channel_ids: Union[List[int], None]) -> None:
    """Set the voice channels (many) that the bot will send voice and watch"""
    if channel_ids is None:
        remove_cache(False, f"{KEY_GUILD_VOICE_CHANNELS}:{guild_id}")
    else:
        set_cache(False, f"{KEY_GUILD_VOICE_CHANNELS}:{guild_id}", channel_ids, ALWAYS_TTL)


def data_access_reset_guild_cache(guild_id: int) -> None:
    """Clear the cache for the given guild"""
    prefixes = [
        f"{KEY_DAILY_MSG}:{guild_id}",
        f"{KEY_REACTION_USERS}:{guild_id}",
        f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}",
        f"{KEY_GUILD_VOICE_CHANNELS}:{guild_id}",
        f"{KEY_GUILD_SCHEDULE_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_GUILD_USERNAME_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_GUILD_GAMING_SESSION_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_GUILD_NEW_USER_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_GUILD_BOT_VOICE_FIRST_USER}:{guild_id}",
        f"{KEY_GUILD_TOURNAMENT_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_GUILD_ANALYTICS_REPORT_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_GUILD_ANALYTICS_REPORT_SENT}:{guild_id}",
        f"{KEY_MESSAGE}:{guild_id}",
        f"{KEY_USER}:{guild_id}",
        f"{KEY_GUILD}:{guild_id}",
        f"{KEY_MEMBER}:{guild_id}",
        f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_LOBBY}:{guild_id}",
        f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM1}:{guild_id}",
        f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM2}:{guild_id}",
    ]
    reset_cache_by_prefixes(prefixes)


async def data_access_get_bot_voice_first_user(guild_id: int) -> bool:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_BOT_VOICE_FIRST_USER}:{guild_id}", lambda: False)


def data_access_set_bot_voice_first_user(guild_id: int, enabled: bool) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_BOT_VOICE_FIRST_USER}:{guild_id}", enabled, ALWAYS_TTL)


def _download_max_rank_sync(ubisoft_user_name: str) -> tuple[str, int]:
    with BrowserContextManager(ubisoft_user_name) as context:
        return context.download_max_rank(ubisoft_user_name)


def _download_current_season_rank_sync(ubisoft_user_name: str) -> tuple[str, int]:
    with BrowserContextManager(ubisoft_user_name) as context:
        return context.download_current_season_rank(ubisoft_user_name)


async def data_access_get_r6tracker_max_rank(ubisoft_user_name: str, force_fetch: bool = False) -> tuple[str, int]:
    """
    Get from R6 Tracker website the max rank for the user
    """
    return await asyncio.to_thread(_download_max_rank_sync, ubisoft_user_name)
    # if force_fetch:
    #     remove_cache(True, f"{KEY_R6TRACKER}:{ubisoft_user_name}")

    # return await get_cache(True, f"{KEY_R6TRACKER}:{ubisoft_user_name}", fetch, ttl_in_seconds=ONE_HOUR_TTL)


def _current_season_rank_cache_key(ubisoft_user_name: str) -> str:
    return f"{KEY_R6TRACKER_CURRENT_SEASON_RANK}:{ubisoft_user_name.strip().lower()}"


async def data_access_get_r6tracker_current_season_rank(
    ubisoft_user_name: str, force_fetch: bool = False
) -> tuple[str, int]:
    """
    Get from R6 Tracker website the user's current ranked season rank.
    """
    cache_key = _current_season_rank_cache_key(ubisoft_user_name)
    if force_fetch:
        remove_cache(False, cache_key)

    async def fetch() -> tuple[str, int]:
        return await asyncio.to_thread(_download_current_season_rank_sync, ubisoft_user_name)

    return await get_cache(False, cache_key, fetch, ttl_in_seconds=TWO_HOUR_TTL)


def _download_current_season_ranks_sync(ubisoft_user_names: List[str]) -> dict[str, tuple[str, int]]:
    """Download the current season rank for many users while opening a single browser session."""
    ranks: dict[str, tuple[str, int]] = {}
    with BrowserContextManager(ubisoft_user_names[0]) as context:
        for i, ubisoft_user_name in enumerate(ubisoft_user_names):
            try:
                ranks[ubisoft_user_name] = context.download_current_season_rank(ubisoft_user_name)
            except BrowserException as e:
                print_warning_log(
                    f"_download_current_season_ranks_sync: Could not fetch rank for {ubisoft_user_name}: {e}"
                )
            if i < len(ubisoft_user_names) - 1:
                sleep(random.uniform(3, 12))  # Sleep few seconds between each request
    return ranks


async def data_access_prefetch_r6tracker_current_season_ranks(ubisoft_user_names: List[str]) -> None:
    """
    Warm the current season rank cache for many users using a single browser session
    instead of opening one browser per user. Users already cached are skipped; users
    whose fetch fails are left uncached so the per-user fallback can retry them.
    """
    names_to_fetch: List[str] = []
    seen: set[str] = set()
    for ubisoft_user_name in ubisoft_user_names:
        normalized = ubisoft_user_name.strip().lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        if await get_cache(False, _current_season_rank_cache_key(ubisoft_user_name)) is None:
            names_to_fetch.append(ubisoft_user_name)

    if len(names_to_fetch) == 0:
        return

    try:
        ranks = await asyncio.to_thread(_download_current_season_ranks_sync, names_to_fetch)
    except Exception as e:
        print_warning_log(f"data_access_prefetch_r6tracker_current_season_ranks: Unable to prefetch ranks in bulk: {e}")
        return

    for ubisoft_user_name, rank in ranks.items():
        set_cache(False, _current_season_rank_cache_key(ubisoft_user_name), rank, TWO_HOUR_TTL)


async def data_access_get_guild_username_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_USERNAME_TEXT_CHANNEL}:{guild_id}")


def data_access_set_guild_username_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_USERNAME_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_gaming_session_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given guild id"""
    return await get_cache(False, f"{KEY_GUILD_GAMING_SESSION_TEXT_CHANNEL}:{guild_id}")


def data_access_set_gaming_session_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_GAMING_SESSION_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_gaming_session_last_activity(member_id: int, guild_id: int) -> Optional[datetime]:
    """Get the last activity for a given user in a guild"""
    return await get_cache(True, f"{KEY_GAMING_SESSION_LAST_ACTIVITY}:{guild_id}:{member_id}")


async def data_access_set_gaming_session_last_activity(member_id: int, guild_id: int, time: datetime) -> None:
    """Get the last activity for a given user in a guild"""
    set_cache(True, f"{KEY_GAMING_SESSION_LAST_ACTIVITY}:{guild_id}:{member_id}", time, ONE_DAY_TTL)


async def data_access_get_new_user_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given guild id"""
    return await get_cache(False, f"{KEY_GUILD_NEW_USER_TEXT_CHANNEL}:{guild_id}")


def data_access_set_new_user_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_NEW_USER_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


lock_member_stats = asyncio.Lock()
lock_voice_user_list = asyncio.Lock()


async def data_access_get_list_member_stats() -> Optional[List[UserQueueForStats]]:
    """Get the list of all the members that are in the queue to get their stats"""
    return await get_cache(True, f"{KEY_QUEUE_USER_STATS}")


def _evict_stale_member_stats(list_users: List[UserQueueForStats]) -> List[UserQueueForStats]:
    """
    Remove all the user where the time_queue is over 1 hour.
    Evicted users never got their stats posted, so log them loudly instead of dropping silently.
    """
    current_time = datetime.now(timezone.utc)
    delta = current_time - timedelta(hours=1)
    fresh_users = [user_in_list for user_in_list in list_users if user_in_list.time_queue > delta]
    evicted_users = [user_in_list for user_in_list in list_users if user_in_list.time_queue <= delta]
    if len(evicted_users) > 0:
        names = ", ".join(
            f"{user_in_list.user_info.display_name} (queued at {user_in_list.time_queue.isoformat()}, "
            f"{user_in_list.attempts} failed attempts)"
            for user_in_list in evicted_users
        )
        print_warning_log(
            f"_evict_stale_member_stats: Dropping {len(evicted_users)} stats queue entry(ies) older than "
            f"1 hour without posting their stats: {names}"
        )
    return fresh_users


async def data_access_add_list_member_stats(user: UserQueueForStats) -> None:
    """Add a user to the list of all the members that are in the queue to get their stats"""
    async with lock_member_stats:
        list_users = await data_access_get_list_member_stats()
        if list_users is None:
            list_users = []

        list_users = _evict_stale_member_stats(list_users)

        # Search to see if the user id is already in the list (maybe few minutes ago it was added to the list)
        for user_in_list in list_users:
            if user_in_list.user_info.id == user.user_info.id and user_in_list.guild_id == user.guild_id:
                return
        list_users.append(user)
        # Lock to make sure that the list is not updated by multiple threads

        set_cache(True, f"{KEY_QUEUE_USER_STATS}", list_users, ONE_DAY_TTL)
    # Lock is released here


async def data_acess_remove_list_member_stats(user_queued_for_stats: UserQueueForStats) -> None:
    """Remove a user from the list of all the members that are in the queue to get their stats"""
    async with lock_member_stats:
        list_users = await data_access_get_list_member_stats()
        if list_users is None:
            return

        list_users = _evict_stale_member_stats(list_users)

        # Search to see if the user id is already in the list (maybe few minutes ago it was added to the list)
        for user_in_list in list_users:
            if (
                user_in_list.user_info.id == user_queued_for_stats.user_info.id
                and user_in_list.guild_id == user_queued_for_stats.guild_id
            ):
                list_users.remove(user_in_list)
                break  # Break because we know maximum one entry per user
        set_cache(True, f"{KEY_QUEUE_USER_STATS}", list_users, ONE_DAY_TTL)
    # Lock is released here


async def data_access_increment_member_stats_attempts(
    attempted_users: List[UserQueueForStats], max_attempts: int
) -> None:
    """
    Increment the failed-attempt counter for the attempted users that are still in the
    queue (meaning their stats were not posted this cycle). Entries reaching max_attempts
    are removed so a user whose fetch always fails cannot clog the queue forever.
    """
    async with lock_member_stats:
        list_users = await data_access_get_list_member_stats()
        if list_users is None or len(list_users) == 0:
            return

        attempted_keys = {(user.user_info.id, user.guild_id) for user in attempted_users}
        remaining_users: List[UserQueueForStats] = []
        for user_in_list in list_users:
            if (user_in_list.user_info.id, user_in_list.guild_id) in attempted_keys:
                user_in_list.attempts += 1
                if user_in_list.attempts >= max_attempts:
                    print_error_log(
                        f"data_access_increment_member_stats_attempts: Giving up on stats for "
                        f"{user_in_list.user_info.display_name} after {user_in_list.attempts} failed attempts"
                    )
                    continue
            remaining_users.append(user_in_list)
        set_cache(True, f"{KEY_QUEUE_USER_STATS}", remaining_users, ONE_DAY_TTL)
    # Lock is released here


async def data_access_get_guild_tournament_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_TOURNAMENT_TEXT_CHANNEL}:{guild_id}")


def data_access_set_guild_tournament_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_TOURNAMENT_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_analytics_report_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the configured monthly analytics report channel."""
    return await get_cache(False, f"{KEY_GUILD_ANALYTICS_REPORT_TEXT_CHANNEL}:{guild_id}")


def data_access_set_analytics_report_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that receives monthly analytics PDF reports."""
    set_cache(False, f"{KEY_GUILD_ANALYTICS_REPORT_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_monthly_analytics_report_sent(guild_id: int, report_month: str) -> bool:
    """Return whether the monthly analytics report was already sent for a guild/month."""
    value = await get_cache(False, f"{KEY_GUILD_ANALYTICS_REPORT_SENT}:{guild_id}:{report_month}")
    return bool(value)


def data_access_set_monthly_analytics_report_sent(guild_id: int, report_month: str) -> None:
    """Mark the monthly analytics report as sent for a guild/month."""
    set_cache(False, f"{KEY_GUILD_ANALYTICS_REPORT_SENT}:{guild_id}:{report_month}", True, ALWAYS_TTL)


async def data_access_get_main_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_MAIN_TEXT_CHANNEL}:{guild_id}")


def data_access_set_main_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text related to Siege"""
    set_cache(False, f"{KEY_GUILD_MAIN_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_ai_text_channel_id(
    guild_id: int,
) -> Union[int, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_AI_TEXT_CHANNEL}:{guild_id}")


def data_access_set_ai_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text related to AI"""
    set_cache(False, f"{KEY_GUILD_AI_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_guild_ai_context(guild_id: int) -> Union[str, None]:
    """Get the permanent AI context for a guild."""
    found, value = get_value_with_presence(f"{KEY_GUILD_AI_CONTEXT}:{guild_id}")
    if not found:
        return None
    return value


def data_access_set_guild_ai_context(guild_id: int, context: str) -> None:
    """Persist the permanent AI context for a guild."""
    key = f"{KEY_GUILD_AI_CONTEXT}:{guild_id}"
    set_cache(False, key, context, ALWAYS_TTL)
    found, stored_value = get_value_with_presence(key)
    if not found or stored_value != context:
        print_error_log(f"data_access_set_guild_ai_context: Failed to persist AI context for guild {guild_id}")


def data_access_clear_guild_ai_context(guild_id: int) -> None:
    """Remove the permanent AI context for a guild."""
    remove_cache(False, f"{KEY_GUILD_AI_CONTEXT}:{guild_id}")


def data_access_set_voice_user_list(guild_id: int, channel_id: int, user_map: dict[int, ActivityTransition]) -> None:
    """Set the list of user for a voice channel and their activity"""
    set_cache(True, f"{KEY_GUILD_VOICE_CHANNEL_LIST_USER}:{guild_id}:{channel_id}", user_map, ALWAYS_TTL)


async def data_access_get_voice_user_list(guild_id: int, channel_id: int) -> dict[int, ActivityTransition]:
    """Get the list of user for a voice channel and their activity"""
    result = await get_cache(True, f"{KEY_GUILD_VOICE_CHANNEL_LIST_USER}:{guild_id}:{channel_id}")
    if result is None:
        return {}
    return result


async def data_access_remove_voice_user_list(guild_id: int, channel_id: int, user_id: int) -> None:
    """Remove a user from the voice channel list"""
    async with lock_voice_user_list:  # FIX: Add locking
        user_map = await data_access_get_voice_user_list(guild_id, channel_id)
        user_map.pop(user_id, None)
        print_log(f"data_access_remove_voice_user_list: Remove voice user list: {len(user_map.keys())}")
        set_cache(True, f"{KEY_GUILD_VOICE_CHANNEL_LIST_USER}:{guild_id}:{channel_id}", user_map, ALWAYS_TTL)


async def data_access_update_voice_user_list(
    guild_id: int, channel_id: int, user_id: int, activity_detail: Optional[Union[ActivityTransition, str]]
) -> None:
    """
    Set for a voice channel the user status
    activity_detail is a string or an Activity
        If a string, we need to take the current after, set to before and use the string as the after
        If an activity, we just set the activity
    """
    async with lock_voice_user_list:  # FIX: Add locking
        user_map = await data_access_get_voice_user_list(guild_id, channel_id)

        # The activity_detail exist (could be string or a full activity detail or None if the user does not have the activity feature enabled)
        if isinstance(activity_detail, str):
            # If a string is provided, it means we only have a activity detail (without the before)
            # It happens in the case of changing status (offline to online)
            current_activity = user_map.get(user_id, None)
            if current_activity is None:
                # If the user wasn't there and we have only the after, we set the None the before
                to_save = ActivityTransition(None, activity_detail)
            else:
                # If we had the user before and now providing only a current detail, we set the current after as before and then the string as after
                to_save = ActivityTransition(current_activity.after, activity_detail)
        else:
            # We have a full activity detail. Might be None, or might have both before and after
            if activity_detail is None:
                to_save = ActivityTransition(None, None)
            else:
                to_save = activity_detail

        # Save the user which is None or a full activity detail
        user_map[user_id] = to_save
        data_access_set_voice_user_list(guild_id, channel_id, user_map)


async def data_access_get_last_bot_message_in_main_text_channel(
    guild_id: int, voice_channel_id: int
) -> Union[datetime, None]:
    """Get the last date time that the bot sent a message in the main text channel in ISO format"""
    return await get_cache(False, f"{KEY_GUILD_LAST_BOT_MESSAGE_MAIN_TEXT_CHANNEL}:{guild_id}:{voice_channel_id}")


def data_access_set_last_bot_message_in_main_text_channel(
    guild_id: int,
    voice_channel_id: int,
    date_time: datetime,
) -> None:
    """Get the last date time that the bot sent a message in the main text channel in ISO format"""
    set_cache(
        False, f"{KEY_GUILD_LAST_BOT_MESSAGE_MAIN_TEXT_CHANNEL}:{guild_id}:{voice_channel_id}", date_time, ONE_HOUR_TTL
    )


async def data_access_get_daily_message_id(guild_id: int) -> Union[int, None]:
    """Get the daily message by the given guild and channel id"""
    current_date = get_now_eastern().strftime("%Y-%m-%d")
    key = f"{KEY_DAILY_MSG}:{guild_id}:{current_date}"
    return await get_cache(False, key)


def data_access_set_daily_message_id(guild_id: int, message_id: int) -> None:
    """Set the daily message by the given guild and channel id"""
    current_date = get_now_eastern().strftime("%Y-%m-%d")
    key = f"{KEY_DAILY_MSG}:{guild_id}:{current_date}"
    set_cache(False, key, message_id, THREE_DAY_TTL)


def data_access_execute_sql_query_from_llm(sql_query: str) -> str:
    """
    Execute a SQL query from LLM
    """
    database_manager.get_cursor().execute(sql_query)
    result = database_manager.get_cursor().fetchall()
    # Convert to string the whole result
    if not result:
        return ""
    result_string = "\n".join(str(row) for row in result)
    return result_string


async def data_access_get_ai_daily_count() -> Union[int, None]:
    """Get the count of time the AI was called"""
    return await get_cache(False, KEY_AI_COUNT)


def data_access_set_ai_daily_count(count: int) -> None:
    """Set the count of time the AI was called"""
    set_cache(False, KEY_AI_COUNT, count, ONE_DAY_TTL)


def data_access_set_custom_game_voice_channels(
    guild_id: int, lobby_channel_id: int, team1_channel_id: int, team2_channel_id: int
) -> None:
    """Set the voice channels used for custom games"""
    set_cache(False, f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_LOBBY}:{guild_id}", lobby_channel_id, ALWAYS_TTL)
    set_cache(False, f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM1}:{guild_id}", team1_channel_id, ALWAYS_TTL)
    set_cache(False, f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM2}:{guild_id}", team2_channel_id, ALWAYS_TTL)


async def data_access_get_custom_game_voice_channels(
    guild_id: int,
) -> tuple[Optional[int], Optional[int], Optional[int]]:
    """Get the voice channels used for custom games"""
    lobby_channel_id = await get_cache(False, f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_LOBBY}:{guild_id}")
    team1_channel_id = await get_cache(False, f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM1}:{guild_id}")
    team2_channel_id = await get_cache(False, f"{KEY_GUILD_CUSTOM_GAME_VOICE_CHANNEL_TEAM2}:{guild_id}")
    return (lobby_channel_id, team1_channel_id, team2_channel_id)


async def data_access_get_last_match_start_gif_time(guild_id: int, channel_id: int) -> Optional[datetime]:
    """Get the last time a match start GIF was sent for a specific voice channel"""
    key = f"{KEY_LAST_MATCH_START_GIF}:{guild_id}:{channel_id}"
    return await get_cache(False, key)


async def data_access_set_last_match_start_gif_time(guild_id: int, channel_id: int, time: datetime) -> None:
    """Set the last time a match start GIF was sent for a specific voice channel"""
    key = f"{KEY_LAST_MATCH_START_GIF}:{guild_id}:{channel_id}"
    set_cache(False, key, time, ONE_HOUR_TTL)


def data_access_clear_last_match_start_gif_time(guild_id: int, channel_id: int) -> None:
    """Clear the match start GIF send reservation for a specific voice channel."""
    key = f"{KEY_LAST_MATCH_START_GIF}:{guild_id}:{channel_id}"
    remove_cache(False, key)


async def data_access_get_pending_match_start_gif_message(
    guild_id: int,
    voice_channel_id: int,
) -> Optional[dict[str, Any]]:
    """Pending match-start GIF message to update when stats.cc reports match end (2h TTL)."""
    key = f"{KEY_PENDING_MATCH_START_GIF}:{guild_id}:{voice_channel_id}"
    return await get_cache(False, key)


def data_access_set_pending_match_start_gif_message(
    guild_id: int,
    voice_channel_id: int,
    text_channel_id: int,
    message_id: int,
    member_ids: list[int],
    last_result_key: str | None = None,
) -> None:
    """Store the text channel/message id and GIF member ids after posting a match-start GIF."""
    key = f"{KEY_PENDING_MATCH_START_GIF}:{guild_id}:{voice_channel_id}"
    value: dict[str, Any] = {"text_channel_id": text_channel_id, "message_id": message_id, "member_ids": member_ids}
    if last_result_key is not None:
        value["last_result_key"] = last_result_key
    set_cache(
        False,
        key,
        value,
        TWO_HOUR_TTL,
    )


def data_access_clear_pending_match_start_gif_message(guild_id: int, voice_channel_id: int) -> None:
    """Remove pending match-start GIF metadata (after successful result edit or abandon)."""
    key = f"{KEY_PENDING_MATCH_START_GIF}:{guild_id}:{voice_channel_id}"
    remove_cache(False, key)


async def data_access_get_guild_private_channel_category_id(guild_id: int) -> Union[int, None]:
    """Get the category where private channels are created"""
    return await get_cache(False, f"{KEY_GUILD_PRIVATE_CHANNEL_CATEGORY}:{guild_id}")


def data_access_set_guild_private_channel_category_id(guild_id: int, category_id: int) -> None:
    """Set the category where private channels are created"""
    set_cache(False, f"{KEY_GUILD_PRIVATE_CHANNEL_CATEGORY}:{guild_id}", category_id, ALWAYS_TTL)


async def data_access_get_guild_active_private_channels(guild_id: int) -> dict[int, tuple[int, bool]]:
    """Get all active private channels as {channel_id: (creator_id, track)}, or empty dict."""
    result = await get_cache(False, f"{KEY_GUILD_ACTIVE_PRIVATE_CHANNEL}:{guild_id}")
    return result if result is not None else {}


async def data_access_set_guild_active_private_channel(
    guild_id: int, channel_id: int, creator_id: int, track: bool = True
) -> None:
    """Add or update a private channel entry."""
    channels = await data_access_get_guild_active_private_channels(guild_id)
    channels[channel_id] = (creator_id, track)
    set_cache(False, f"{KEY_GUILD_ACTIVE_PRIVATE_CHANNEL}:{guild_id}", channels, ALWAYS_TTL)


async def data_access_remove_guild_active_private_channel(guild_id: int, channel_id: int) -> None:
    """Remove a single private channel entry."""
    channels = await data_access_get_guild_active_private_channels(guild_id)
    channels.pop(channel_id, None)
    if channels:
        set_cache(False, f"{KEY_GUILD_ACTIVE_PRIVATE_CHANNEL}:{guild_id}", channels, ALWAYS_TTL)
    else:
        remove_cache(False, f"{KEY_GUILD_ACTIVE_PRIVATE_CHANNEL}:{guild_id}")
