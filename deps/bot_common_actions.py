"""Common Actions that the bots Cogs or Bots can invoke"""

import asyncio
import io
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Mapping, Optional, Union
from gtts import gTTS  # type: ignore
import discord
from deps.browser import (
    download_full_matches_async,
    download_full_user_information_async,
    download_operator_stats_for_users_async,
)
from deps.analytic_data_access import (
    data_access_set_max_mmr,
    data_access_set_r6_tracker_id,
    fetch_user_info_by_user_id,
    get_active_user_info,
    insert_if_nonexistant_full_match_info,
    insert_if_nonexistant_full_user_info,
)
from deps.data_access_data_class import UserInfo
from deps.operator_stats_data_access import upsert_operator_stats
from deps.data_access import (
    data_access_add_list_member_stats,
    data_access_get_bot_voice_first_user,
    data_access_get_channel,
    data_access_get_daily_message_id,
    data_access_get_gaming_session_last_activity,
    data_access_get_gaming_session_text_channel_id,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_guild_username_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_last_bot_message_in_main_text_channel,
    data_access_get_list_member_stats,
    data_access_get_main_text_channel_id,
    data_access_get_member,
    data_access_get_message,
    data_access_get_r6tracker_max_rank,
    data_access_get_reaction_message,
    data_access_get_voice_user_list,
    data_access_set_daily_message_id,
    data_access_set_gaming_session_last_activity,
    data_access_set_last_bot_message_in_main_text_channel,
    data_access_set_reaction_message,
    data_acess_remove_list_member_stats,
)
from deps.mybot import MyBot
from deps.models import (
    ActivityTransition,
    SimpleUser,
    UserMatchInfoSessionAggregate,
    UserQueueForStats,
    UserWithUserInformation,
    UserWithUserMatchInfo,
)
from deps.log import print_error_log, print_log, print_warning_log
from deps.functions_model import get_empty_votes
from deps.functions_date import get_current_hour_eastern, is_today
from deps.functions import (
    get_last_schedule_message,
    get_url_user_profile_main,
    get_url_user_profile_overview,
    set_member_role_from_rank,
)
from deps.values import (
    DELAY_BETWEEN_DISCORD_ACTIONS_SECONDS,
    MATCH_START_GIF_DELETE_AFTER_SECONDS,
    STATS_HOURS_WINDOW_IN_PAST,
    SUPPORTED_TIMES_STR,
)
from deps.siege import get_aggregation_siege_activity, get_color_for_rank, get_list_users_with_rank, get_user_rank_emoji
from deps.functions_r6_tracker import get_user_gaming_session_stats, parse_operator_stats_from_json
from deps.functions_schedule import (
    adjust_reaction,
    get_daily_embed_message,
    auto_assign_user_to_daily_question,
    update_vote_message,
)
from deps.match_start_gif import generate_match_start_gif
from ui.schedule_buttons import ScheduleButtons


