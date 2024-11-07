#!/usr/bin/env python3
""" Entry file for the Discord bot """

import asyncio
import os
import io
from typing import List, Dict, Optional, Union
from datetime import datetime, timedelta, date, time, timezone
import discord
from gtts import gTTS
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import pytz

from deps.confirmation_rank_view import ConfirmCancelView
from deps.data_access_data_class import UserInfo
from deps.analytic_visualizer import display_graph_cluster_people
from deps.analytic_database import EVENT_CONNECT, EVENT_DISCONNECT
from deps.analytic_data_access import (
    fetch_user_info_by_user_id,
    fetch_user_info_by_user_id_list,
    insert_user_activity,
)
from deps.bot_singleton import BotSingleton
from deps.data_access import (
    data_access_get_bot_voice_first_user,
    data_access_get_channel,
    data_access_get_daily_message,
    data_access_get_guild,
    data_access_get_guild_text_channel_id,
    data_access_get_guild_username_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_member,
    data_access_get_message,
    data_access_get_r6tracker_max_rank,
    data_access_get_reaction_message,
    data_access_get_user,
    data_access_get_users_auto_schedule,
    data_access_reset_guild_cache,
    data_access_set_bot_voice_first_user,
    data_access_set_daily_message,
    data_access_set_guild_text_channel_id,
    data_access_set_guild_username_text_channel_id,
    data_access_set_guild_voice_channel_ids,
    data_access_set_reaction_message,
    data_access_set_users_auto_schedule,
)
from deps.date_utils import is_today
from deps.siege import get_user_rank_emoji
from deps.models import SimpleUser, SimpleUserHour, DayOfWeek
from deps.values import (
    DATE_FORMAT,
    MSG_UNIQUE_STRING,
    SUPPORTED_TIMES_STR,
    EMOJI_TO_TIME,
    DAYS_OF_WEEK,
    COMMAND_SCHEDULE_ADD,
    COMMAND_SCHEDULE_REMOVE,
    COMMAND_SCHEDULE_SEE,
    COMMAND_SET_USER_TIME_ZONE,
    COMMAND_GET_USER_TIME_ZONE,
    COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL,
    COMMAND_ADJUST_RANK,
    COMMAND_SCHEDULE_ADD_USER,
    COMMAND_SCHEDULE_REFRESH_FROM_REACTION,
    COMMAND_FORCE_SEND,
    COMMAND_SCHEDULE_APPLY,
    COMMAND_SET_USER_TIME_ZONE_OTHER_USER,
    COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL,
    COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION,
    COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION,
    COMMAND_GUILD_ENABLE_BOT_VOICE,
    COMMAND_SHOW_COMMUNITY,
    COMMAND_VERSION,
    COMMAND_RESET_CACHE,
)
from deps.functions import (
    get_current_hour_eastern,
    get_empty_votes,
    get_reactions,
    get_sha,
    get_supported_time_time_label,
    get_time_choices,
    get_last_schedule_message,
    most_common,
    set_member_role_from_rank,
)
from deps.log import print_log, print_error_log, print_warning_log
from deps.schedule_day_hours_view import ScheduleDayHours
from deps.timezone_view import TimeZoneView

load_dotenv()

ENV = os.getenv("ENV")
TOKEN = os.getenv("BOT_TOKEN_DEV") if ENV == "dev" else os.getenv("BOT_TOKEN")
HOUR_SEND_DAILY_MESSAGE = 7


bot: discord.Client = BotSingleton().bot

print_log(f"Env: {ENV}")
print_log(f"Token: {TOKEN}")

reactions = get_reactions()
supported_times_time_label = get_supported_time_time_label()

guild_emoji: Dict[str, Dict[str, str]] = {}

lock = asyncio.Lock()


