""" Access to the data is done throught this data access"""

from typing import List, Union
from datetime import datetime
import discord
from deps.bot_singleton import BotSingleton
from deps.cache import (
    ALWAYS_TTL,
    THREE_DAY_TTL,
    get_cache,
    remove_cache,
    reset_cache_by_prefixes,
    set_cache,
)
from deps.models import SimpleUserHour

KEY_DAILY_MSG = "DailyMessageSentInChannel"
KEY_REACTION_USERS = "ReactionUsersV2"
KEY_GUILD_USERS_AUTO_SCHEDULE = "GuildUsersAutoScheduleByDay"
KEY_GUILD_TEXT_CHANNEL = "GuildAdminConfigTextChannel"
KEY_GUILD_VOICE_CHANNELS = "GuildAdminConfigVoiceChannels"
KEY_MESSAGE = "Message"
KEY_USER = "User"
KEY_GUILD = "Guild"
KEY_MEMBER = "Member"
KEY_CHANNEL = "Channel"
KEY_GUILD_BOT_VOICE_FIRST_USER = "GuildBotVoiceFirstUser"


async def data_access_get_guild(guild_id: discord.Guild) -> Union[discord.Guild, None]:
    """Get the guild by the given guild"""

    async def fetch():
        return BotSingleton().bot.get_guild(guild_id)

    return await get_cache(True, f"{KEY_GUILD}:{guild_id}", fetch)


async def data_access_get_message(
    guild_id: discord.Guild, channel_id: int, message_id: int
) -> Union[discord.Message, None]:
    """Get the message by the given guild, channel and message id"""

    async def fetch():
        channel: discord.TextChannel = await data_access_get_channel(channel_id)
        return await channel.fetch_message(message_id)

    return await get_cache(True, f"{KEY_MESSAGE}:{guild_id}:{channel_id}:{message_id}", fetch)


async def data_access_get_user(guild_id: discord.Guild, user_id: int) -> Union[discord.User, None]:
    """Get the user by the given guild and user id"""

    async def fetch():
        return BotSingleton().bot.get_user(user_id)

    return await get_cache(True, f"{KEY_USER}:{guild_id}:{user_id}", fetch)


async def data_access_get_member(guild_id: discord.Guild, user_id: int) -> Union[discord.Member, None]:
    """Get the member by the given guild and user id"""

    async def fetch():
        guild: discord.Guild = await data_access_get_guild(guild_id)
        return guild.get_member(user_id)

    return await get_cache(True, f"{KEY_MEMBER}:{guild_id}:{user_id}", fetch)


async def data_access_get_channel(channel_id: int) -> Union[discord.TextChannel, None]:
    """Get the channel by the given channel id"""

    async def fetch():
        return BotSingleton().bot.get_channel(channel_id)

    return await get_cache(True, f"{KEY_CHANNEL}:{channel_id}", fetch)


async def data_access_get_reaction_message(guild_id: int, channel_id: int, message_id: int) -> dict[str, list]:
    """Get the users reactions for a specific mesage"""
    key = f"{KEY_REACTION_USERS}:{guild_id}:{channel_id}:{message_id}"
    return await get_cache(False, key)


def data_access_set_reaction_message(
    guild_id: int, channel_id: int, message_id: int, message_votes: dict[str, list]
) -> None:
    """Set the reaction for a specific message"""
    key = f"{KEY_REACTION_USERS}:{guild_id}:{channel_id}:{message_id}"
    set_cache(False, key, message_votes, ALWAYS_TTL)


async def data_access_get_daily_message(guild_id: int, channel_id: int) -> Union[discord.Message, None]:
    """Get the daily message by the given guild and channel id"""
    now = datetime.now()
    current_date = now.strftime("%Y%m%d")
    key = f"{KEY_DAILY_MSG}:{guild_id}:{channel_id}:{current_date}"
    return await get_cache(False, key)


def data_access_set_daily_message(guild_id: int, channel_id: int) -> None:
    """Set the daily message by the given guild and channel id"""
    now = datetime.now()
    current_date = now.strftime("%Y%m%d")
    key = f"{KEY_DAILY_MSG}:{guild_id}:{channel_id}:{current_date}"
    set_cache(False, key, True, THREE_DAY_TTL)


async def data_access_get_users_auto_schedule(
    guild_id: int, day_of_week_number: str
) -> Union[List[SimpleUserHour], None]:
    """Get users schedule for a specific day of the week"""
    return await get_cache(False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}:{day_of_week_number}")


def data_access_set_users_auto_schedule(guild_id: int, day_of_week_number: str, users: List[SimpleUserHour]) -> None:
    """Configure the users schedule for a specific day of the week"""
    set_cache(
        False,
        f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}:{day_of_week_number}",
        users,
        ALWAYS_TTL,
    )


async def data_access_get_guild_text_channel_id(
    guild_id: int,
) -> Union[discord.TextChannel, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}")


def data_access_set_guild_text_channel_id(guild_id: int, channel_id: int) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}", channel_id, ALWAYS_TTL)


async def data_access_get_guild_voice_channel_ids(
    guild_id: int,
) -> Union[discord.VoiceChannel, None]:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_VOICE_CHANNELS}:{guild_id}")


def data_access_set_guild_voice_channel_ids(guild_id: int, channel_ids: Union[List, None]) -> None:
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
        f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}",
        f"{KEY_MESSAGE}:{guild_id}",
        f"{KEY_USER}:{guild_id}",
        f"{KEY_GUILD}:{guild_id}",
        f"{KEY_MEMBER}:{guild_id}",
    ]
    reset_cache_by_prefixes(prefixes)


async def data_access_get_bot_voice_first_user(guild_id: int) -> bool:
    """Get the channel by the given channel id"""
    return await get_cache(False, f"{KEY_GUILD_BOT_VOICE_FIRST_USER}:{guild_id}", lambda: False)


def data_access_set_bot_voice_first_user(guild_id: int, enabled: bool) -> None:
    """Set the channel that the bot will send text"""
    set_cache(False, f"{KEY_GUILD_BOT_VOICE_FIRST_USER}:{guild_id}", enabled, ALWAYS_TTL)