async def send_daily_question_to_a_guild(bot: MyBot, guild: discord.Guild):
    """
    Send the daily schedule question to a specific guild
    If there is an existing message, we update. This is importantto have always the View connected to the callbacks
    So, if the bot disconnects, the view will be reconnected to the callback
    """
    guild_id = guild.id

    channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(f"\t⚠️ Channel id (schedule channel) not found for guild {guild.name}. Skipping.")
        return

    channel = await data_access_get_channel(channel_id)
    if channel is None:
        print_error_log(f"send_daily_question_to_a_guild: Channel not found for guild {guild.name}. Skipping.")
        return
    # last_message_id = await data_access_get_daily_message_id(guild_id)
    # last_message = None

    # ⚠️TEMPORARY CODE START
    # if last_message_id is None:
    last_message = await get_last_schedule_message(
        bot, channel
    )  # 23 just to make sure the script will create a new entry every 24 hours. Giving some buffer to avoid editing the message by the script
    if last_message is not None:
        # last_message_id = last_message.id
        if is_today(last_message.created_at):
            print_warning_log(
                f"\t⚠️ Daily message already in Discord for guild {guild.name}. Updating the message and skipping pushing a new message."
            )
            channel_message_votes = await data_access_get_reaction_message(guild_id, channel_id, last_message.id)
            if channel_message_votes is None:
                channel_message_votes = get_empty_votes()
            await update_vote_message(
                last_message, channel_message_votes, bot.guild_emoji
            )  # Will edit and make the buttons work again
            return
    # ⚠️TEMPORARY CODE END
    # if last_message_id is not None:
    #    last_message = await data_access_get_message(guild_id, channel_id, last_message_id)

    # if last_message is None:
    #     votes = None
    # else:
    #     votes = await data_access_get_reaction_message(guild_id, channel_id, last_message.id)

    # Votes can be none because last message was not there or the message was not voted yet
    votes = get_empty_votes()
    embed_msg = get_daily_embed_message(votes)  # The message to show (new or edited)
    view = ScheduleButtons(bot.guild_emoji, adjust_reaction)  # Always re-create the buttons for the callbacks
    message: discord.Message = await channel.send(content="", embed=embed_msg, view=view)
    await auto_assign_user_to_daily_question(guild_id, channel_id, message, bot.guild_emoji)
    data_access_set_daily_message_id(guild_id, message.id)
    print_log(f"\t✅ Daily new schedule message sent in guild {guild.name}")


async def check_voice_channel(bot: MyBot):
    """
    Run when the bot start and every X minutes to update the cache of the users in the voice channel and update the schedule
    """

    for guild in bot.guilds:
        guild_id = guild.id
        emoji_guild: Dict[str, str] = bot.guild_emoji.get(guild_id, {})
        if len(emoji_guild) == 0:
            print_warning_log(f"check_voice_channel: No emoji found for guild {guild.name}. Skipping.")
            continue
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
        # last_message_id = await data_access_get_daily_message_id(guild_id)
        last_message = await get_last_schedule_message(bot, text_channel)
        last_message_id = last_message.id if last_message is not None else None
        if last_message_id is None:
            print_warning_log(f"check_voice_channel: No message found in the channel {text_channel.name}. Skipping.")
            continue
        message_votes = await data_access_get_reaction_message(guild_id, text_channel_id, last_message_id)
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
                        f"check_voice_channel: User {user.id} already voted for {current_hour_str} in message {last_message_id}"
                    )
                    continue
                # Add the user to the message votes
                found_new_user = True

                message_votes.setdefault(current_hour_str, []).append(
                    SimpleUser(
                        user.id,
                        user.display_name,
                        get_user_rank_emoji(emoji_guild, user),
                    )
                )

        if found_new_user:
            print_log(f"check_voice_channel: Updating voice channel cache for {guild.name} and updating the message")
            # Always update the cache
            data_access_set_reaction_message(guild_id, text_channel_id, last_message_id, message_votes)
            last_discord_msg = await data_access_get_message(guild_id, text_channel_id, last_message_id)
            if last_discord_msg is None:
                print_log(
                    f"check_voice_channel: Discord message not found for {guild.name} and msg id {last_message_id}. Skipping."
                )
            else:
                await update_vote_message(last_discord_msg, message_votes, bot.guild_emoji)
                print_log(f"check_voice_channel: Updated voice channel cache for {guild.name}")