@bot.event
async def on_ready():
    """Main function to run when the bot is ready"""
    print_log(f"{bot.user} has connected to Discord!")
    print_log(f"Bot latency: {bot.latency} seconds")
    for guild in bot.guilds:
        print_log(f"Checking in guild: {guild.name} ({guild.id})")
        print_log(f"\tGuild {guild.name} has {guild.member_count} members, setting the commands")
        guild_obj = discord.Object(id=guild.id)

        # commands_reg = await bot.tree.fetch_commands(guild=guild_obj)
        # for command in commands_reg:
        #     print_log(f"\tDeleting command {command.name}")
        #     await bot.tree.remove_command(command=command.name, guild=guild_obj)

        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print_log(f"\tSynced {len(synced)} commands for guild {guild.name}.")

        commands_reg = await bot.tree.fetch_commands(guild=guild_obj)
        for command in commands_reg:
            print_log(f"\t\t/{command.name}")

        guild_emoji[guild.id] = {}
        for emoji in guild.emojis:
            guild_emoji[guild.id][emoji.name] = emoji.id
            print_log(f"Guild emoji: {emoji.name} -> {emoji.id}")

        channel_id = await data_access_get_guild_text_channel_id(guild.id)
        if channel_id is None:
            print_log(
                f"\tThe administrator of the guild {guild.name} did not configure the channel to send the daily message."
            )
            continue

        channel: discord.TextChannel = await data_access_get_channel(channel_id)

        if channel:
            permissions = check_bot_permissions(channel)
            print_log(f"\tBot permissions in channel {channel.name}: {permissions}")
        else:
            print_warning_log(f"\tChannel ID {channel_id} not found in guild {guild.name}")

    check_voice_channel.start()  # Start the background task
    send_daily_question_to_all_guild.start()  # Start the background task

    # Run it for today (won't duplicate)
    await send_daily_question_to_all_guild()


# local_tz = datetime.now().astimezone().tzinfo
local_tz = pytz.timezone("America/Los_Angeles")
time_send_daily_message = time(hour=HOUR_SEND_DAILY_MESSAGE, minute=0, second=0, tzinfo=local_tz)


@tasks.loop(time=time_send_daily_message)
async def send_daily_question_to_all_guild():
    """
    Send only once every day the question for each guild who has the bot
    """
    print_log(f"Sending daily schedule message, current time {datetime.now()}")
    for guild in bot.guilds:
        await send_daily_question_to_a_guild(guild)


async def send_daily_question_to_a_guild(guild: discord.Guild, force: bool = False):
    """
    Send the daily schedule question to a specific guild
    """
    guild_id = guild.id
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


def check_bot_permissions(channel: discord.TextChannel) -> dict:
    """Check the bot permissions in a specific channel"""
    bot_permissions = channel.permissions_for(channel.guild.me)

    permissions = {
        "read_messages": bot_permissions.read_messages,
        "send_messages": bot_permissions.send_messages,
        "manage_messages": bot_permissions.manage_messages,
        "add_reactions": bot_permissions.add_reactions,
        "read_message_history": bot_permissions.read_message_history,
    }

    return permissions


@bot.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    """User adds a reaction to a message"""
    await adjust_reaction(reaction, False)


@bot.event
async def on_raw_reaction_remove(reaction: discord.RawReactionActionEvent):
    """User removes a reaction to a message"""
    await adjust_reaction(reaction, True)


