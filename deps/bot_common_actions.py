""" Common Actions that the bots Cogs or Bots can invoke """

import asyncio
import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Union
from gtts import gTTS
import discord
from deps.browser_context_manager import BrowserContextManager
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.data_access_data_class import UserInfo
from deps.data_access import (
    data_access_add_list_member_stats,
    data_access_get_bot_voice_first_user,
    data_access_get_channel,
    data_access_get_daily_message,
    data_access_get_gaming_session_last_activity,
    data_access_get_gaming_session_text_channel_id,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_guild_username_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_list_member_stats,
    data_access_get_member,
    data_access_get_r6tracker_max_rank,
    data_access_get_reaction_message,
    data_access_get_users_auto_schedule,
    data_access_set_daily_message,
    data_access_set_gaming_session_last_activity,
    data_access_set_reaction_message,
    data_acess_remove_list_member_stats,
)
from deps.date_utils import is_today
from deps.mybot import MyBot
from deps.models import (
    SimpleUser,
    SimpleUserHour,
    UserMatchInfo,
    UserMatchInfoSessionAggregate,
    UserQueueForStats,
    UserWithUserMatchInfo,
)
from deps.log import print_error_log, print_log, print_warning_log
from deps.functions import (
    get_current_hour_eastern,
    get_empty_votes,
    get_last_schedule_message,
    get_reactions,
    get_url_user_profile_main,
    get_url_user_profile_overview,
    set_member_role_from_rank,
)
from deps.values import (
    COMMAND_SCHEDULE_ADD,
    DATE_FORMAT,
    MSG_UNIQUE_STRING,
    STATS_HOURS_WINDOW_IN_PAST,
    SUPPORTED_TIMES_STR,
)
from deps.siege import get_color_for_rank, get_user_rank_emoji
from deps.functions_r6_tracker import get_user_gaming_session_stats


async def send_daily_question_to_a_guild(bot: MyBot, guild: discord.Guild, force: bool = False):
    """
    Send the daily schedule question to a specific guild
    """
    guild_id = guild.id
    reactions = get_reactions()
    channel_id = await data_access_get_guild_schedule_text_channel_id(guild.id)
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
        text_channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
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
    schedule_text_channel_id: int,
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
    channel_schedule: Optional[discord.TextChannel] = await data_access_get_channel(schedule_text_channel_id)
    channel_name = channel_schedule.name if channel_schedule is not None else "schedule"
    list_simple_users = await get_users_scheduled_today_current_hour(bot, guild_id, get_current_hour_eastern())
    list_simple_users = list(filter(lambda x: x.user_id != member.id, list_simple_users))
    if len(list_simple_users) > 0:
        other_members = ", ".join([f"{user.display_name}" for user in list_simple_users])
        text_message = f"Hello {member.display_name}! {other_members} are scheduled to play at this time. Check the bot {channel_name} channel."
    else:
        # Check next hour
        list_simple_users = await get_users_scheduled_today_current_hour(bot, guild_id, get_current_hour_eastern(1))
        list_simple_users = list(filter(lambda x: x.user_id != member.id, list_simple_users))
        if len(list_simple_users) > 0:
            other_members = ", ".join([f"{user.display_name}" for user in list_simple_users])
            text_message = f"Hello {member.display_name}! {other_members} are scheduled to play in the upcoming hour. Check the bot {channel_name} channel."
        else:
            text_message = f"Hello {member.display_name}! Use the slash lfg command in the rainbow six siege channel to find partners and check the {channel_name} channel."

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
    channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
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
    guild: discord.guild, member: discord.member, ubisoft_connect_name: str, ubisoft_active_account: str = None
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
    if ubisoft_active_account is None:
        active_msg = ""
    else:
        active_msg = f"\nCurrently playing on the [{ubisoft_active_account}]({get_url_user_profile_overview(ubisoft_active_account)}) account."

    await channel.send(
        content=f"{member.mention} main account is [{ubisoft_connect_name}]({get_url_user_profile_overview(ubisoft_connect_name)}) with max rank of `{max_rank}`.{active_msg}\n{mod_role.mention} please confirm the max account belong to this person.",
    )
    return max_rank