async def send_notification_voice_channel(
    guild_id: int,
    member: discord.Member,
    voice_channel: Union[discord.VoiceChannel, discord.StageChannel],
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
    #     f"You're the only one in the voice channel: Feel free to message the Siege channel with \"/lfg\" to find other players and check the other players' schedule in <#{text_channel_id}>."
    # )
    channel_schedule: Optional[discord.TextChannel] = await data_access_get_channel(schedule_text_channel_id)
    channel_name = channel_schedule.name if channel_schedule is not None else "schedule"
    list_simple_users = await get_users_scheduled_today_current_hour(guild_id, get_current_hour_eastern())
    list_simple_users = list(filter(lambda x: x.user_id != member.id, list_simple_users))
    if len(list_simple_users) > 0:
        other_members = ", ".join([f"{user.display_name}" for user in list_simple_users])
        text_message = f"Hello {member.display_name}! {other_members} are scheduled to play at this time. Check the bot {channel_name} channel."
    else:
        # Check next hour
        list_simple_users = await get_users_scheduled_today_current_hour(guild_id, get_current_hour_eastern(1))
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
        voice_client: discord.VoiceClient = await voice_channel.connect()

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


async def get_users_scheduled_today_current_hour(guild_id: int, current_hour_str: str) -> List[SimpleUser]:
    """
    Get the list of users scheduled for the current day and hour
    current_hour_str: The current hour in the format "3am"
    """
    channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
    if channel_id is None:
        print_warning_log(
            f"get_users_scheduled_today_current_hour: Text channel not set for guild {guild_id}. Skipping."
        )
        return []
    last_message_id = await data_access_get_daily_message_id(guild_id)

    if last_message_id is None:
        print_warning_log(
            f"get_users_scheduled_today_current_hour: No message id found for guild {guild_id}. Skipping."
        )
        return []

    # Cache all users for this message's reactions to avoid redundant API calls
    message_votes = await data_access_get_reaction_message(guild_id, channel_id, last_message_id)
    if message_votes is None:
        message_votes = get_empty_votes()
    if current_hour_str not in message_votes:
        return []
    return message_votes[current_hour_str]


async def adjust_role_from_ubisoft_max_account(
    guild: discord.Guild,
    member: discord.Member,
    ubisoft_connect_name: str,
    ubisoft_active_account: Union[str, None] = None,
) -> tuple[str, int]:
    """Adjust the server's role of a user based on their max rank in R6 Tracker"""
    max_rank, max_mmr = await data_access_get_r6tracker_max_rank(ubisoft_connect_name, True)
    print_log(
        f"""adjust_role_from_ubisoft_max_account: R6 Tracker Downloaded Info for user {member.display_name} and found for user name {ubisoft_connect_name} the max role: {max_rank}"""
    )
    try:
        await set_member_role_from_rank(guild, member, max_rank)
    except Exception as e:
        print_error_log(f"adjust_role_from_ubisoft_max_account: Error setting the role: {e}")
        return ("", 0)

    text_channel_id = await data_access_get_guild_username_text_channel_id(guild.id)
    if text_channel_id is None:
        print_warning_log(
            f"adjust_role_from_ubisoft_max_account: Text channel not set for guild {guild.name}. Skipping."
        )
        return max_rank, max_mmr

    # Retrieve the moderator role by name
    mod_role = discord.utils.get(guild.roles, name="Mod")

    if mod_role is None:
        print_warning_log(f"adjust_role_from_ubisoft_max_account: Mod role not found in guild {guild.name}. Skipping.")
        return ("", 0)
    channel = await data_access_get_channel(text_channel_id)
    if ubisoft_active_account is None or channel is None:
        active_msg = ""
        return ("", 0)
    else:
        active_msg = f"""\nCurrently playing on the [{ubisoft_active_account}]({get_url_user_profile_overview(ubisoft_active_account)}) account."""

    await channel.send(
        content=f"""{member.mention} main account is [{ubisoft_connect_name}]({get_url_user_profile_overview(ubisoft_connect_name)}) with max rank of `{max_rank}`.{active_msg}\n{mod_role.mention} please confirm the max account belong to this person.""",
    )
    return max_rank, max_mmr


async def send_session_stats_directly(member: discord.Member, guild_id: int) -> None:
    """
    Get the statistic of a user and post it
    """
    await send_session_stats_to_queue(member, guild_id)
    await post_queued_user_stats(False)


async def send_session_stats_to_queue(member: discord.Member, guild_id: int) -> None:
    """
    Get the statistic of a user and add the request into a queue
    """

    if member.bot:
        return  # Ignore bot

    channel_id = await data_access_get_gaming_session_text_channel_id(guild_id)
    if channel_id is None:
        print_warning_log(f"send_session_stats_to_queue: Text channel not set for guild {guild_id}. Skipping.")
        return

    member_id = member.id
    member_name = member.display_name

    # Only perform the action if it wasn't done in the last hour
    current_time = datetime.now(timezone.utc)
    last_activity = await data_access_get_gaming_session_last_activity(member_id, guild_id)
    # Only shows the stats once per hour per user maximum
    if last_activity is not None and last_activity > current_time - timedelta(hours=1):
        print_log(f"User {member_name} already has stats in the last hour")
        return

    # Get the user ubisoft name
    user_info = await fetch_user_info_by_user_id(member_id)
    if user_info is None or user_info.ubisoft_username_active is None:
        print_log(f"User {member_name} has no active Ubisoft account set")
        return

    # Queue the request to get the user stats with the time which allows to delay the
    # transmission of about 5 minutes to avoid missing the last match
    user = UserQueueForStats(user_info, guild_id, current_time)
    await data_access_add_list_member_stats(user)
    print_log(f"User {member_name} added to the queue to get the stats")


async def post_queued_user_stats(check_time_delay: bool = True) -> None:
    """
    Get the stats for all the users in the queue and post it
    The function relies on opening a browser once and get all the users
    from the queue to get their stats at the same time
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

    if len(users) == 0:
        return

    # Accumulate all the stats for all the users before posting them
    all_users_matches = await download_full_matches_async(users)

    # Post to the channel the stats for the users who disconnected
    try:
        # Persist the data into the database
        for user_stats in all_users_matches:
            insert_if_nonexistant_full_match_info(user_stats.user_request_stats.user_info, user_stats.match_stats)
    except Exception as e:
        print_error_log(f"post_post_queued_user_stats: Error persisting the data: {e}")
    try:
        # Send the stats to the channel
        await send_channel_list_stats(all_users_matches)
    except Exception as e:
        print_error_log(f"post_post_queued_user_stats: Error sending the stats: {e}")


async def send_channel_list_stats(users_stats: List[UserWithUserMatchInfo]) -> None:
    """Post on the channel all the stats"""
    current_time = datetime.now(timezone.utc)
    last_hour = STATS_HOURS_WINDOW_IN_PAST
    time_past = current_time - timedelta(hours=last_hour)
    for user_stats in users_stats:
        user_info = user_stats.user_request_stats.user_info
        member_id = user_info.id
        guild_id = user_stats.user_request_stats.guild_id
        if user_info.ubisoft_username_active is None:
            print_log(f"send_channel_list_stats: User {user_info.display_name} has no active Ubisoft account set")
            continue
        try:
            await data_acess_remove_list_member_stats(user_stats.user_request_stats)
            aggregation: Optional[UserMatchInfoSessionAggregate] = get_user_gaming_session_stats(
                user_info.ubisoft_username_active, time_past, user_stats.match_stats
            )
            if aggregation is None:
                print_log(
                    f"""send_channel_list_stats: User {user_info.display_name} has no stats to show in the last {last_hour} hours. Overall stats found {len(users_stats)}"""
                )
                continue  # Skip to the next user

            channel_id = await data_access_get_gaming_session_text_channel_id(guild_id)
            if channel_id is None:
                print_warning_log(f"send_channel_list_stats: Text channel not set for guild {guild_id}. Skipping.")
                continue
            channel = await data_access_get_channel(channel_id)
            if channel is None:
                print_warning_log(f"send_channel_list_stats: Text channel not found for guild {guild_id}. Skipping.")
                continue
            member = await data_access_get_member(guild_id, member_id)
            if member is None:
                print_error_log(f"send_channel_list_stats: Member {member_id} not found in guild {guild_id}")
                continue  # Skip to the next user
            # We never sent the message, so we send it, add the reactions and save it in the cache
            embed_msg = get_gaming_session_user_embed_message(member, user_info, aggregation, last_hour)
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
    member: discord.Member, user_info: UserInfo, aggregation: UserMatchInfoSessionAggregate, last_hour: int
) -> discord.Embed:
    """Create the stats message"""
    title = f"{member.display_name} Stats"
    embed = discord.Embed(
        title=title,
        description=f"""{member.mention} ({user_info.ubisoft_username_active}) played {aggregation.match_count} matches: {aggregation.match_win_count} wins and {aggregation.match_loss_count} losses.""",
        color=get_color_for_rank(member),
        timestamp=datetime.now(),
        url=get_url_user_profile_main(aggregation.ubisoft_username_active),
    )

    # Get the list of kill_death into a string with comma separated
    str_kda = "\n".join(
        f"""Match #{i+1} - {'won 🏆' if match.has_win else 'lose ☠'} - {match.map_name}: {match.kill_count}/{match.death_count}/{match.assist_count}"""
        for i, match in enumerate(reversed(aggregation.matches_recent))
    )
    if member.avatar is not None:
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
    embed.add_field(
        name="Ace (5k) round", value=add_star_if_above_value(aggregation.total_round_with_aces), inline=True
    )
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