async def adjust_reaction(reaction: discord.RawReactionActionEvent, remove: bool):
    """Adjust the reaction with add or remove"""

    channel_id = reaction.channel_id
    guild_id = reaction.guild_id
    message_id = reaction.message_id
    user_id = reaction.user_id
    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    text_message_reaction: discord.Message = await data_access_get_message(guild_id, channel_id, message_id)
    user: discord.User = await data_access_get_user(guild_id, user_id)
    guild: discord.Guild = await data_access_get_guild(guild_id)
    member: discord.Member = await data_access_get_member(guild_id, user_id)
    text_channel_configured_for_bot: discord.TextChannel = await data_access_get_guild_text_channel_id(guild_id)
    reaction_emoji = reaction.emoji

    print_log(
        f"adjust_reaction: {'Add' if remove is False else 'Remove'} reaction for {user.id} ({member.display_name}) at time {reaction_emoji}"
    )
    # We do not act on message that are not in the Guild's text channel
    if text_channel_configured_for_bot is None or text_channel_configured_for_bot != channel_id:
        # The reaction was on another channel, we allow it
        return

    if not channel or not text_message_reaction or not user or not guild or not member:
        print_log("End-Before Adjusting reaction")
        return

    if user.bot:
        return  # Ignore reactions from bots

    # Check if the message is older than 24 hours
    if text_message_reaction.created_at < datetime.now(timezone.utc) - timedelta(days=1):
        await user.send("You can't vote on a message that is older than 24 hours.")
        return

    # Ensure no one is adding additional reactions
    emoji_from_list = EMOJI_TO_TIME.get(str(reaction_emoji))
    if emoji_from_list is None:
        await text_message_reaction.remove_reaction(reaction_emoji, member)
        await user.send("You cannot add reaction beside the one provided. Each reaction is a time slot.")
        return

    # Cache all users for this message's reactions to avoid redundant API calls
    channel_message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
    async with lock:
        # In the case there is no vote in the cache, we need to populate it with all the potential votes
        if not channel_message_votes:
            print_log(f"adjust_reaction: Add empty vote for message {message_id}")
            channel_message_votes = get_empty_votes()
            # Iterate over each reaction in the message only if it's not cached
            for react in text_message_reaction.reactions:
                time_voted = EMOJI_TO_TIME.get(str(react.emoji))
                if time_voted:
                    users = [u async for u in react.users() if not u.bot]
                    for user in users:
                        channel_message_votes[time_voted].append(
                            SimpleUser(
                                user.id,
                                member.display_name,
                                get_user_rank_emoji(guild_emoji.get(guild_id), member),
                            )
                        )
            # Always update the cache to avoid other event to save a new empty list of votes
            data_access_set_reaction_message(guild_id, channel_id, message_id, channel_message_votes)
            print_log(f"adjust_reaction: Setting reaction users for message {message_id} in cache")

        # Add or Remove Action
        print_log(f"adjust_reaction: Updating for the current reaction {message_id}")
        time_voted = EMOJI_TO_TIME.get(str(reaction_emoji))
        if remove:
            # Remove the user from the message votes
            for time_v, value in channel_message_votes.items():
                if time_v == time_voted:
                    for single_vote in value:
                        if user.id == single_vote.user_id:
                            print_log(
                                f"adjust_reaction: Found in {message_id} entry of the user for reaction {reaction_emoji}. Removing."
                            )
                            channel_message_votes[time_voted].remove(single_vote)
                            break
        else:
            # Add the user to the message votes
            time_voted = EMOJI_TO_TIME.get(str(reaction_emoji))
            if time_voted:
                if any(user.id == u.user_id for u in channel_message_votes[time_voted]):
                    print_log(
                        f"adjust_reaction: User {user.id} ({member.display_name}) already voted for {time_voted} in message {message_id}"
                    )
                else:
                    channel_message_votes[time_voted].append(
                        SimpleUser(
                            user.id,
                            member.display_name,
                            get_user_rank_emoji(guild_emoji.get(guild_id), member),
                        )
                    )
                    print_log(f"adjust_reaction: Updating reaction users for message {message_id} in cache")
        # Always update the cache
        data_access_set_reaction_message(guild_id, channel_id, message_id, channel_message_votes)

        print_log("adjust_reaction: End Adjusting reaction")
        # await rate_limiter(update_vote_message, message, message_votes)
    # Lock is released here
    await update_vote_message(text_message_reaction, channel_message_votes)


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


def get_daily_string_message(vote_for_message: Dict[str, List[SimpleUser]]) -> str:
    """Create the daily message"""
    current_date = date.today().strftime(DATE_FORMAT)
    vote_message = f"{MSG_UNIQUE_STRING} today **{current_date}**?"
    vote_message += "\n\n**Schedule**\n"
    for key_time, users in vote_for_message.items():
        if users:
            vote_message += f"{key_time}: {','.join([f'{user.rank_emoji}{user.display_name}' for user in users])}\n"
        else:
            vote_message += f"{key_time}: -\n"
    vote_message += f"\n⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nYou can use `/{COMMAND_SCHEDULE_ADD}` to set recurrent day and hours or click the emoji corresponding to your time:"
    return vote_message


async def update_vote_message(message: discord.Message, vote_for_message: Dict[str, List[SimpleUser]]):
    """Update the votes per hour on the bot message"""
    embed_msg = get_daily_embed_message(vote_for_message)
    print_log("update_vote_message: Updated Message")
    await message.edit(content="", embed=embed_msg)


@bot.tree.command(name=COMMAND_SCHEDULE_ADD)
async def add_user_schedule(interaction: discord.Interaction):
    """
    Add a schedule for the active user who perform the command
    """
    view = ScheduleDayHours(guild_emoji)

    await interaction.response.send_message(
        "Choose your day and hour. If you already have a schedule, this new one will add on top of the previous schedule with the new hours for the day choosen.",
        view=view,
        ephemeral=True,
    )


@bot.tree.command(name=COMMAND_SCHEDULE_REMOVE)
@app_commands.describe(day="The day of the week")
async def remove_user_schedule(interaction: discord.Interaction, day: DayOfWeek):
    """
    Remove the schedule for the active user who perform the command
    """
    guild_id = interaction.guild_id
    day_str = day.value
    list_users: Union[List[SimpleUserHour] | None] = await data_access_get_users_auto_schedule(guild_id, day_str)
    if list_users is None:
        list_users = []
    my_list = list(filter(lambda x: x.simple_user.user_id != interaction.user.id, list_users))
    data_access_set_users_auto_schedule(guild_id, day_str, my_list)
    await interaction.response.send_message(f"Remove for {DAYS_OF_WEEK[day_str]}", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_SEE)
