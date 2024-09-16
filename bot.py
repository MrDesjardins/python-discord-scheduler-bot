import discord
from discord import app_commands
from discord.ui import Select, View
import os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List, Dict, Union
import asyncio
from datetime import datetime, timedelta, date, timezone
from deps.siege import getUserRankEmoji
from deps.cache import get_cache, set_cache, reset_cache_for_guid, ALWAYS_TTL, KEY_DAILY_MSG, KEY_REACTION_USERS, KEY_GUILD_USERS_AUTO_SCHEDULE, KEY_GUILD_TEXT_CHANNEL, KEY_MESSAGE, KEY_USER, KEY_GUILD, KEY_MEMBER, KEY_GUILD_VOICE_CHANNEL
from deps.models import SimpleUser, SimpleUserHour, DayOfWeek
from deps.values import supported_times_str, emoji_to_time, days_of_week, COMMAND_SCHEDULE_ADD, COMMAND_SCHEDULE_REMOVE, COMMAND_SCHEDULE_SEE, COMMAND_SCHEDULE_ADD_USER, COMMAND_SCHEDULE_CHANNEL_SELECTION, COMMAND_SCHEDULE_REFRESH_FROM_REACTION, COMMAND_RESET_CACHE, COMMAND_SCHEDULE_CHANNEL_VOICE_SELECTION
from deps.functions import get_current_hour_eastern, get_empty_votes, get_reactions, get_supported_time_time_label, get_time_choices, get_last_schedule_message, get_poll_message
from deps.log import print_log, print_error_log, print_warning_log
import pytz


load_dotenv()

ENV = os.getenv('ENV')
TOKEN = os.getenv('BOT_TOKEN_DEV') if ENV == 'dev' else os.getenv('BOT_TOKEN')
HOUR_SEND_DAILY_MESSAGE = 8

COMMAND_SCHEDULE_ADD = "addschedule"
COMMAND_SCHEDULE_REMOVE = "removeschedule"
COMMAND_SCHEDULE_SEE = "seeschedule"
COMMAND_SCHEDULE_APPLY = "applyschedule"
COMMAND_SCHEDULE_ADD_USER = "adduserschedule"
COMMAND_SCHEDULE_CHANNEL_SELECTION = "channel"
COMMAND_SCHEDULE_REFRESH_FROM_REACTION = "refreshschedule"
COMMAND_RESET_CACHE = "resetcache"
COMMAND_SCHEDULE_CHANNEL_VOICE_SELECTION = "voicechannel"

intents = discord.Intents.default()
intents.messages = True  # Enable the messages intent
intents.members = True  # Enable the messages intent
intents.reactions = True  # Enable the reactions intent
intents.message_content = True  # Enable the message content intent
intents.guild_reactions = True  # Enable the guild reactions intent
intents.voice_states = True  # Enable voice states to track who is in voice channel

bot = commands.Bot(command_prefix='/', intents=intents)

print_log(f"Env: {ENV}")
print_log(f"Token: {TOKEN}")

reactions = get_reactions()
supported_times_time_label = get_supported_time_time_label()

# Scheduler to send daily message
scheduler = AsyncIOScheduler()


async def reaction_worker():
    while True:
        reaction, remove = await bot.reaction_queue.get()
        try:
            await adjust_reaction(reaction, remove)
        except Exception as e:
            print_error_log(f"Error processing reaction: {e}")
        finally:
            bot.reaction_queue.task_done()


@bot.event
async def on_ready():
    print_log(f'{bot.user} has connected to Discord!')
    print_log(f'Bot latency: {bot.latency} seconds')
    for guild in bot.guilds:
        print_log(f"Checking in guild: {guild.name} ({guild.id})")
        print_log(
            f"\tGuild {guild.name} has {guild.member_count} members, setting the commands")
        guild_obj = discord.Object(id=guild.id)
        bot.tree.copy_global_to(guild=guild_obj)
        synced = await bot.tree.sync(guild=guild_obj)
        print_log(f"\tSynced {len(synced)} commands for guild {guild.name}.")
        channel_id = await get_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild.id}")
        if channel_id is None:
            print_log(
                f"\tThe administrator of the guild {guild.name} did not configure the channel to send the daily message.")
            continue

        channel = bot.get_channel(channel_id)

        if channel:
            permissions = check_bot_permissions(channel)
            print_log(
                f"\tBot permissions in channel {channel.name}: {permissions}")
        else:
            print_warning_log(
                f"\tChannel ID {channel_id} not found in guild {guild.name}")

        # Debug
        list_users: Union[List[SimpleUserHour] | None] = await get_cache(False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild.id}:{datetime.now().weekday()}")
        if list_users:
            for user_hours in list_users:
                print_log(
                    f"User {user_hours.simple_user.display_name} will play at {user_hours.hour}")

    # Start the reaction worker. The queue ensure that one reaction is handled at a time, sequentially
    # It avoids parallel processing of the same message, ensure the cache is filled by the previous reaction
    bot.reaction_queue = asyncio.Queue()
    bot.loop.create_task(reaction_worker())

    # Schedule the daily question to be sent every day
    pacific = pytz.timezone('America/Los_Angeles')
    scheduler.add_job(send_daily_question_to_all_guild, 'cron',
                      hour=HOUR_SEND_DAILY_MESSAGE, minute=0, timezone=pacific)
    scheduler.start()

    check_voice_channel.start()  # Start the background task

    # Run it for today (won't duplicate)
    await send_daily_question_to_all_guild()