async def send_automatic_lfg_message(bot: MyBot, guild_id: int, voice_channel_id: int) -> None:
    """
    Send a message to the main text channel about looking for group to play
    """

    dict_users: Mapping[int, ActivityTransition] = await data_access_get_voice_user_list(guild_id, voice_channel_id)
    if dict_users is None:
        # No user, nothing to do
        return

    # Get the text channel to send the message
    text_channel_main_siege_id = await data_access_get_main_text_channel_id(guild_id)
    if text_channel_main_siege_id is None:
        print_warning_log(
            f"send_automatic_lfg_message: Main Siege text channel id not set for guild id {guild_id}. Skipping."
        )
        return
    channel = await data_access_get_channel(text_channel_main_siege_id)
    if not channel:
        print_warning_log(
            f"send_automatic_lfg_message: Main Siege text channel not found for guild id {guild_id}. Skipping."
        )
        return

    # Commented because the dict_users might not have all users since the activity is optional in Discord. Better do the rule about the user count using the vc_channel.members (we sdo it below)
    # Check the number of users in the voice channel
    # user_count = len(dict_users)
    # if user_count == 0 or user_count >= 5:
    #     # No user or too many users, nothing to do
    #     # print_log(
    #     #     f"""send_automatic_lfg_message: User count {user_count} in guild id {guild_id} for voice channel {voice_channel_id}. Skipping."""
    #     # )
    #     return

    current_time = datetime.now(timezone.utc)
    last_message_time: Optional[datetime] = await data_access_get_last_bot_message_in_main_text_channel(
        guild_id, voice_channel_id
    )

    if last_message_time is not None:
        delta = current_time - last_message_time
        # To avoid spamming, we allow only one message every x minutes maximum
        if delta < timedelta(minutes=15):
            return

    # Get current voice channel information
    vc_channel = await data_access_get_channel(voice_channel_id)
    if vc_channel is None:
        print_warning_log(
            f"""send_automatic_lfg_message: Voice channel {voice_channel_id} not found for guild id {guild_id} . Skipping."""
        )
        return
    # Redundant check since we checked with the data_access_get_voice_user_list but we want to be sure
    user_count_vc = len(vc_channel.members)
    if user_count_vc >= 5:
        # print_log(
        #     f"send_automatic_lfg_message: {user_count_vc} users in the voice channel, no need to send the message."
        # )
        return
    needed_user = 5 - user_count_vc
    # At this point, we have 1 to 4 users in the voice channel, we still miss few to get 5
    try:
        aggregation = get_aggregation_siege_activity(dict_users)
        print_log(
            f"""send_automatic_lfg_message: count_in_menu {aggregation.count_in_menu}, game_not_started {aggregation.game_not_started}, user_leaving {aggregation.user_leaving}, warming_up {aggregation.warming_up}, done_warming_up {aggregation.done_warming_up_waiting_in_menu}, done_match_waiting_in_menu {aggregation.done_match_waiting_in_menu}, playing_rank {aggregation.playing_rank}, playing_standard {aggregation.playing_standard} for voice channel {voice_channel_id}"""
        )
        ready_to_play = aggregation.done_match_waiting_in_menu + aggregation.done_warming_up_waiting_in_menu
        already_playing = aggregation.playing_rank + aggregation.playing_standard
        if ready_to_play > 0 and ready_to_play > already_playing:
            list_users = get_list_users_with_rank(bot, vc_channel.members, guild_id)
            print_log(f"🎮 {list_users} are looking for {needed_user} teammates to play in <#{voice_channel_id}>")
            await channel.send(
                f"🎮 {list_users} are looking for {needed_user} teammates to play in <#{voice_channel_id}>"
            )
            data_access_set_last_bot_message_in_main_text_channel(guild_id, voice_channel_id, current_time)
    except Exception as e:
        print_error_log(f"send_automatic_lfg_message: Error sending the message: {e}")
        return