async def see_user_own_schedule(interaction: discord.Interaction):
    """
    Show the current schedule for the user
    """
    response = ""
    guild_id = interaction.guild_id
    for day, day_display in enumerate(DAYS_OF_WEEK):
        list_users: Union[List[SimpleUserHour] | None] = await data_access_get_users_auto_schedule(guild_id, day)
        print_log(list_users)
        if list_users is not None:
            for user_hour in list_users:
                if user_hour.simple_user.user_id == interaction.user.id:
                    response += f"{day_display}: {user_hour.hour}\n"
    if response == "":
        response = f"No schedule found, uses the command /{COMMAND_SCHEDULE_ADD} to configure a recurrent schedule."

    await interaction.response.send_message(response, ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_REFRESH_FROM_REACTION)
@commands.has_permissions(administrator=True)
async def refresh_from_reaction(interaction: discord.Interaction):
    """
    An administrator can refresh the schedule from the reaction. Good to synchronize users' reaction when the bot was offline.
    """
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    # Fetch the last message from the channel
    channel = interaction.channel
    channel_id = channel.id
    last_message = await get_last_schedule_message(bot, channel)

    if last_message is None:
        await interaction.response.send_message("No messages found in this channel.", ephemeral=True)
        return

    message_id = last_message.id
    # Cache all users for this message's reactions to avoid redundant API calls

    message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
    if not message_votes:
        message_votes = get_empty_votes()

    message: discord.Message = await data_access_get_message(guild_id, channel_id, message_id)
    # Check if there are reactions
    if message.reactions:
        for reaction in message.reactions:
            # Get users who reacted
            users = [user async for user in reaction.users()]
            for user in users:
                # Check if the user is a bot
                if user.bot:
                    continue
                # Check if the user already reacted
                if any(user.id == u.user_id for u in message_votes[EMOJI_TO_TIME.get(str(reaction.emoji))]):
                    continue
                # Add the user to the message votes
                message_votes[EMOJI_TO_TIME.get(str(reaction.emoji))].append(
                    SimpleUser(
                        user.id,
                        user.display_name,
                        get_user_rank_emoji(guild_emoji.get(guild_id), user),
                    )
                )
        # Always update the cache
        data_access_set_reaction_message(guild_id, channel.id, message_id, message_votes)
        await update_vote_message(message, message_votes)
        await interaction.followup.send("Updated from the reaction", ephemeral=True)
    else:
        await interaction.followup.send("No reactions on the last message.", ephemeral=True)


@bot.tree.command(name=COMMAND_RESET_CACHE)
@commands.has_permissions(administrator=True)
async def reset_cache(interaction: discord.Interaction):
    """
    An administrator can reset the cache for the guild
    """
    # perms = interaction.channel.permissions_for(interaction.user)
    # print_log(f"User {interaction.author.id} has permissions {perms}")
    if interaction.user.id == interaction.guild.owner_id:
        guild_id = interaction.guild.id
        data_access_reset_guild_cache(guild_id)
        await interaction.response.send_message("Cached flushed", ephemeral=True)
    else:
        await interaction.response.send_message("Only the owner of the guild can reset the cache", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_ADD_USER)
@commands.has_permissions(administrator=True)
@app_commands.choices(time_voted=get_time_choices())
async def set_schedule_user_today(
    interaction: discord.Interaction,
    member: discord.Member,
    time_voted: app_commands.Choice[str],
):
    """
    An administrator can assign a user to a specific time for the current day
    """

    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    channel: discord.TextChannel = data_access_get_guild_text_channel_id(guild_id)
    channel_id = channel.id

    last_message = await get_last_schedule_message(bot, channel)
    if last_message is None:
        await interaction.followup.send("No messages found in this channel.", ephemeral=True)
        return
    message_id = last_message.id
    message: discord.Message = await data_access_get_message(guild_id, channel_id, message_id)
    message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
    if not message_votes:
        message_votes = get_empty_votes()

    simple_user = SimpleUser(
        member.id,
        member.display_name,
        get_user_rank_emoji(guild_emoji.get(guild_id), member),
    )
    message_votes[time_voted.value].append(simple_user)

    # Always update the cache
    data_access_set_reaction_message(guild_id, channel_id, message_id, message_votes)

    await update_vote_message(message, message_votes)
    await interaction.followup.send("User added", ephemeral=True)


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


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_SET_VOICE_CHANNEL)
@commands.has_permissions(administrator=True)
async def set_voice_channels(interaction: discord.Interaction, channel: discord.VoiceChannel):
    """
    Set the voice channels to listen to the users in the voice channel
    """
    guild_id = interaction.guild.id
    voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
    if voice_channel_ids is None:
        voice_channel_ids = []

    if channel.id not in voice_channel_ids:
        voice_channel_ids.append(channel.id)
    data_access_set_guild_voice_channel_ids(guild_id, voice_channel_ids)
    await interaction.response.send_message(f"The bot will check the voice channel #{channel.name}.", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_RESET_VOICE_SELECTION)
