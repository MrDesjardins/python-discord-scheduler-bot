""" Common Actions that the bots Cogs or Bots can invoke """

import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Union
from gtts import gTTS
import discord
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.data_access_data_class import UserInfo
from deps.data_access import (
    data_access_get_bot_voice_first_user,
    data_access_get_channel,
    data_access_get_daily_message,
    data_access_get_gaming_session_last_activity,
    data_access_get_gaming_session_text_channel_id,
    data_access_get_guild_text_channel_id,
    data_access_get_guild_username_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_r6tracker_max_rank,
    data_access_get_reaction_message,
    data_access_get_users_auto_schedule,
    data_access_set_daily_message,
    data_access_set_gaming_session_last_activity,
    data_access_set_reaction_message,
)
from deps.date_utils import is_today
from deps.mybot import MyBot
from deps.models import SimpleUser, SimpleUserHour, UserMatchInfoSessionAggregate
from deps.log import print_error_log, print_log, print_warning_log
from deps.functions import (
    get_current_hour_eastern,
    get_empty_votes,
    get_last_schedule_message,
    get_reactions,
    set_member_role_from_rank,
)
from deps.values import COMMAND_SCHEDULE_ADD, DATE_FORMAT, MSG_UNIQUE_STRING, SUPPORTED_TIMES_STR
from deps.siege import get_color_for_rank, get_user_rank_emoji
from deps.functions_r6_tracker import get_r6tracker_user_recent_matches, get_user_gaming_session_stats


async def send_daily_question_to_a_guild(bot: MyBot, guild: discord.Guild, force: bool = False):
    """
    Send the daily schedule question to a specific guild
    """
    guild_id = guild.id
    reactions = get_reactions()
    channel_id = await data_access_get_guild_text_channel_id(guild.id)
    if channel_id is None:
        print_error_log(f"\t⚠️ Channel id (configuration) not found for guild {guild.name}. Skipping.")
        return

    message_sent = await data_access_get_daily_message(guild_id, channel_id)
    if message_sent is None or force is True:
        channel: discord.TextChannel = await data_access_get_channel(channel_id)
        # We might not have in the cache but maybe the message was sent, let's check
        last_message = await get_last_schedule_message(bot, channel)
        if last_message is not None:
            if is_today(last_message.created_at):
                print_warning_log(
                    f"\t⚠️ Daily message already in Discord for guild {guild.name}. Adding in cache and skipping."
                )
                data_access_set_daily_message(guild_id, channel_id)
                return
        # We never sent the message, so we send it, add the reactions and save it in the cache
        embed_msg = get_daily_embed_message(get_empty_votes())
        message: discord.Message = await channel.send(content="", embed=embed_msg)
        for reaction in reactions:
            await message.add_reaction(reaction)
        await auto_assign_user_to_daily_question(guild.id, channel_id, message)
        data_access_set_daily_message(guild_id, channel_id)
        print_log(f"\t✅ Daily message sent in guild {guild.name}")
    else:
        print_warning_log(f"\t⚠️ Daily message already sent in guild {guild.name}. Skipping.")


async def update_vote_message(message: discord.Message, vote_for_message: Dict[str, List[SimpleUser]]):
    """Update the votes per hour on the bot message"""
    embed_msg = get_daily_embed_message(vote_for_message)
    print_log("update_vote_message: Updated Message")
    await message.edit(content="", embed=embed_msg)


def get_daily_embed_message(vote_for_message: Dict[str, List[SimpleUser]]) -> discord.Embed:
    """Create the daily message"""
    current_date = date.today().strftime(DATE_FORMAT)
    vote_message = f"{MSG_UNIQUE_STRING} today **{current_date}**?"
    vote_message += "\n\n**Schedule**\n"
    for key_time, users in vote_for_message.items():
        if users:
            vote_message += f"{key_time}: {','.join([f'{user.rank_emoji}{user.display_name}' for user in users])}\n"
        else:
            vote_message += f"{key_time}: -\n"

    embed = discord.Embed(
        title="Schedule",
        description=vote_message,
        color=0x00FF00,
        timestamp=datetime.now(),
    )
    embed.set_footer(
        text=f"⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nYou can use `/{COMMAND_SCHEDULE_ADD}` to set recurrent day and hours or click the emoji corresponding to your time:"
    )
    return embed