async def persist_siege_matches_cross_guilds(from_time: datetime, to_time: datetime) -> None:
    """
    Fetch and persist the matches between two dates for user who were active
    """
    # Get the list of user who were active between the time
    users: List[UserInfo] = get_active_user_info(from_time, to_time)
    # Log all users we found active
    print_log(f"persist_siege_matches_cross_guilds: Found {len(users)} active users between {from_time} and {to_time}")
    print_log(f"persist_siege_matches_cross_guilds: Active users: {[user.display_name for user in users]}")
    users_stats: List[UserQueueForStats] = [UserQueueForStats(user, 0, from_time) for user in users]
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    all_users_matches = await download_full_matches_async(users_stats)

    # Persist the match info in the database
    # Persist the r6 tracker UUID in the user profile table if available

    # Use the matches that we downloaded
    for user_and_matches in all_users_matches:
        # Save the matches in the database
        user_info = user_and_matches.user_request_stats.user_info
        match_stats = user_and_matches.match_stats
        try:
            insert_if_nonexistant_full_match_info(user_info, match_stats)
        except Exception as e:
            print_error_log(f"persist_siege_matches_cross_guilds: Error saving the match info: {e}")
            continue

        # Add r6 tracker UUID to the user profile table if available
        if user_info.r6_tracker_active_id is None and len(match_stats) > 0:
            # Update user with the R6 tracker if if it wasn't available before
            r6_id = match_stats[0].r6_tracker_user_uuid
            data_access_set_r6_tracker_id(user_info.id, r6_id)