async def send_daily_question_to_all_guild():
    """
    Send only once every day the question for each guild who has the bot
    """
    print_log("Sending daily schedule message")
    for guild in bot.guilds:
        await send_daily_question_to_a_guild(guild)


async def send_daily_question_to_a_guild(guild: discord.Guild):
    """
    Send the daily schedule question to a specific guild
    """
    now = datetime.now()
    current_date = now.strftime("%Y%m%d")
    day_of_week_number = now.weekday()  # 0 is Monday, 6 is Sunday
    channel_id = await get_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild.id}")
    if channel_id is None:
        print_error_log(
            f"\t⚠️ Channel id (configuration) not found for guild {guild.name}. Skipping.")
        return

    message_sent = await get_cache(False, f"{KEY_DAILY_MSG}:{guild.id}:{channel_id}:{current_date}")
    if message_sent is None:
        # channel: discord.TextChannel = bot.get_channel(channel_id)
        channel = await get_cache(
            True, f"Channel:{channel_id}", lambda: bot.fetch_channel(channel_id))
        message: discord.Message = await channel.send(get_poll_message())
        for reaction in reactions:
            await message.add_reaction(reaction)
        await auto_assign_user_to_daily_question(
            guild.id, message.id, channel_id, day_of_week_number)
        set_cache(
            False, f"{KEY_DAILY_MSG}:{guild.id}:{channel_id}:{current_date}", True, ALWAYS_TTL)
        print_log(f"\t✅ Daily message sent in guild {guild.name}")
    else:
        print_warning_log(
            f"\t⚠️ Daily message already sent in guild {guild.name}. Skipping.")


def check_bot_permissions(channel: discord.TextChannel) -> dict:
    bot_permissions = channel.permissions_for(channel.guild.me)

    permissions = {
        "read_messages": bot_permissions.read_messages,
        "send_messages": bot_permissions.send_messages,
        "manage_messages": bot_permissions.manage_messages,
        "add_reactions": bot_permissions.add_reactions,
    }

    return permissions


@bot.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    """ User adds a reaction to a message """
    await bot.reaction_queue.put((reaction, False))


@bot.event
async def on_raw_reaction_remove(reaction:  discord.RawReactionActionEvent):
    """ User removes a reaction to a message """
    await bot.reaction_queue.put((reaction, True))