async def auto_assign_user_to_daily_question(guild_id: int, channel_id: int, message: discord.Message) -> None:
    """Take the existing schedules for all user and apply it to the message"""
    day_of_week_number = datetime.now().weekday()  # 0 is Monday, 6 is Sunday
    message_id = message.id
    print_log(
        f"Auto assign user to daily question for guild {guild_id}, message_id {message_id}, day_of_week_number {day_of_week_number}"
    )

    # Get the list of user and their hour for the specific day of the week
    list_users: Union[List[SimpleUserHour] | None] = await data_access_get_users_auto_schedule(
        guild_id, day_of_week_number
    )

    message_votes = get_empty_votes()  # Start with nothing for the day

    # Loop for the user+hours
    if list_users is not None:
        print_log(f"Found {len(list_users)} schedules for the day {day_of_week_number}")
        for user_hour in list_users:
            # Assign for each hour the user
            message_votes[user_hour.hour].append(user_hour.simple_user)

        data_access_set_reaction_message(guild_id, channel_id, message_id, message_votes)
        print_log(f"Updated message {message_id} with the user schedules for the day {day_of_week_number}")
        print_log(message_votes)
        await update_vote_message(message, message_votes)

    else:
        print_log(f"No schedule found for the day {day_of_week_number}")


async def check_voice_channel(bot: MyBot):
    """
    Run when the bot start and every X minutes to update the cache of the users in the voice channel and update the schedule
    """
    print_log("check_voice_channel: Checking voice channel to sync the schedule")
    for guild in bot.guilds:
        guild_id = guild.id
        text_channel_id = await data_access_get_guild_text_channel_id(guild_id)
        if text_channel_id is None:
            print_warning_log(f"check_voice_channel: Text channel not set for guild {guild.name}. Skipping.")
            continue
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_channel_ids is None:
            print_warning_log(f"check_voice_channel: Voice channel not set for guild {guild.name}. Skipping.")
            continue
        text_channel = await data_access_get_channel(text_channel_id)

        if text_channel is None:
            print_warning_log(
                f"check_voice_channel: Text channel configured but not found in the guild {guild.name}. Skipping."
            )
            continue
        last_message = await get_last_schedule_message(bot, text_channel)
        if last_message is None:
            print_warning_log(f"check_voice_channel: No message found in the channel {text_channel.name}. Skipping.")
            continue
        message_id = last_message.id
        message_votes = await data_access_get_reaction_message(guild_id, text_channel_id, message_id)
        if not message_votes:
            message_votes = get_empty_votes()
        found_new_user = False
        for voice_channel_id in voice_channel_ids:
            voice_channel = await data_access_get_channel(voice_channel_id)
            if voice_channel is None:
                print_warning_log(
                    f"check_voice_channel: Voice channel configured but not found in the guild {guild.name}. Skipping."
                )
                continue

            users_in_channel = voice_channel.members  # List of users in the voice channel
            for user in users_in_channel:
                # Check if the user is a bot
                if user.bot:
                    continue
                # Check if the user already reacted
                current_hour_str = get_current_hour_eastern()
                if current_hour_str not in SUPPORTED_TIMES_STR:
                    # We support a limited amount of hours because of emoji constraints
                    print_log(f"check_voice_channel: Current hour {current_hour_str} not supported. Skipping.")
                    continue
                if any(user.id == u.user_id for u in message_votes[current_hour_str]):
                    # User already voted for the current hour
                    print_log(
                        f"check_voice_channel: User {user.id} already voted for {current_hour_str} in message {message_id}"
                    )
                    continue
                # Add the user to the message votes
                found_new_user = True
                message_votes[current_hour_str].append(
                    SimpleUser(
                        user.id,
                        user.display_name,
                        get_user_rank_emoji(bot.guild_emoji[guild_id], user),
                    )
                )

        if found_new_user:
            print_log(f"check_voice_channel: Updating voice channel cache for {guild.name} and updating the message")
            # Always update the cache
            data_access_set_reaction_message(guild_id, text_channel_id, message_id, message_votes)
            await update_vote_message(last_message, message_votes)
            print_log(f"check_voice_channel: Updated voice channel cache for {guild.name}")
        else:
            print_log(f"check_voice_channel: No new user found in voice channel for {guild.name}")