async def fetch_and_persist_operator_stats(users: List[UserInfo]) -> None:
    """
    Fetch and persist operator statistics for all active users.
    Uses BrowserContextManager to fetch data with proper cookies and rate limiting.

    Args:
        users: List of UserInfo objects with r6_tracker_active_id
    """
    print_log(f"fetch_and_persist_operator_stats: Starting collection for {len(users)} users")

    # Download operator stats using BrowserContextManager (with built-in rate limiting)
    all_operator_data = await download_operator_stats_for_users_async(users)

    # Parse and store the data
    for user, operator_data in all_operator_data:
        try:
            # Parse the operator stats
            operator_stats = parse_operator_stats_from_json(operator_data, user.id)

            if operator_stats:
                # Store in database
                upsert_operator_stats(operator_stats)
                print_log(
                    f"fetch_and_persist_operator_stats: Saved {len(operator_stats)} operator stats for {user.display_name}"
                )
            else:
                print_log(f"fetch_and_persist_operator_stats: No operator stats found for {user.display_name}")

        except Exception as e:
            print_error_log(f"fetch_and_persist_operator_stats: Error processing stats for {user.display_name}: {e}")
            continue

    print_log(f"fetch_and_persist_operator_stats: Completed collection for {len(all_operator_data)} users")