async def send_session_stats_directly(
    member: discord.Member, guild_id: int, last_hours: int
) -> Optional[UserMatchInfoSessionAggregate]:
    """
    Get the statistic of a user and post it
    """
    await send_session_stats_to_queue(member, guild_id)
    await post_queued_user_stats(False, last_hours)


async def send_session_stats_to_queue(member: discord.Member, guild_id: int) -> Optional[UserMatchInfoSessionAggregate]:
    """
    Get the statistic of a user and add the request into a queue
    """

    if member.bot:
        return  # Ignore bot

    member_id = member.id
    member_name = member.display_name

    # Only perform the action if it wasn't done in the last hour
    current_time = datetime.now(timezone.utc)
    last_activity = await data_access_get_gaming_session_last_activity(member_id, guild_id)
    # Only shows the stats once per hour per user maximum
    if last_activity is not None and last_activity > current_time - timedelta(hours=1):
        print_log(f"User {member_name} already has stats in the last hour")
        return None

    # Get the user ubisoft name
    user_info: UserInfo = await fetch_user_info_by_user_id(member_id)
    if user_info is None or user_info.ubisoft_username_active is None:
        print_log(f"User {member_name} has no active Ubisoft account set")
        return None

    # Queue the request to get the user stats with the time which allows to delay the transmission of about 5 minutes to avoid missing the last match
    user = UserQueueForStats(user_info, guild_id, current_time)
    await data_access_add_list_member_stats(user)
    print_log(f"User {member_name} added to the queue to get the stats")


async def post_queued_user_stats(check_time_delay: bool = True, last_hour: int = STATS_HOURS_WINDOW_IN_PAST) -> None:
    """
    Get the stats for all the users in the queue and post it
    The function relies on opening a browser once and get all the users from the queue to get their stats at the same time
    """
    # Get all the user waiting even if it's not the time yet (might just got added but the task kicked in)
    list_users: Optional[List[UserQueueForStats]] = await data_access_get_list_member_stats()
    list_users = list_users if list_users is not None else []  # Avoid None
    # print_log(f"post_queued_user_stats: {len(list_users)} users in the queue before delta time")

    if check_time_delay:
        # Filter the list for only user who it's been at least 2 minutes since added to the queue
        # This is to avoid getting the stats too early and miss the last match
        current_time = datetime.now(timezone.utc)
        delta = current_time - timedelta(minutes=2)
        users = [
            user_in_list for user_in_list in list_users if user_in_list.time_queue < delta
        ]  # Keep user that has been there for -infinity to -2 minutes

        if len(users) == 0:
            # print_log("post_queued_user_stats: 0 user in the queue after delta time")
            return
        # print_log(f"post_queued_user_stats: {len(users)} users in the queue after delta time")
    else:
        users = list_users
    # Accumulate all the stats for all the users before posting them
    all_users_matches: List[UserWithUserMatchInfo] = []
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    try:
        with BrowserContextManager() as context:
            for user in users:
                try:
                    matches: List[UserMatchInfo] = context.download_matches(user.user_info.ubisoft_username_active)
                    all_users_matches.append(UserWithUserMatchInfo(user, matches))
                    if len(users) > 1:
                        await asyncio.sleep(random.uniform(0.5, 2))  # Sleep 0.5 to 2 seconds between each request
                except Exception as e:
                    print_error_log(
                        f"post_queued_user_stats: Error getting the user ({user.user_info.display_name}) stats from R6 tracker: {e}"
                    )
                    continue  # Skip to the next user
    except Exception as e:
        print_error_log(f"post_queued_user_stats: Error opening the browser context: {e}")

    # End of the browser context
    if len(users) != len(all_users_matches):
        print_log(f"post_queued_user_stats: Not all users have been processed. {len(all_users_matches)}/{len(users)}")
    await send_channel_list_stats(all_users_matches, last_hour)