async def send_notification_voice_channel(
    bot: MyBot,
    guild_id: int,
    member: discord.Member,
    voice_channel: discord.VoiceChannel,
    text_channel_id: int,
) -> None:
    """
    Send a notification to the user in the voice channel
    """
    is_enabled = await data_access_get_bot_voice_first_user(guild_id)
    if not is_enabled:
        return
    # Send DM to the user
    # await member.send(
    #     f"You're the only one in the voice channel: Feel free to message the Siege channel with \"@here lfg 4 rank\" to find other players and check the other players' schedule in <#{text_channel_id}>."
    # )

    list_simple_users = await get_users_scheduled_today_current_hour(bot, guild_id, get_current_hour_eastern())
    list_simple_users = list(filter(lambda x: x.user_id != member.id, list_simple_users))
    if len(list_simple_users) > 0:
        other_members = ", ".join([f"{user.display_name}" for user in list_simple_users])
        text_message = f"Hello {member.display_name}! {other_members} are scheduled to play at this time. Check the bot schedule channel."
    else:
        # Check next hour
        list_simple_users = await get_users_scheduled_today_current_hour(bot, guild_id, get_current_hour_eastern(1))
        list_simple_users = list(filter(lambda x: x.user_id != member.id, list_simple_users))
        if len(list_simple_users) > 0:
            other_members = ", ".join([f"{user.display_name}" for user in list_simple_users])
            text_message = f"Hello {member.display_name}! {other_members} are scheduled to play in the upcoming hour. Check the bot schedule channel."
        else:
            text_message = f"Hello {member.display_name}! Feel free to message the rainbow six siege channel to find partners and check the bot schedule channel."

    print_log(f"Sending voice message to {member.display_name}")
    # Convert text to speech using gTTS
    tts = gTTS(text_message, lang="en")
    tts.save("welcome.mp3")
    # Connect to the voice channel
    if member.guild.voice_client is None:  # Bot isn't already in a channel
        voice_client = await voice_channel.connect()
    else:
        voice_client = member.guild.voice_client

    # Play the audio
    audio_source = discord.FFmpegPCMAudio("welcome.mp3")
    voice_client.play(audio_source)

    # Wait for the audio to finish playing
    while voice_client.is_playing():
        await discord.utils.sleep_until(datetime.now() + timedelta(seconds=1))

    # Disconnect after playing the audio
    await voice_client.disconnect()

    # Clean up the saved audio file
    os.remove("welcome.mp3")


async def get_users_scheduled_today_current_hour(bot: MyBot, guild_id: int, current_hour_str: str) -> List[SimpleUser]:
    """
    Get the list of users scheduled for the current day and hour
    current_hour_str: The current hour in the format "3am"
    """
    channel_id = await data_access_get_guild_text_channel_id(guild_id)
    channel = await data_access_get_channel(channel_id)

    last_message = await get_last_schedule_message(bot, channel)

    if last_message is None:
        return []

    # Cache all users for this message's reactions to avoid redundant API calls
    message_votes = await data_access_get_reaction_message(guild_id, channel_id, last_message.id)
    if not message_votes:
        message_votes = get_empty_votes()
    if current_hour_str not in message_votes:
        return []
    return message_votes[current_hour_str]


async def adjust_role_from_ubisoft_max_account(
    guild: discord.guild, member: discord.member, ubisoft_connect_name: str
) -> str:
    """Adjust the server's role of a user based on their max rank in R6 Tracker"""
    max_rank = await data_access_get_r6tracker_max_rank(ubisoft_connect_name)

    print_log(
        f"adjust_role_from_ubisoft_max_account: R6 Tracker Downloaded Info for user {member.display_name} and found for user name {ubisoft_connect_name} the max role: {max_rank}"
    )
    try:
        await set_member_role_from_rank(guild, member, max_rank)
    except Exception as e:
        print_error_log(f"adjust_role_from_ubisoft_max_account: Error setting the role: {e}")

        return

    text_channel_id = await data_access_get_guild_username_text_channel_id(guild.id)
    if text_channel_id is None:
        print_warning_log(
            f"adjust_role_from_ubisoft_max_account: Text channel not set for guild {guild.name}. Skipping."
        )
        return

    # Retrieve the moderator role by name
    mod_role = discord.utils.get(guild.roles, name="Mod")

    if mod_role is None:
        print_warning_log(f"adjust_role_from_ubisoft_max_account: Mod role not found in guild {guild.name}. Skipping.")

    channel = await data_access_get_channel(text_channel_id)
    await channel.send(
        content=f"{member.mention} main account is `{ubisoft_connect_name}` with max rank of `{max_rank}`.\n{mod_role.mention} please confirm the account belong to this person.",
    )
    return max_rank