@commands.has_permissions(administrator=True)
async def reset_voice_channels(interaction: discord.Interaction):
    """
    Set the voice channels to listen to the users in the voice channel
    """
    guild_id = interaction.guild.id
    data_access_set_guild_voice_channel_ids(guild_id, None)

    await interaction.response.send_message("Deleted all configuration for voice channels", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_APPLY)
@commands.has_permissions(administrator=True)
async def apply_schedule(interaction: discord.Interaction):
    """
    Apply the schedule for user who scheduled using the /addschedule command
    Should not have to use it, but admin can trigger the sync
    """
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    channel_id = await data_access_get_guild_text_channel_id(guild_id)
    if channel_id is None:
        print_warning_log(f"No text channel in guild {interaction.guild.name}. Skipping.")
        await interaction.followup.send("Text channel not set.", ephemeral=True)
        return

    channel: discord.TextChannel = await data_access_get_channel(channel_id)
    last_message: discord.Message = await get_last_schedule_message(bot, channel)
    if last_message is None:
        print_warning_log(f"No message found in the channel {channel.name}. Skipping.")
        await interaction.followup.send(f"Cannot find a schedule message #{channel.name}.", ephemeral=True)

    await auto_assign_user_to_daily_question(guild_id, channel_id, last_message)

    await interaction.followup.send(f"Update message in #{channel.name}.", ephemeral=True)


@bot.tree.command(name=COMMAND_FORCE_SEND)
@commands.has_permissions(administrator=True)
async def force_send_daily(interaction: discord.Interaction):
    """Apply the schedule for user who scheduled using the /addschedule command"""
    await interaction.response.defer(ephemeral=True)
    await send_daily_question_to_a_guild(interaction.guild, True)
    await interaction.followup.send("Force sending", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_GET_VOICE_SELECTION)
@commands.has_permissions(administrator=True)
async def see_voice_channels(interaction: discord.Interaction):
    """Display the voice channels configured"""
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    voice_ids = await data_access_get_guild_voice_channel_ids(guild_id)
    if voice_ids is None:
        print_warning_log(f"No voice channel in guild {interaction.guild.name}. Skipping.")
        await interaction.followup.send("Voice channel not set.", ephemeral=True)
        return
    names = []
    for voice_id in voice_ids:
        names.append(voice_id)

    names_txt = ", ".join(map(lambda x: "<#" + str(x) + ">", voice_ids))
    await interaction.followup.send(f"The voice channels are: {names_txt} ", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_SET_SCHEDULE_CHANNEL)