async def persist_user_full_information_cross_guilds(from_time: datetime, to_time: datetime) -> None:
    """
    Fetch and persist the user full information between two dates
    """

    # Get the list of user who were active between the time
    users: List[UserInfo] = get_active_user_info(from_time, to_time)
    users_stats: List[UserQueueForStats] = [UserQueueForStats(user, 0, from_time) for user in users]
    # Before the loop, start the browser and do a request to the R6 tracker to get the cookies
    # Then, in the loop, use the cookies to get the stats using the API
    all_users = await download_full_user_information_async(users_stats)

    # Persist the full user information in the database
    for full_user_stats_info in all_users:
        # Save the matches in the database
        try:
            insert_if_nonexistant_full_user_info(
                full_user_stats_info.user_request_stats.user_info, full_user_stats_info.full_stats
            )
        except Exception as e:
            print_error_log(f"persist_user_full_information_cross_guilds: Error saving the user full stats info: {e}")
            continue

    # Fetch and persist operator statistics for all active users
    print_log("persist_user_full_information_cross_guilds: Starting operator stats collection...")
    await fetch_and_persist_operator_stats(users)


async def move_members_between_voice_channel(
    source_voice_channel: Union[discord.VoiceChannel, discord.StageChannel],
    target_voice_channel: Union[discord.VoiceChannel, discord.StageChannel],
) -> None:
    """
    Move all members from one voice channel to another
    """
    for member in source_voice_channel.members:
        try:
            await member.move_to(target_voice_channel)
            print_log(
                f"Moved member {member.display_name} from {source_voice_channel.name} to channel {target_voice_channel.name}"
            )
            await asyncio.sleep(DELAY_BETWEEN_DISCORD_ACTIONS_SECONDS)
        except Exception as e:
            print_error_log(f"Error moving member {member.display_name}: {e}")


async def send_match_start_gif(bot: MyBot, guild_id: int, voice_channel_id: int) -> None:
    """
    Generate and send match start GIF to main text channel.

    Args:
        bot: Bot instance
        guild_id: Guild ID
        voice_channel_id: Voice channel ID where the match is starting
    """
    try:
        # Get voice channel and members
        vc_channel = await data_access_get_channel(voice_channel_id)
        if not vc_channel or not vc_channel.members:
            print_log(f"send_match_start_gif: No voice channel or members found for channel {voice_channel_id}")
            return

        # Get text channel
        text_channel_id = await data_access_get_main_text_channel_id(guild_id)
        text_channel = await data_access_get_channel(text_channel_id)
        if not text_channel:
            print_log(f"send_match_start_gif: No main text channel found for guild {guild_id}")
            return

        # Generate GIF
        print_log(f"send_match_start_gif: Generating GIF for {len(vc_channel.members)} members in {vc_channel.name}")
        gif_bytes = await generate_match_start_gif(vc_channel.members, guild_id, bot.guild_emoji.get(guild_id, {}))

        if not gif_bytes:
            print_log("send_match_start_gif: GIF generation returned no data")
            return

        # Send to Discord with automatic deletion
        file = discord.File(fp=io.BytesIO(gif_bytes), filename="match_start.gif")
        await text_channel.send(
            f"🎮 Match starting in <#{voice_channel_id}>! Good luck!",
            file=file,
            delete_after=MATCH_START_GIF_DELETE_AFTER_SECONDS,
        )
        print_log(
            f"send_match_start_gif: Successfully sent GIF to {text_channel.name} "
            f"(will auto-delete after {MATCH_START_GIF_DELETE_AFTER_SECONDS // 60} minutes)"
        )

    except Exception as e:
        print_error_log(f"send_match_start_gif: Error: {e}")
