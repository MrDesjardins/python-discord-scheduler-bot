"""This module contains the functions for the schedule command."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Union
import discord
import json
from deps.data_access import (
    data_access_get_channel,
    data_access_get_guild,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_member,
    data_access_get_message,
    data_access_get_reaction_message,
    data_access_get_user,
    data_access_get_users_auto_schedule,
    data_access_set_reaction_message,
)
from deps.log import print_log, print_error_log
from deps.models import SimpleUser, SimpleUserHour
from deps.siege import get_user_rank_emoji
from deps.functions_model import get_empty_votes
from deps.values import DATE_FORMAT, COMMAND_SCHEDULE_ADD, MSG_UNIQUE_STRING, SUPPORTED_TIMES_ARR
from deps.functions_date import get_now_eastern
from deps.performance import PerformanceContext
from ui.schedule_buttons import ScheduleButtons

lock = asyncio.Lock()


async def adjust_reaction(
    guild_emoji: dict[int, Dict[str, str]], interaction: discord.Interaction, time_clicked: str
) -> None:
    """Adjust the reaction with add or remove"""

    channel_id = interaction.channel_id
    if channel_id is None:
        print_error_log("adjust_reaction: No channel_id found in the interaction. Skipping.")
        return
    guild_id = interaction.guild_id
    if guild_id is None:
        print_error_log("adjust_reaction: No guild_id found in the interaction. Skipping.")
        return
    if interaction.message is None:
        print_error_log("adjust_reaction: No message found in the interaction. Skipping.")
        return
    message_id = interaction.message.id
    user_id = interaction.user.id

    guild: Union[discord.Guild, None] = await data_access_get_guild(guild_id)
    channel: Union[discord.TextChannel, None] = await data_access_get_channel(channel_id)
    text_message_reaction: Union[discord.Message, None] = await data_access_get_message(
        guild_id, channel_id, message_id
    )
    user: Union[discord.User, None] = await data_access_get_user(guild_id, user_id)
    member: Union[discord.Member, None] = await data_access_get_member(guild_id, user_id)
    text_channel_configured_for_bot_id: Union[int, None] = await data_access_get_guild_schedule_text_channel_id(
        guild_id
    )

    if user is None:
        print_error_log(f"adjust_reaction: User not found for user {user_id}. Skipping.")
        return

    if member is None:
        print_error_log(f"adjust_reaction: Member not found for user {user_id}. Skipping.")
        return
    user_display_name = member.display_name

    # We do not act on message that are not in the Guild's text channel
    if text_channel_configured_for_bot_id is None or text_channel_configured_for_bot_id != channel_id:
        # The reaction was on another channel, we allow it
        return

    if channel is None or text_message_reaction is None or guild is None:
        print_log("adjust_reaction: End-Before Adjusting reaction because of channel, message or guild not found")
        return

    if user.bot:
        return  # Ignore reactions from bots

    # Check if the message is older than 24 hours
    if text_message_reaction.created_at < datetime.now(timezone.utc) - timedelta(days=1):
        await user.send(f"You can't vote on a message that is older than 24 hours. User: {user_display_name}")
        return

    channel_message_votes = await get_adjust_reaction_votes(
        guild_id,
        channel_id,
        message_id,
        SimpleUser(
            user.id,
            user.display_name,
            get_user_rank_emoji(guild_emoji[guild_id], member),
        ),
        time_clicked,
    )
    await update_vote_message(text_message_reaction, channel_message_votes, guild_emoji)


async def get_adjust_reaction_votes(
    guild_id: int, channel_id: int, message_id: int, user: SimpleUser, time_clicked: str
) -> Dict[str, List[SimpleUser]]:
    """
    Adjust the reaction for the user on the message at the time the user clicked
    """
    print_log(f"adjust_reaction: Start (lock) Adjusting reaction for {user.display_name}")
    with PerformanceContext("adjust_reaction", None) as perf:
        async with lock:  # Acquire the lock to ensure get + set under one transaction
            channel_message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
            perf.add_marker("Get Reaction Message Completed")
            if channel_message_votes is None:
                channel_message_votes = get_empty_votes()
            # Add or Remove Action
            people_clicked_time: list[SimpleUser] = channel_message_votes.get(time_clicked, [])
            users_clicked_already = any(u.user_id == user.user_id for u in people_clicked_time)
            perf.add_marker(f"Saving Reaction Message: Before count {len(people_clicked_time)}")
            if users_clicked_already:
                # Remove the user from the message votes
                channel_message_votes[time_clicked] = [u for u in people_clicked_time if u.user_id != user.user_id]
            else:
                # Add the user to the message votes
                people_clicked_time.append(user)
                channel_message_votes[time_clicked] = people_clicked_time
            perf.add_marker(f"Saving Reaction Message: After count {len(people_clicked_time)}")
            # Always update the cache
            data_access_set_reaction_message(guild_id, channel_id, message_id, channel_message_votes)
            perf.add_marker("Saving Reaction Message End")
    return channel_message_votes


async def update_vote_message(
    message: discord.Message, vote_for_message: Dict[str, List[SimpleUser]], guild_emoji: dict[int, Dict[str, str]]
):
    """Update the votes per hour on the bot message"""
    embed_msg = get_daily_embed_message(vote_for_message)
    print_log("update_vote_message: Updated Message")
    await message.edit(
        content="", embed=embed_msg, view=ScheduleButtons(guild_emoji, adjust_reaction)
    )  # Always re-create the buttons for the callbacks)


def get_daily_embed_message(vote_for_message: Dict[str, List[SimpleUser]]) -> discord.Embed:
    """Create the daily message"""
    current_date = get_now_eastern().strftime(DATE_FORMAT)
    vote_message = f"{MSG_UNIQUE_STRING} today **{current_date}**?"
    vote_message += "\n\n**Schedule**\n"
    for key_time in SUPPORTED_TIMES_ARR:
        users = vote_for_message.get(key_time, [])
        if users:
            vote_message += f"{key_time}: {','.join([f'{user.rank_emoji}{user.display_name}' for user in users])}\n"
        else:
            vote_message += f"{key_time}: -\n"

    embed = discord.Embed(title="Schedule", description=vote_message, color=0x00FF00, timestamp=datetime.now())

    embed.set_footer(
        text=f"⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nYou can use `/{COMMAND_SCHEDULE_ADD}` to set recurrent day and hours or click the emoji corresponding to your time:"
    )
    return embed


async def auto_assign_user_to_daily_question(
    guild_id: int, channel_id: int, message: discord.Message, guild_emoji: dict[int, Dict[str, str]]
) -> Dict[str, List[SimpleUser]]:
    """Take the existing schedules for all user and apply it to the message"""
    day_of_week_number = get_now_eastern().weekday()  # 0 is Monday, 6 is Sunday
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
        print_log(json.dumps(message_votes))
        await update_vote_message(message, message_votes, guild_emoji)

    else:
        print_log(f"No schedule found for the day {day_of_week_number}")
    return message_votes