async def send_session_stats(
    member: discord.Member, guild_id: int, last_hour: int = 12
) -> Optional[UserMatchInfoSessionAggregate]:
    """
    Get the statistic of a user and post it
    """

    if member.bot:
        return  # Ignore bot

    # Only perform the action if it wasn't done in the last hour
    current_time = datetime.now(timezone.utc)
    last_activity = await data_access_get_gaming_session_last_activity(member.id, guild_id)
    # Only shows the stats once per hour per user maximum
    if last_activity is not None and last_activity > current_time - timedelta(hours=1):
        return None

    # Get the user ubisoft name
    user_info: UserInfo = await fetch_user_info_by_user_id(member.id)
    if user_info is None or user_info.ubisoft_username_active is None:
        return None

    try:
        matches = get_r6tracker_user_recent_matches(user_info.ubisoft_username_active)
        await data_access_set_gaming_session_last_activity(member.id, guild_id, current_time)
    except Exception as e:
        print_error_log(f"Error getting the user stats from R6 tracker: {e}")
        return None

    aggregation: Optional[UserMatchInfoSessionAggregate] = get_user_gaming_session_stats(
        user_info.ubisoft_username_active, current_time - timedelta(hours=last_hour), matches
    )
    if aggregation is None:
        print_log(f"User {member.display_name} has no stats to show in the last {last_hour} hours")
        return None

    channel_id: int = await data_access_get_gaming_session_text_channel_id(guild_id)
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    # We never sent the message, so we send it, add the reactions and save it in the cache
    embed_msg = get_gaming_session_user_embed_message(member, aggregation, last_hour)
    await channel.send(content="", embed=embed_msg)
    return aggregation


def get_gaming_session_user_embed_message(
    member: discord.Member, aggregation: UserMatchInfoSessionAggregate, last_hour: int
) -> discord.Embed:
    """Create the stats message"""
    title = f"{member.display_name} Stats"
    embed = discord.Embed(
        title=title,
        description=f"{member.mention} played {aggregation.match_count} matches: {aggregation.match_win_count} wins and {aggregation.match_loss_count} losses.",
        color=get_color_for_rank(member),
        timestamp=datetime.now(),
        url=f"https://r6.tracker.network/r6siege/profile/ubi/{aggregation.ubisoft_username_active}",
    )
    # Get the list of kill_death into a string with comma separated
    str_kd = "\n".join(
        f"Match #{i+1} ({map_name}): {kd}"
        for i, (kd, map_name) in enumerate(reversed(list(zip(aggregation.kill_death_assist, aggregation.maps_played))))
    )
    embed.set_thumbnail(url=member.avatar.url)

    embed.add_field(name="Starting Pts", value=aggregation.started_rank_points, inline=True)
    diff = (
        "+" + str(aggregation.total_gained_points)
        if aggregation.total_gained_points > 0
        else str(aggregation.total_gained_points)
    )
    embed.add_field(name="Ending Pts", value=f"{aggregation.ended_rank_points}", inline=True)
    embed.add_field(name="Pts Variation", value=diff, inline=True)
    embed.add_field(name="Total Kills", value=aggregation.total_kill_count, inline=True)
    embed.add_field(name="Total Deaths", value=aggregation.total_death_count, inline=True)
    embed.add_field(name="Total Assists", value=aggregation.total_assist_count, inline=True)
    embed.add_field(name="Total TK", value=aggregation.total_tk_count, inline=True)
    embed.add_field(name="Total 3k round", value=aggregation.total_round_with_3k, inline=True)
    embed.add_field(name="Total 4k round", value=aggregation.total_round_with_3k, inline=True)
    embed.add_field(name="Total Ace round", value=aggregation.total_round_with_aces, inline=True)
    embed.add_field(name="Kill/Death/Asssist Per Match", value=str_kd, inline=False)
    embed.set_footer(text=f"Your stats for the last {last_hour} hours")
    return embed
