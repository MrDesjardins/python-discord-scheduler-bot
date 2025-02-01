"""This module contains the functions for the schedule command."""

import asyncio
from datetime import datetime, timedelta, timezone, date
from typing import Dict, List, Union
import discord
from deps.data_access import (
    data_access_get_channel,
    data_access_get_daily_message_id,
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
from deps.values import DATE_FORMAT, COMMAND_SCHEDULE_ADD, MSG_UNIQUE_STRING

lock = asyncio.Lock()


async def adjust_reaction(guild_emoji: dict[str, Dict[str, str]], interaction: discord.Interaction, time_clicked: str):
    """Adjust the reaction with add or remove"""

    channel_id = interaction.channel_id
    guild_id = interaction.guild_id
    message_id = interaction.message.id
    user_id = interaction.user.id

    last_message_id = await data_access_get_daily_message_id(guild_id)
    print_log(f"DB Latest Msg ID {last_message_id}, and interaction Msg ID {message_id}")

    guild: discord.Guild = await data_access_get_guild(guild_id)
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    text_message_reaction: discord.Message = await data_access_get_message(guild_id, channel_id, message_id)
    user: discord.User = await data_access_get_user(guild_id, user_id)
    member: discord.Member = await data_access_get_member(guild_id, user_id)
    text_channel_configured_for_bot: discord.TextChannel = await data_access_get_guild_schedule_text_channel_id(
        guild_id
    )

    if user is None:
        print_error_log(f"adjust_reaction: User not found for user {user_id}. Skipping.")
        return

    if member is None:
        print_error_log(f"adjust_reaction: Member not found for user {user_id}. Skipping.")
        return

    # We do not act on message that are not in the Guild's text channel
    if text_channel_configured_for_bot is None or text_channel_configured_for_bot != channel_id:
        # The reaction was on another channel, we allow it
        return

    if not channel or not text_message_reaction or not user or not guild or not member:
        print_log("adjust_reaction: End-Before Adjusting reaction")
        return

    if user.bot:
        return  # Ignore reactions from bots

    # Check if the message is older than 24 hours
    if text_message_reaction.created_at < datetime.now(timezone.utc) - timedelta(days=1):
        await user.send("You can't vote on a message that is older than 24 hours.")
        return
    print_log("adjust_reaction: Start (lock) Adjusting reaction")
    async with lock:  # Acquire the lock
        # Cache all users for this message's reactions to avoid redundant API calls
        channel_message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
        if channel_message_votes is None:
            channel_message_votes = get_empty_votes()
        # Add or Remove Action
        people_clicked_time: list[SimpleUser] = channel_message_votes.get(time_clicked, [])
        users_clicked = [user.id == u.user_id for u in people_clicked_time]
        remove = len(users_clicked) > 0
        if remove:
            # Remove the user from the message votes
            channel_message_votes[time_clicked] = [u for u in people_clicked_time if u.user_id != user.id]
        else:
            # Add the user to the message votes
            channel_message_votes.setdefault(time_clicked, []).append(
                SimpleUser(
                    user.id,
                    user.display_name,
                    get_user_rank_emoji(guild_emoji[guild_id], member),
                )
            )
        # Always update the cache
        data_access_set_reaction_message(guild_id, channel_id, message_id, channel_message_votes)
    print_log("adjust_reaction: End Adjusting reaction")

    await update_vote_message(text_message_reaction, channel_message_votes)


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

    embed = discord.Embed(title="Schedule", description=vote_message, color=0x00FF00, timestamp=datetime.now())

    embed.set_footer(
        text=f"⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nYou can use `/{COMMAND_SCHEDULE_ADD}` to set recurrent day and hours or click the emoji corresponding to your time:"
    )
    return embed


async def auto_assign_user_to_daily_question(
    guild_id: int, channel_id: int, message: discord.Message
) -> Dict[str, List[SimpleUser]]:
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
    return message_votes