async def adjust_reaction(reaction: discord.RawReactionActionEvent, remove: bool):
    """ Adjust the reaction with add or remove """
    print_log("Start Adjusting reaction")
    channel = await get_cache(
        True, f"Channel:{reaction.channel_id}", lambda: bot.fetch_channel(reaction.channel_id))
    message: discord.Message = await get_cache(True, f"{KEY_MESSAGE}:{reaction.guild_id}:{reaction.channel_id}:{reaction.message_id}",
                                               lambda: channel.fetch_message(reaction.message_id))
    user: discord.User = await get_cache(True, f"{KEY_USER}:{reaction.guild_id}:{reaction.channel_id}:{reaction.user_id}",
                                         lambda: bot.fetch_user(reaction.user_id))
    guild = await get_cache(True, f"{KEY_GUILD}:{reaction.guild_id}",
                            lambda: bot.get_guild(reaction.guild_id))
    member = await get_cache(True, f"{KEY_MEMBER}:{reaction.guild_id}:{reaction.channel_id}:{reaction.user_id}",
                             lambda: guild.fetch_member(user.id))

    if not channel or not message or not user or not guild or not member:
        print_log("End-Before Adjusting reaction")
        return

    if user.bot:
        return  # Ignore reactions from bots

    # Check if the message is older than 24 hours
    if message.created_at < datetime.now(timezone.utc) - timedelta(days=1):
        await user.send("You can't vote on a message that is older than 24 hours.")
        return

    reaction_emoji = reaction.emoji

    # Ensure no one is adding additional reactions
    emoji_from_list = emoji_to_time.get(str(reaction_emoji))
    if emoji_from_list is None:
        await message.remove_reaction(reaction_emoji, member)
        await user.send("You cannot add reaction beside the one provided.")
        return

    # Cache all users for this message's reactions to avoid redundant API calls
    reaction_users_cache_key = f"{KEY_REACTION_USERS}:{guild.id}:{channel.id}:{message.id}"
    message_votes = await get_cache(False, reaction_users_cache_key)
    # In the case there is no vote in the cache, we need to populate it with all the potential votes
    if not message_votes:
        message_votes = get_empty_votes()
        # Iterate over each reaction in the message only if it's not cached
        for react in message.reactions:
            time_voted = emoji_to_time.get(str(react.emoji))
            if time_voted:
                users = [u async for u in react.users() if not u.bot]
                for user in users:
                    message_votes[time_voted].append(
                        SimpleUser(user.id, member.display_name, getUserRankEmoji(member)))
        print_log(f"Setting reaction users for message {message.id} in cache")

    print_log(f"Updating for the current reaction {message.id}")
    time_voted = emoji_to_time.get(str(reaction_emoji))
    if remove:
        # Remove the user from the message votes
        for time_v, value in message_votes.items():
            print_log(f"Checking time {time_v}")
            print_log(value)
            if time_v == time_voted:
                for single_vote in value:
                    if user.id == single_vote.user_id:
                        print_log(
                            f"Found in {message.id} entry of the user for reaction {reaction_emoji}. Removing.")
                        message_votes[time_voted].remove(single_vote)
                        break
    else:
        # Add the user to the message votes
        time_voted = emoji_to_time.get(str(reaction_emoji))
        if time_voted:
            if any(user.id == u.user_id for u in message_votes[time_voted]):
                print_log(
                    f"User {user.id} already voted for {time_voted} in message {message.id}")
            else:
                message_votes[time_voted].append(
                    SimpleUser(user.id, member.display_name, getUserRankEmoji(member)))
                print_log(
                    f"Updating reaction users for message {message.id} in cache")
    # Always update the cache
    set_cache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)

    print_log("End Adjusting reaction")
    # await rate_limiter(update_vote_message, message, message_votes)
    await update_vote_message(message, message_votes)

# Function to update the vote message


async def update_vote_message(message: discord.Message, vote_for_message: Dict[str, List[SimpleUser]]):
    """ Update the votes per hour on the bot message"""
    vote_message = get_poll_message() + "\n\nSchedule for " + \
        date.today().strftime("%B %d, %Y") + "\n"
    for time, users in vote_for_message.items():
        if users:
            vote_message += f"{time}: {','.join([f'{user.rank_emoji}{user.display_name}' for user in users])}\n"
        else:
            vote_message += f"{time}: -\n"
    print_log(vote_message)
    await message.edit(content=vote_message)