@commands.has_permissions(administrator=True)
async def set_schedule_text_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    An administrator can set the channel where the daily schedule message will be sent
    """
    guild_id = interaction.guild.id
    data_access_set_guild_text_channel_id(guild_id, channel.id)

    await interaction.response.send_message(
        f"Confirmed to send a daily schedule message into #{channel.name}.",
        ephemeral=True,
    )
    await send_daily_question_to_a_guild(interaction.guild)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_GET_SCHEDULE_CHANNEL)
@commands.has_permissions(administrator=True)
async def see_schedule_text_channel(interaction: discord.Interaction):
    """Display the text channel configured"""
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    channel_id = await data_access_get_guild_text_channel_id(guild_id)
    if channel_id is None:
        print_warning_log(f"No schedule text channel in guild {interaction.guild.name}. Skipping.")
        await interaction.followup.send("Schedule text channel not set.", ephemeral=True)
        return

    await interaction.followup.send(f"The schedule text channel is <#{channel_id}>", ephemeral=True)


@tasks.loop(minutes=16)
async def check_voice_channel():
    """
    Run when the bot start and every X minutes to update the cache of the users in the voice channel and update the schedule
    """
    print_log("Checking voice channel to sync the schedule")
    for guild in bot.guilds:
        guild_id = guild.id
        text_channel_id = await data_access_get_guild_text_channel_id(guild_id)
        if text_channel_id is None:
            print_warning_log(f"Text channel not set for guild {guild.name}. Skipping.")
            continue
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_channel_ids is None:
            print_warning_log(f"Voice channel not set for guild {guild.name}. Skipping.")
            continue
        text_channel = await data_access_get_channel(text_channel_id)

        if text_channel is None:
            print_warning_log(f"Text channel configured but not found in the guild {guild.name}. Skipping.")
            continue
        last_message = await get_last_schedule_message(bot, text_channel)
        if last_message is None:
            print_warning_log(f"No message found in the channel {text_channel.name}. Skipping.")
            continue
        message_id = last_message.id
        message_votes = await data_access_get_reaction_message(guild_id, text_channel_id, message_id)
        if not message_votes:
            message_votes = get_empty_votes()
        found_new_user = False
        for voice_channel_id in voice_channel_ids:
            voice_channel = await data_access_get_channel(voice_channel_id)
            if voice_channel is None:
                print_warning_log(f"Voice channel configured but not found in the guild {guild.name}. Skipping.")
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
                    print_log(f"Current hour {current_hour_str} not supported. Skipping.")
                    continue
                if any(user.id == u.user_id for u in message_votes[current_hour_str]):
                    # User already voted for the current hour
                    print_log(f"User {user.id} already voted for {current_hour_str} in message {message_id}")
                    continue
                # Add the user to the message votes
                found_new_user = True
                message_votes[current_hour_str].append(
                    SimpleUser(
                        user.id,
                        user.display_name,
                        get_user_rank_emoji(guild_emoji[guild_id], user),
                    )
                )

        if found_new_user:
            print_log(f"Updating voice channel cache for {guild.name} and updating the message")
            # Always update the cache
            data_access_set_reaction_message(guild_id, text_channel_id, message_id, message_votes)
            await update_vote_message(last_message, message_votes)
            print_log(f"Updated voice channel cache for {guild.name}")
        else:
            print_log(f"No new user found in voice channel for {guild.name}")


@check_voice_channel.before_loop
async def before_check_voice_channel():
    """
    Ensure the bot is ready before starting the loop
    """
    await bot.wait_until_ready()


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """
    Check if the user is the only one in the voice channel
    """
    if member.bot:
        return  # Ignore bot

    for guild in bot.guilds:
        guild_id = guild.id
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        if voice_channel_ids is None:
            print_warning_log(f"Voice channel not set for guild {guild.name}. Skipping.")
            continue
        text_channel_id = await data_access_get_guild_text_channel_id(guild_id)
        if text_channel_id is None:
            print_warning_log(f"Text channel not set for guild {guild.name}. Skipping.")
            continue

        # Log user activity
        try:
            if before.channel is None and after.channel is not None:
                # User joined a voice channel
                channel_id = after.channel.id
                event = EVENT_CONNECT
                insert_user_activity(
                    member.id,
                    member.display_name,
                    channel_id,
                    guild_id,
                    event,
                    datetime.now(timezone.utc),
                )
            elif before.channel is not None and after.channel is None:
                # User left a voice channel
                channel_id = before.channel.id
                event = EVENT_DISCONNECT
                insert_user_activity(
                    member.id,
                    member.display_name,
                    channel_id,
                    guild_id,
                    event,
                    datetime.now(timezone.utc),
                )
            elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
                # User switched between voice channel
                insert_user_activity(
                    member.id,
                    member.display_name,
                    before.channel.id,
                    guild_id,
                    EVENT_DISCONNECT,
                    datetime.now(timezone.utc),
                )
                insert_user_activity(
                    member.id,
                    member.display_name,
                    after.channel.id,
                    guild_id,
                    EVENT_CONNECT,
                    datetime.now(timezone.utc),
                )
        except Exception as e:
            print_error_log(f"Error logging user activity: {e}")

        # Check if the user joined a voice channel to send a voice message
        if after.channel is not None and after.channel.id in voice_channel_ids:
            # Check if the user is the only one in the voice channel
            if len(after.channel.members) == 1:
                await send_notification_voice_channel(guild_id, member, after.channel, text_channel_id)


#         # Change the status of the voice channel
#         if after.channel is not None:
#             await update_voice_channel_status(member, after.channel, guild_id)


# async def update_voice_channel_status(member: discord.Member, voice_channel: discord.VoiceChannel, guild_id: int):
#     # Fetch the user from the database to retrieve the timezone
#     user_info = await fetch_user_info_by_user_id(member.id)
#     # Set the user timezone to the voice channel status


async def send_notification_voice_channel(
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

    list_simple_users = await get_users_scheduled_today_current_hour(guild_id, get_current_hour_eastern())
    list_simple_users = list(filter(lambda x: x.user_id != member.id, list_simple_users))
    if len(list_simple_users) > 0:
        other_members = ", ".join([f"{user.display_name}" for user in list_simple_users])
        text_message = f"Hello {member.display_name}! {other_members} are scheduled to play at this time. Check the bot schedule channel."
    else:
        # Check next hour
        list_simple_users = await get_users_scheduled_today_current_hour(guild_id, get_current_hour_eastern(1))
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


async def get_users_scheduled_today_current_hour(guild_id: int, current_hour_str: str) -> List[SimpleUser]:
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


@bot.tree.command(name=COMMAND_GUILD_ENABLE_BOT_VOICE)
@commands.has_permissions(administrator=True)
async def enable_voice_bot(interaction: discord.Interaction, enable: bool):
    """Activate or deactivate the bot voice message"""
    data_access_set_bot_voice_first_user(interaction.guild.id, enable)
    await interaction.response.send_message(f"The bot status to voice is {enable}", ephemeral=True)


@bot.tree.command(name=COMMAND_SHOW_COMMUNITY)
@commands.has_permissions(administrator=True)
async def community_show_image(interaction: discord.Interaction, from_day_ago: int = 90, to_day_ago: int = 0):
    """Activate or deactivate the bot voice message"""
    img_bytes = display_graph_cluster_people(False, from_day_ago, to_day_ago)
    bytesio = io.BytesIO(img_bytes)
    bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
    file = discord.File(fp=bytesio, filename="plot.png")
    await interaction.response.send_message(file=file, ephemeral=True)


@bot.tree.command(name=COMMAND_VERSION)
@commands.has_permissions(administrator=True)
async def show_version(interaction: discord.Interaction):
    """Show the version of the bot"""
    await interaction.response.defer(ephemeral=True)
    sha = get_sha()
    await interaction.followup.send(f"Version: {sha}", ephemeral=True)


@bot.tree.command(name=COMMAND_SET_USER_TIME_ZONE)
async def set_user_time_zone(interaction: discord.Interaction):
    """Command to set the user timezone"""
    await interaction.response.defer(ephemeral=True)
    # Create a view with the timezone options
    view = TimeZoneView(interaction.user.id)
    # Send a message with the buttons
    await interaction.followup.send("Please select a timezone:", view=view)


@commands.has_permissions(administrator=True)
@bot.tree.command(name=COMMAND_SET_USER_TIME_ZONE_OTHER_USER)
async def set_user_time_zone_for_other_user(interaction: discord.Interaction, member: discord.Member):
    """Command to set the user timezone"""
    await interaction.response.defer(ephemeral=True)
    # Create a view with the timezone options
    view = TimeZoneView(member.id)
    # Send a message with the buttons
    await interaction.followup.send("Please select a timezone:", view=view)


@bot.tree.command(name=COMMAND_GET_USER_TIME_ZONE)
async def get_user_time_zone(interaction: discord.Interaction, member: discord.Member):
    """Get the timezone of a single user"""
    await interaction.response.defer(ephemeral=True)
    user_info: UserInfo = await fetch_user_info_by_user_id(member.id)
    if user_info is None:
        await interaction.followup.send(f"User {member.display_name} has no timezone set.", ephemeral=True)
    else:
        await interaction.followup.send(
            f"User {member.display_name} has timezone {user_info.time_zone}", ephemeral=True
        )


@bot.tree.command(name=COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL)
async def get_users_time_zone_from_voice_channel(interaction: discord.Interaction, voice_channel: discord.VoiceChannel):
    """Get the timezone of all users in a voice channel"""
    await interaction.response.defer()
    users_id = [members.id for members in voice_channel.members]
    userid_member = {members.id: members for members in voice_channel.members}
    if len(users_id) == 0:
        await interaction.followup.send("No users in the voice channel.")
        return

    user_infos: Optional[UserInfo] = fetch_user_info_by_user_id_list(users_id)

    embed = discord.Embed(
        title=f"{voice_channel.name} Timezone",
        color=0x00FF00,
        timestamp=datetime.now(),
    )

    pacific = ""
    central = ""
    eastern = ""

    for user_info in user_infos:
        rank = get_user_rank_emoji(guild_emoji.get(interaction.guild.id), userid_member.get(user_info.id))
        member = userid_member.get(user_info.id)

        user_name = member.display_name if member is not None else user_info.display_name
        if user_info is not None:
            if user_info.time_zone == "US/Eastern":
                eastern += f"{rank} {user_name}\n"
            elif user_info.time_zone == "US/Central":
                central += f"{rank} {user_name}\n"
            elif user_info.time_zone == "US/Pacific":
                pacific += f"{rank} {user_name}\n"

    embed.add_field(name="Pacific", value="-" if pacific == "" else pacific, inline=True)
    embed.add_field(name="Central", value="-" if central == "" else central, inline=True)
    embed.add_field(name="Eastern", value="-" if eastern == "" else eastern, inline=True)

    if len(user_infos) == 0:
        await interaction.followup.send("Cannot find users timezone.")
        return
    most_common_tz = most_common([user_info.time_zone for user_info in user_infos])

    embed.set_footer(text=f"Most common timezone: {most_common_tz}")
    await interaction.followup.send(content="", embed=embed)


@bot.tree.command(name=COMMAND_ADJUST_RANK)
@app_commands.describe(ubisoft_connect_name="Your Ubisoft Connect name to fetch the max rank")
async def adjust_rank(interaction: discord.Interaction, ubisoft_connect_name: str):
    """COMMAND_SCHEDULE_ADD
    Set the role of the user depending of the maximum rank found in R6 Tracker
    """
    await interaction.response.defer(ephemeral=True)

    view = ConfirmCancelView()
    await interaction.followup.send(
        f"Are you sure you want to perform this action? If {ubisoft_connect_name} is not your real account you will face consequences.",
        view=view,
        ephemeral=True,
    )

    # Wait for the user to interact with the view
    await view.wait()

    # Check the result after user clicks a button
    if view.result is None:
        await interaction.followup.send("No response, action timed out.")
    elif view.result:

        guild_id = interaction.guild.id
        member: discord.Member = await data_access_get_member(guild_id, interaction.user.id)
        # member: discord.Member = interaction.guild.get_member(interaction.user.id)
        if member is None:
            print_error_log(f"adjust_rank: Cannot find a member from user id {interaction.user.id}.")
            await interaction.followup.send("Cannot find the member", ephemeral=True)
            return

        max_rank = await data_access_get_r6tracker_max_rank(ubisoft_connect_name)
        print_log(
            f"adjust_rank: R6 Tracker Downloaded Info for user {interaction.user.display_name} and found for user name {ubisoft_connect_name} the max role: {max_rank}"
        )
        try:
            await set_member_role_from_rank(interaction.guild, member, max_rank)
        except Exception as e:
            print_error_log(f"adjust_rank: Error setting the role: {e}")
            await interaction.followup.send(
                "Sorry, we cannot change your role for the moment. Please contact a moderator to manually change it.",
                ephemeral=True,
            )
            return

        text_channel_id = await data_access_get_guild_username_text_channel_id(guild_id)
        if text_channel_id is None:
            print_warning_log(f"adjust_rank: Text channel not set for guild {interaction.guild.name}. Skipping.")
            return

        # Retrieve the moderator role by name
        mod_role = discord.utils.get(interaction.guild.roles, name="Mod")

        if mod_role is None:
            print_warning_log(f"adjust_rank: Mod role not found in guild {interaction.guild.name}. Skipping.")

        channel = await data_access_get_channel(text_channel_id)
        await channel.send(
            content=f"{member.mention} main account is `{ubisoft_connect_name}` with max rank of `{max_rank}`.\n{mod_role.mention} please confirm the role change.",
        )

        await interaction.followup.send(f"Found max rank {max_rank}, role adjusted", ephemeral=True)
    # Add code to perform the actual action here
    else:
        await interaction.followup.send("Action was canceled.", ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_SET_USER_NAME_GAME_CHANNEL)
@commands.has_permissions(administrator=True)
async def set_username_text_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    An administrator can set the channel where the user name is shown
    """
    guild_id = interaction.guild.id
    data_access_set_guild_username_text_channel_id(guild_id, channel.id)

    await interaction.response.send_message(
        f"Confirmed to send a user name message into #{channel.name}.",
        ephemeral=True,
    )


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_GET_USER_NAME_GAME_CHANNEL)
@commands.has_permissions(administrator=True)
async def see_username_text_channel(interaction: discord.Interaction):
    """Display the text channel configured"""
    await interaction.response.defer(ephemeral=True)
    guild_id = interaction.guild.id
    channel_id = await data_access_get_guild_text_channel_id(guild_id)
    if channel_id is None:
        print_warning_log(f"No username text channel in guild {interaction.guild.name}. Skipping.")
        await interaction.followup.send("Username Text channel not set.", ephemeral=True)
        return

    await interaction.followup.send(f"The username text channel is <#{channel_id}>", ephemeral=True)


def main() -> None:
    """Start the bot"""
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