async def send_channel_list_stats(all_users_matches: List[UserWithUserMatchInfo], last_hour: int) -> None:
    """Post on the channel all the stats"""
    current_time = datetime.now(timezone.utc)
    time_past = current_time - timedelta(hours=last_hour)
    for user_matches in all_users_matches:
        user_info = user_matches.user.user_info
        member_id = user_info.id
        guild_id = user_matches.user.guild_id
        try:
            await data_acess_remove_list_member_stats(user_matches.user)
            aggregation: Optional[UserMatchInfoSessionAggregate] = get_user_gaming_session_stats(
                user_info.ubisoft_username_active, time_past, user_matches.user_match_info
            )
            if aggregation is None:
                print_log(
                    f"send_channel_list_stats: User {user_info.display_name} has no stats to show in the last {last_hour} hours"
                )
                continue  # Skip to the next user

            channel_id: int = await data_access_get_gaming_session_text_channel_id(guild_id)
            channel: discord.TextChannel = await data_access_get_channel(channel_id)
            member = await data_access_get_member(guild_id, member_id)
            if member is None:
                print_error_log(f"send_channel_list_stats: Member {member_id} not found in guild {guild_id}")
                continue  # Skip to the next user
            # We never sent the message, so we send it, add the reactions and save it in the cache
            embed_msg = get_gaming_session_user_embed_message(member, aggregation, last_hour)
        except Exception as e:
            print_error_log(f"send_channel_list_stats: Error removing and computing user stats: {e}")
            continue
        try:
            await channel.send(content="", embed=embed_msg)
            await data_access_set_gaming_session_last_activity(member_id, guild_id, current_time)
        except Exception as e:
            print_error_log(f"send_channel_list_stats: Error sending the user stats: {e}")
            continue  # Skip to the next user


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
        url=get_url_user_profile_main(aggregation.ubisoft_username_active),
    )

    # Get the list of kill_death into a string with comma separated
    str_kda = "\n".join(
        f"Match #{i+1} - {'won 🏆' if match.has_win else 'lose ☠'} - {match.map_name}: {match.kill_count}/{match.death_count}/{match.assist_count}"
        for i, match in enumerate(reversed(aggregation.matches_recent))
    )
    embed.set_thumbnail(url=member.avatar.url)

    embed.add_field(name="Starting Pts", value=aggregation.started_rank_points, inline=True)
    diff = (
        "+" + str(aggregation.total_gained_points) + " ⭐"
        if aggregation.total_gained_points > 0
        else str(aggregation.total_gained_points)
    )
    embed.add_field(name="Ending Pts", value=f"{aggregation.ended_rank_points}", inline=True)
    embed.add_field(name="Pts Variation", value=diff, inline=True)
    embed.add_field(name="Kills", value=aggregation.total_kill_count, inline=True)
    embed.add_field(name="Deaths", value=aggregation.total_death_count, inline=True)
    embed.add_field(name="Assists", value=aggregation.total_assist_count, inline=True)
    embed.add_field(name="TK", value=aggregation.total_tk_count, inline=True)
    embed.add_field(name="3k round", value=add_star_if_above_value(aggregation.total_round_with_3k), inline=True)
    embed.add_field(name="4k round", value=add_star_if_above_value(aggregation.total_round_with_4k), inline=True)
    embed.add_field(name="Ace round", value=aggregation.total_round_with_aces, inline=True)
    embed.add_field(
        name="Clutch Wins", value=add_star_if_above_value(aggregation.total_clutches_win_count), inline=True
    )
    embed.add_field(name="Clutch Loss", value=aggregation.total_clutches_loss_count, inline=True)
    embed.add_field(name="First Kill", value=aggregation.total_first_kill_count, inline=True)
    embed.add_field(name="First Death", value=aggregation.total_first_death_count, inline=True)
    embed.add_field(name="Kill/Death/Asssist Per Match", value=str_kda, inline=False)
    embed.set_footer(text=f"Your stats for the last {last_hour} hours")
    return embed


def add_star_if_above_value(value: int, threshold: int = 0) -> str:
    """Add a star if the value is above the threshold"""
    return f"{value}{'⭐' if value > threshold else ''}"