class CombinedView(View):
    """
    A view that combines two selects for the user to answer two questions
    """

    def __init__(self):
        super().__init__()

        # First question select menu
        self.first_select = Select(
            placeholder="Days of the weeks:",
            options=[
                discord.SelectOption(
                    value="0", label=days_of_week[0]),
                discord.SelectOption(
                    value="1", label=days_of_week[1]),
                discord.SelectOption(
                    value="2", label=days_of_week[2]),
                discord.SelectOption(
                    value="3", label=days_of_week[3]),
                discord.SelectOption(
                    value="4", label=days_of_week[4]),
                discord.SelectOption(
                    value="5", label=days_of_week[5]),
                discord.SelectOption(
                    value="6", label=days_of_week[6]),
            ],
            custom_id="in_days",
            min_values=1, max_values=7
        )
        self.add_item(self.first_select)

        self.second_select = Select(
            placeholder="Time of the Day:",
            options=list(map(lambda x:
                             discord.SelectOption(
                                 value=x.value, label=x.label, description=x.description), supported_times_time_label)),
            custom_id="in_hours",
            min_values=1, max_values=12
        )
        self.add_item(self.second_select)
        # Track if both selects have been answered
        self.first_response = None
        self.second_response = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """ Callback function to check if the interaction is valid """
        # Capture the response for the fruit question
        if interaction.data["custom_id"] == "in_days":
            self.first_response = self.first_select.values
            await interaction.response.send_message("Days Saved", ephemeral=True)

        # Capture the response for the color question
        elif interaction.data["custom_id"] == "in_hours":
            self.second_response = self.second_select.values
            await interaction.response.send_message("Hours Saved", ephemeral=True)

        # If both responses are present, finalize the interaction
        if self.first_response and self.second_response:
            # Save user responses
            simple_user = SimpleUser(
                interaction.user.id, interaction.user.display_name, getUserRankEmoji(interaction.user))

            for day in self.first_response:
                list_users = []
                for hour in self.second_response:
                    list_users.append(SimpleUserHour(simple_user, hour))
                set_cache(
                    False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{interaction.guild_id}:{day}", list_users, ALWAYS_TTL)

            # Send final confirmation message with the saved data
            await interaction.followup.send(
                f"Your schedule has been saved. You can see your schedule with /{COMMAND_SCHEDULE_SEE} or remove it with /{COMMAND_SCHEDULE_REMOVE}",
                ephemeral=True
            )
            return True

        return False


@bot.tree.command(name=COMMAND_SCHEDULE_ADD)
async def add_user_schedule(interaction: discord.Interaction):
    """
    Add a schedule for the active user who perform the command
    """
    view = CombinedView()

    await interaction.response.send_message("Choose your day and hour. If you already have a schedule, this new one will override the previous schedule with the new hours for the day choosen.", view=view, ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_REMOVE)
@app_commands.describe(day="The day of the week")
async def remove_user_schedule(interaction: discord.Interaction, day: DayOfWeek):
    """
    Remove the schedule for the active user who perform the command
    """
    list_users: Union[List[SimpleUserHour] | None] = await get_cache(False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{interaction.guild_id}:{day.value}")
    if list_users is None:
        list_users = []
    my_list = list(filter(lambda x: x.simple_user.user_id !=
                   interaction.user.id, list_users))
    set_cache(
        False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{interaction.guild_id}:{day.value}", my_list, ALWAYS_TTL)
    await interaction.response.send_message(f"Remove for {repr(day)}")


@bot.tree.command(name=COMMAND_SCHEDULE_SEE)
async def see_user_own_schedule(interaction: discord.Interaction):
    """
    Show the current schedule for the user
    """
    response = ''
    for day, day_display in enumerate(days_of_week):
        list_users: Union[List[SimpleUserHour] | None] = await get_cache(False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{interaction.guild_id}:{day}")
        print_log(list_users)
        if list_users is not None:
            for user_hour in list_users:
                if user_hour.simple_user.user_id == interaction.user.id:
                    response += f"{day_display}: {user_hour.hour}\n"
    if response == '':
        response = f"No schedule found, uses the command /{COMMAND_SCHEDULE_ADD} to configure a recurrent schedule."

    await interaction.response.send_message(response)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_SELECTION)
@commands.has_permissions(administrator=True)
async def set_text_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    """
    An administrator can set the channel where the daily schedule message will be sent
    """
    guild_id = interaction.guild.id
    set_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}",
              channel.id, ALWAYS_TTL)
    await interaction.response.send_message(f"Confirmed to send a daily schedule message into #{channel.name}.")
    await send_daily_question_to_a_guild(interaction.guild)


@bot.tree.command(name=COMMAND_SCHEDULE_REFRESH_FROM_REACTION)
@commands.has_permissions(administrator=True)
async def refresh_from_reaction(interaction: discord.Interaction):
    """
    An administrator can refresh the schedule from the reaction. Good to synchronize users' reaction when the bot was offline.
    """
    guild_id = interaction.guild.id
    # Fetch the last message from the channel
    channel = interaction.channel
    last_message = await get_last_schedule_message(channel)

    if last_message is None:
        await interaction.response.send_message("No messages found in this channel.")
        return

    await interaction.response.defer()

    # Cache all users for this message's reactions to avoid redundant API calls
    reaction_users_cache_key = f"{KEY_REACTION_USERS}:{guild_id}:{channel.id}:{last_message.id}"
    message_votes = await get_cache(False, reaction_users_cache_key)
    if not message_votes:
        message_votes = get_empty_votes()

    message: discord.Message = await get_cache(True, f"{KEY_MESSAGE}:{guild_id}:{channel.id}:{last_message.id}",
                                               lambda: channel.fetch_message(last_message.id))
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
                if any(user.id == u.user_id for u in message_votes[emoji_to_time.get(str(reaction.emoji))]):
                    continue
                # Add the user to the message votes
                message_votes[emoji_to_time.get(str(reaction.emoji))].append(
                    SimpleUser(user.id, user.display_name, getUserRankEmoji(user)))
        # Always update the cache
        set_cache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)
        await update_vote_message(message, message_votes)
        await interaction.followup.send('Updated from the reaction')
    else:
        await interaction.followup.send("No reactions on the last message.")


@bot.tree.command(name=COMMAND_RESET_CACHE)
@commands.has_permissions(administrator=True)
async def reset_cache(interaction: discord.Interaction):
    """
    An administrator can reset the cache for the guild
    """
    guild_id = interaction.guild.id
    reset_cache_for_guid(guild_id)
    await interaction.response.send_message("Cached flushed")


@bot.tree.command(name=COMMAND_SCHEDULE_ADD_USER)
@commands.has_permissions(administrator=True)
@app_commands.choices(time_voted=get_time_choices())
async def set_schedule_user_today(interaction: discord.Interaction, member: discord.Member, time_voted: app_commands.Choice[str]):
    """
    An administrator can assign a user to a specific time for the current day
    """
    guild_id = interaction.guild.id
    channel_id = interaction.channel.id
    channel = await get_cache(
        True, f"Channel:{interaction.channel_id}", lambda: bot.fetch_channel(channel_id))

    last_message = await get_last_schedule_message(channel)
    if last_message is None:
        await interaction.response.send_message("No messages found in this channel.")
        return
    message_id = last_message.id
    message: discord.Message = await get_cache(True, f"{KEY_MESSAGE}:{interaction.guild_id}:{channel_id}:{message_id}",
                                               lambda: channel.fetch_message(message_id))
    reaction_users_cache_key = f"{KEY_REACTION_USERS}:{guild_id}:{channel_id}:{message_id}"
    message_votes = await get_cache(False, reaction_users_cache_key)
    if not message_votes:
        message_votes = get_empty_votes()

    simple_user = SimpleUser(
        member.id, member.display_name, getUserRankEmoji(member))
    message_votes[time_voted.value].append(simple_user)

    # Always update the cache
    set_cache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)

    await update_vote_message(message, message_votes)


async def auto_assign_user_to_daily_question(guild_id: int, channel_id: int, message_id: int, day_of_week_number: int):
    print_log(
        f"Auto assign user to daily question for guild {guild_id}, message_id {message_id}, day_of_week_number {day_of_week_number}")
    # Get the list of user and their hour for the specific day of the week
    list_users: Union[List[SimpleUserHour] | None] = await get_cache(False, f"{KEY_GUILD_USERS_AUTO_SCHEDULE}:{guild_id}:{day_of_week_number}")
    reaction_users_cache_key = f"{KEY_REACTION_USERS}:{guild_id}:{channel_id}:{message_id}"

    message_votes = get_empty_votes()  # Start with nothing for the day

    # Loop for the user+hours
    if list_users is not None:
        print_log(
            f"Found {len(list_users)} users for the day {day_of_week_number}")
        for userHour in list_users:
            # Assign for each hour the user
            message_votes[userHour.hour].append(userHour.simple_user)

        set_cache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)

        channel = await get_cache(
            True, f"Channel:{channel_id}", lambda: bot.fetch_channel(channel_id))

        last_message = await get_last_schedule_message(channel)
        await update_vote_message(last_message, message_votes)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_VOICE_SELECTION)
@commands.has_permissions(administrator=True)
async def set_voice_channel(interaction: discord.Interaction, channel: discord.VoiceChannel):
    """
    Set the voice channel to listen to the users in the voice channel
    """
    guild_id = interaction.guild.id
    set_cache(False, f"{KEY_GUILD_VOICE_CHANNEL}:{guild_id}",
              channel.id, ALWAYS_TTL)
    await interaction.response.send_message(f"Confirmed to list to #{channel.name}.")


@bot.tree.command(name=COMMAND_SCHEDULE_APPLY)
@commands.has_permissions(administrator=True)
async def apply_schedule(interaction: discord.Interaction):
    await interaction.response.defer()
    """
    Apply the schedule for user who scheduled using the /addschedule command
    Should not have to use it, but admin can trigger the sync
    """
    guild_id = interaction.guild.id
    channel_id = await get_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}")
    if channel_id is None:
        print_warning_log(
            f"No text channel in guild {interaction.guild.name}. Skipping.")
        await interaction.followup.send("Text channel not set.")
        return

    channel: discord.TextChannel = bot.get_channel(channel_id)
    last_message: discord.Message = await get_last_schedule_message(channel)
    if last_message is None:
        print_warning_log(
            f"No message found in the channel {channel.name}. Skipping.")
        await interaction.followup.send(f"Cannot find a schedule message #{channel.name}.")

    days_of_week = datetime.now().weekday()
    await auto_assign_user_to_daily_question(guild_id, channel_id, last_message.id, days_of_week)

    await interaction.followup.send(f"Update message in #{channel.name}.")


@tasks.loop(minutes=16)
async def check_voice_channel():
    """
    Run when the bot start and every X minutes to update the cache of the users in the voice channel and update the schedule
    """
    for guild in bot.guilds:
        guild_id = guild.id
        text_channel_id = await get_cache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}")
        if text_channel_id is None:
            print_warning_log(
                f"Text channel not set for guild {guild.name}. Skipping.")
            continue
        voice_channel_id = await get_cache(False, f"{KEY_GUILD_VOICE_CHANNEL}:{guild_id}")
        if voice_channel_id is None:
            print_warning_log(
                f"Voice channel not set for guild {guild.name}. Skipping.")
            continue
        text_channel = discord.utils.get(
            guild.text_channels, id=text_channel_id)
        if text_channel is None:
            print_warning_log(
                f"Text channel configured but not found in the guild {guild.name}. Skipping.")
            continue
        voice_channel = discord.utils.get(
            guild.voice_channels, id=voice_channel_id)
        if voice_channel is None:
            print_warning_log(
                f"Voice channel configured but not found in the guild {guild.name}. Skipping.")
            continue
        last_message = await get_last_schedule_message(text_channel)
        if last_message is None:
            print_warning_log(
                f"No message found in the channel {text_channel.name}. Skipping.")
            continue
        reaction_users_cache_key = f"{KEY_REACTION_USERS}:{guild_id}:{text_channel_id}:{last_message.id}"
        message_votes = await get_cache(False, reaction_users_cache_key)
        if not message_votes:
            message_votes = get_empty_votes()
        users_in_channel = voice_channel.members  # List of users in the voice channel
        for user in users_in_channel:
            # Check if the user is a bot
            if user.bot:
                continue
            # Check if the user already reacted
            current_hour_str = get_current_hour_eastern()
            if current_hour_str not in supported_times_str:
                # We support a limited amount of hours because of emoji constraints
                continue
            if any(user.id == u.user_id for u in message_votes[current_hour_str]):
                # User already voted for the current hour
                continue
            # Add the user to the message votes
            message_votes[current_hour_str].append(
                SimpleUser(user.id, user.display_name, getUserRankEmoji(user)))

            # Always update the cache
            set_cache(False, reaction_users_cache_key,
                      message_votes, ALWAYS_TTL)
        await update_vote_message(last_message, message_votes)
        print_log(f"Updated voice channel cache for {guild.name}")


@check_voice_channel.before_loop
async def before_check_voice_channel():
    """
    Ensure the bot is ready before starting the loop
    """
    await bot.wait_until_ready()


# @bot.event
# async def on_voice_state_update(member, before, after):
#     """
#     Check if the user is the only one in the voice channel
#     """
#     for guild in bot.guilds:
#         guild_id = guild.id
#         voice_channel_id = await getCache(False, f"{KEY_GUILD_VOICE_CHANNEL}:{guild_id}")
#         if voice_channel_id is None:
#             print_warning_log(
#                 f"Voice channel not set for guild {guild.name}. Skipping.")
#             continue
#         text_channel_id = await getCache(False, f"{KEY_GUILD_TEXT_CHANNEL}:{guild_id}")
#         if text_channel_id is None:
#             print_warning_log(
#                 f"Text channel not set for guild {guild.name}. Skipping.")
#             continue
#         # Check if the user joined a voice channel
#         if after.channel is not None and after.channel.id == voice_channel_id:
#             # Check if the user is the only one in the voice channel
#             if len(after.channel.members) == 1:
#                 await member.send(f"You're the only one in the voice channel: Feel free to message the Siege channel with \"@here lfg 4 rank\" to find other players and check the other players' schedule in <#{text_channel_id}>.")


bot.run(TOKEN)
