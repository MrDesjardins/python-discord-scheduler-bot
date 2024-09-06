import discord
from discord import app_commands
from discord.ui import Select, View
import os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext.commands import Bot
import pytz
from typing import List, Dict, Callable, Awaitable, Union, Optional
from types import MappingProxyType
from copy import deepcopy
import asyncio
from datetime import datetime, timedelta, date, timezone
import time
from enum import Enum
import atexit
import dill as pickle
import inspect
load_dotenv()
ALWAYS_TTL = 60*60*24*365*10
TOKEN = os.getenv('BOT_TOKEN')
CACHE_FILE = "cache.txt"

EMOJI_CHAMPION = "<:Champion:1279550703311917208>"
EMOJI_DIAMOND = "<:Diamond:1279550706373623883> "
EMOJI_EMERALD = "<:Emerald:1279550712233197619> "
EMOJI_PLATINUM = "<:Platinum:1279550709616087052>"
EMOJI_GOLD = "<:Gold:1279550707971915776> "
EMOJI_SILVER = "<:Silver:1279550710941483038"
EMOJI_BRONZE = "<:Bronze:1279550704427597826> "
EMOJI_COPPER = "<:Copper:1279550705551802399> "

intents = discord.Intents.default()
intents.messages = True  # Enable the messages intent
# intents.members = True  # Enable the messages intent
intents.reactions = True  # Enable the reactions intent
intents.message_content = True  # Enable the message content intent
intents.guild_reactions = True  # Enable the guild reactions intent

bot = commands.Bot(command_prefix='/', intents=intents)

print(f"Token: {TOKEN}")


def save_to_file(obj, filename):
    with open(filename, 'wb') as file:
        pickle.dump(obj, file)


def load_from_file(filename):
    try:
        with open(filename, 'rb') as file:
            return pickle.load(file)
    except FileNotFoundError:
        return None


class DayOfWeek(Enum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


days_of_week = ['Monday', 'Tuesday', 'Wednesday',
                'Thursday', 'Friday', 'Saturday', 'Sunday']


class CacheItem:
    def __init__(self, value, ttl):
        self.value = value
        self.expiry = time.time() + ttl


class TTLCache:
    def __init__(self, default_ttl=60):
        self.cache = {}
        self.default_ttl = default_ttl
        self.lock = asyncio.Lock()

    def _is_expired(self, key):
        item = self.cache.get(key, None)
        if not item:
            return True
        if time.time() > item.expiry:
            del self.cache[key]
            return True
        return False

    def set(self, key, value, ttl=None):
        if ttl is None:
            ttl = self.default_ttl
        self.cache[key] = CacheItem(value, ttl)

    def get(self, key):
        if self._is_expired(key):
            return None
        return self.cache.get(key).value

    def delete(self, key):
        if key in self.cache:
            del self.cache[key]

    def clear(self):
        self.cache.clear()

    async def _cleanup(self):
        while True:
            expired_keys = []
            for key in list(self.cache.keys()):
                if self._is_expired(key):
                    expired_keys.append(key)
            for key in expired_keys:
                del self.cache[key]
            await asyncio.sleep(1)  # Adjust the sleep time as needed

    def start_cleanup(self):
        asyncio.create_task(self._cleanup())

    def initialize(self, values):
        if values:
            self.cache = values


class RateLimiter:
    def __init__(self, interval_seconds):
        self.interval_seconds = interval_seconds
        self.last_called = datetime.min
        self.lock = asyncio.Lock()

    async def _call_function(self, func, *args, **kwargs):
        async with self.lock:
            now = datetime.now()
            if now - self.last_called < timedelta(seconds=self.interval_seconds):
                print(f'Skipping function {func.__name__} at {now}')
                return  # Skip execution if within the interval
            self.last_called = now
            # Ensure func is awaited correctly
            print(f'Calling function {func.__name__} at {now}')
            # if asyncio.iscoroutinefunction(func):
            await func(*args, **kwargs)
            # else:
            #     func(*args, **kwargs)

    async def __call__(self, func, *args, **kwargs):
        await self._call_function(func, *args, **kwargs)


class SimpleUser:
    def __init__(self, user_id, display_name, rank_emoji):
        self.user_id = user_id
        self.display_name = display_name
        self.rank_emoji = rank_emoji

    def __str__(self):
        return f"User ID: {self.user_id}, Display Name: {self.display_name}"


class SimpleUserHour:
    def __init__(self, user: SimpleUser, hour):
        self.simpleUser = user
        self.hour = hour


# This dictionary will store votes to an array of user
def get_empty_votes():
    return {
        '4pm': [],
        '5pm': [],
        '6pm': [],
        '7pm': [],
        '8pm': [],
        '9pm': [],
        '10pm': [],
        '11pm': [],
        '12pm': [],
        '1am': [],
        '2am': [],
        '3am': [],
    }


emoji_to_time = {
    '4️⃣': '4pm',
    '5️⃣': '5pm',
    '6️⃣': '6pm',
    '7️⃣': '7pm',
    '8️⃣': '8pm',
    '9️⃣': '9pm',
    '🔟': '10pm',
    '🕚': '11pm',
    '🕛': '12pm',
    '1️⃣': '1am',
    '2️⃣': '2am',
    '3️⃣': '3am'
}

poll_message = f"What time will you play today ?\n⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nReact with all the time you plan to be available. You can use /setautoschedule to set recurrent day and hours."
reactions = ['4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣',
             '9️⃣', '🔟', '🕚', '🕛', '1️⃣', '2️⃣', '3️⃣']

# Scheduler to send daily message
scheduler = AsyncIOScheduler()
memoryCache = TTLCache(default_ttl=60)  # Cache with 60 seconds TTL
dataCache = TTLCache(default_ttl=60)  # Cache with 60 seconds TTL

# previous_cache_content = load_from_file(CACHE_FILE)
# if previous_cache_content is None:
#     print("No cache data found")
# else:
#     cache.cache = previous_cache_content
#     print("Cache loaded from file")


rate_limiter = RateLimiter(interval_seconds=2)


async def reaction_worker():
    while True:
        reaction, remove = await bot.reaction_queue.get()
        try:
            await adjust_reaction(reaction, remove)
        except Exception as e:
            print(f"Error processing reaction: {e}")
        finally:
            bot.reaction_queue.task_done()

dataCache.initialize(load_from_file(CACHE_FILE))


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot latency: {bot.latency} seconds')
    for guild in bot.guilds:
        print(f"Checking in guild: {guild.name} ({guild.id})")
        print(
            f"\tGuild {guild.name} has {guild.approximate_member_count} members, setting the commands")
        guildObj = discord.Object(id=guild.id)
        bot.tree.copy_global_to(guild=guildObj)
        await bot.tree.sync(guild=guildObj)
        print("\tChecking if the guild has a channel set")
        channelId = await getCache(False, f"Guild_Channel:{guild.id}")
        if channelId is None:
            print(f"\tChannel ID not found for guild {guild.name}")
            continue

        channel = bot.get_channel(channelId)

        if channel:
            permissions = check_bot_permissions(channel)
            print(
                f"\tBot permissions in channel {channel.name}: {permissions}")
        else:
            print(f"\tChannel ID {channelId} not found in guild {guild.name}")

        # DEbug
        list_users: Union[List[SimpleUserHour] | None] = await getCache(False, f"GuildUserAutoDay:{guild.id}:0")
        if list_users:
            for userHour in list_users:
                print(
                    f"User {userHour.simpleUser.user_id} will play at {userHour.hour}")

    # Waiting the commands
    print("Waiting for commands to load")
    synced = await bot.tree.sync()

    print(f"Synced {len(synced)} commands.")

    # Start the reaction worker
    bot.reaction_queue = asyncio.Queue()
    bot.loop.create_task(reaction_worker())
    # Schedule the daily question to be sent every day
    # pacific = pytz.timezone('America/Los_Angeles')
    # scheduler.add_job(send_daily_question, 'cron', hour=15, minute=0, timezone=pacific)
    # scheduler.start()
    await send_daily_question()  # Test


async def send_daily_question():
    """
    Send only once every day the question for each guild who has the bot
    """
    now = datetime.now()
    current_date = now.strftime("%Y%m%d")
    day_of_week_number = now.weekday()  # 0 is Monday, 6 is Sunday
    for guild in bot.guilds:
        channelId = await getCache(False, f"Guild_Channel:{guild.id}")
        if channelId is None:
            print(f"Channel ID not found for guild {guild.name}")
            continue

        message_sent = await getCache(False, f"DailyMessageSentInChannel:{channelId}:{current_date}")
        if message_sent is None:
            channel: discord.TextChannel = bot.get_channel(channelId)
            message: discord.Message = await channel.send(poll_message)
            for reaction in reactions:
                await message.add_reaction(reaction)
            auto_assign_user_to_daily_question(
                guild.id, message.id, day_of_week_number)
            setCache(
                False, f"DailyMessageSentInChannel:{channelId}:{current_date}", True, ALWAYS_TTL)
        else:
            print(f"Daily message already sent in guild {guild.name}")


def check_bot_permissions(channel: discord.TextChannel) -> dict:
    bot_permissions = channel.permissions_for(channel.guild.me)

    permissions = {
        "read_messages": bot_permissions.read_messages,
        "send_messages": bot_permissions.send_messages,
        "manage_messages": bot_permissions.manage_messages,
        "add_reactions": bot_permissions.add_reactions,
    }

    return permissions

# Handle reactions


@bot.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    await bot.reaction_queue.put((reaction, False))

# Handle removing reactions


@bot.event
async def on_raw_reaction_remove(reaction:  discord.RawReactionActionEvent):
    await bot.reaction_queue.put((reaction, True))


async def getCache(inMemory: bool, key: str, fetch_function: Optional[Union[Callable[[], Awaitable], Callable[[], str]]] = None):
    if inMemory:
        cache = memoryCache
    else:
        cache = dataCache
    value = cache.get(key)
    if not value:
        if fetch_function:
            # Check if the fetch function is asynchronous
            result = fetch_function()
            if inspect.isawaitable(result):
                value = await result
            else:
                value = result
            if value:
                cache.set(key, value)
            else:
                print(f"Value {key} not found by api")
    else:
        print(f"Value {key} found in cache")
    return value


def setCache(inMemory: bool, key: str, value: any, cache_seconds: Optional[int] = None):
    if inMemory:
        memoryCache.set(key, value, cache_seconds)
    else:
        dataCache.set(key, value, cache_seconds)
        save_to_file(dataCache.cache, CACHE_FILE)


async def adjust_reaction(reaction: discord.RawReactionActionEvent, remove: bool):
    print("Start Adjusting reaction")
    channel = await getCache(
        True, f"Channel:{reaction.channel_id}", lambda: bot.fetch_channel(reaction.channel_id))
    message: discord.Message = await getCache(True, f"Message:{reaction.message_id}",
                                              lambda: channel.fetch_message(reaction.message_id))
    user: discord.User = await getCache(True, f"User:{reaction.user_id}",
                                        lambda: bot.fetch_user(reaction.user_id))
    guild = await getCache(True, f"Guild:{reaction.guild_id}",
                           lambda: bot.get_guild(reaction.guild_id))
    member = await getCache(True, f"Member:{reaction.guild_id}",
                            lambda: guild.fetch_member(user.id))

    if not channel or not message or not user or not guild or not member:
        print("End-Before Adjusting reaction")
        return

    if user.bot:
        return  # Ignore reactions from bots

    # Check if the message is older than 24 hours
    # if message.created_at < datetime.now(timezone.utc) - timedelta(days=1):
    if not is_today(message.created_at):
        await user.send("You can't vote on a message that is older than 24 hours.")

    # Cache all users for this message's reactions to avoid redundant API calls
    reaction_users_cache_key = f"ReactionUsers:{message.id}"
    message_votes = await getCache(False, reaction_users_cache_key)
    if not message_votes:
        message_votes = get_empty_votes()
        # Iterate over each reaction in the message only if it's not cached
        for react in message.reactions:
            time_voted = emoji_to_time.get(str(react.emoji))
            if time_voted:
                users = [u async for u in react.users() if not u.bot]
                for user in users:
                    message_votes[time_voted].append(
                        SimpleUser(user.id, user.display_name, getUserRankEmoji(member)))
        print(f"Setting reaction users for message {message.id} in cache")
        setCache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)
    else:
        print(f"Using cached reaction users for message {message.id}")
        time_voted = emoji_to_time.get(str(reaction.emoji))
        if remove:
            # Remove the user from the message votes
            for time_v, value in message_votes.items():
                print(f"Checking time {time_v}")
                print(value)
                if time_v == time_voted:
                    for single_vote in value:
                        if user.id == single_vote.user_id:
                            print(
                                f"Found in {message.id} entry of the user for reaction {reaction.emoji}. Removing.")
                            message_votes[time_voted].remove(single_vote)
                            break
        else:
            # Add the user to the message votes
            time_voted = emoji_to_time.get(str(reaction.emoji))
            if time_voted:
                if any(user.id == u.user_id for u in message_votes[time_voted]):
                    print(
                        f"User {user.id} already voted for {time_voted} in message {message.id}")
                else:
                    message_votes[time_voted].append(
                        SimpleUser(user.id, user.display_name, getUserRankEmoji(member)))
                    print(
                        f"Updating reaction users for message {message.id} in cache")
        # Always update the cache
        setCache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)

    print("End Adjusting reaction")
    # await rate_limiter(update_vote_message, message, message_votes)
    await update_vote_message(message, message_votes)

# Function to update the vote message


async def update_vote_message(message: discord.Message, vote_for_message: Dict[str, List[SimpleUser]]):
    # channel: discord.TextChannel = bot.get_channel(1279593593639665707)
    # message: discord.Message = await channel.fetch_message(message.id)

    vote_message = poll_message + "\n\nSchedule for " + \
        date.today().strftime("%B %d, %Y") + "\n"
    for time, users in vote_for_message.items():
        if users:
            vote_message += f"{time}: {','.join([f'{user.rank_emoji}{user.display_name}' for user in users])}\n"
        else:
            vote_message += f"{time}: -\n"
    print(vote_message)
    await message.edit(content=vote_message)


class CombinedView(View):
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
            options=[
                discord.SelectOption(
                    value="4", label="4 pm", description="4 am Eastern Time"),
                discord.SelectOption(
                    value="5", label="5 pm", description="5 am Eastern Time"),
                discord.SelectOption(
                    value="6", label="6 pm", description="6 am Eastern Time"),
                discord.SelectOption(
                    value="7", label="7 pm", description="7 am Eastern Time"),
                discord.SelectOption(
                    value="8", label="8 pm", description="8 am Eastern Time"),
                discord.SelectOption(
                    value="9", label="9 pm", description="9 am Eastern Time"),
                discord.SelectOption(
                    value="10", label="10 pm", description="10 am Eastern Time"),
                discord.SelectOption(
                    value="11", label="11 pm", description="11 am Eastern Time"),
                discord.SelectOption(
                    value="12", label="12 am", description="12 am Eastern Time"),
                discord.SelectOption(
                    value="1", label="1 am", description="1 am Eastern Time"),
                discord.SelectOption(
                    value="2", label="2 am", description="2 am Eastern Time"),
                discord.SelectOption(
                    value="3", label="3 am", description="3 am Eastern Time")
            ],
            custom_id="in_hours",
            min_values=1, max_values=12
        )
        self.add_item(self.second_select)
        # Track if both selects have been answered
        self.first_response = None
        self.second_response = None

    # This function handles the callback when any select is interacted with
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Capture the response for the fruit question
        if interaction.data["custom_id"] == "in_days":
            self.first_response = self.first_select.values
            await interaction.response.send_message(f"Days Saved", ephemeral=True)

        # Capture the response for the color question
        elif interaction.data["custom_id"] == "in_hours":
            self.second_response = self.second_select.values
            await interaction.response.send_message(f"Hours Saved", ephemeral=True)

        # If both responses are present, finalize the interaction
        if self.first_response and self.second_response:
            # Save user responses
            simpleUser = SimpleUser(
                interaction.user.id, interaction.user.display_name, getUserRankEmoji(interaction.user))

            for day in self.first_response:
                list_users = []
                for hour in self.second_response:
                    list_users.append(SimpleUserHour(simpleUser, hour))
                setCache(
                    False, f"GuildUserAutoDay:{interaction.guild_id}:{day}", list_users, ALWAYS_TTL)

            # Send final confirmation message with the saved data
            await interaction.followup.send(
                f"Your schedule has been saved.",
                ephemeral=True
            )
            return True

        return False


@bot.tree.command(name="setautoschedule")
async def setSchedule(interaction: discord.Interaction):
    view = CombinedView()

    await interaction.response.send_message(f"Choose your day and hour", view=view, ephemeral=True)


@bot.tree.command(name="removeautoschedule")
@app_commands.describe(day="The day of the week")
async def removeSchedule(interaction: discord.Interaction, day: DayOfWeek):
    list_users: Union[List[SimpleUserHour] | None] = await getCache(False, f"GuildUserAutoDay:{interaction.guild_id}:{day.value}")
    if list_users is None:
        list_users = []
    my_list = list(filter(lambda x: x.simpleUser.id !=
                   interaction.user.id, list_users))
    setCache(
        False, f"GuildUserAutoDay:{interaction.guild_id}:{day.value}", my_list, ALWAYS_TTL)
    await interaction.response.send_message(f"Remove for {repr(day)}")


@bot.tree.command(name="setschedulerchannel")
@commands.has_permissions(administrator=True)
async def setDailyChannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    setCache(False, f"Guild_Channel:{guild_id}", channel.id, ALWAYS_TTL)
    await interaction.response.send_message(f"Confirmed to send a daily message into #{channel.name}.")


def getUserRankEmoji(user: discord.Member) -> str:
    # Check the user's roles to determine their rank
    for role in user.roles:
        print(f"Checking role {role.name}")
        if role.name == "Champion":
            return EMOJI_CHAMPION
        elif role.name == "Diamond":
            return EMOJI_DIAMOND
        elif role.name == "Emerald":
            return EMOJI_EMERALD
        elif role.name == "Platinum":
            return EMOJI_PLATINUM
        elif role.name == "Gold":
            return EMOJI_GOLD
        elif role.name == "Silver":
            return EMOJI_SILVER
        elif role.name == "Bronze":
            return EMOJI_BRONZE
        elif role.name == "Copper":
            return EMOJI_COPPER
    print("No rank found")
    return EMOJI_COPPER


async def auto_assign_user_to_daily_question(guild_id: int, message_id: int, day_of_week_number: int):
    # Get the list of user and their hour for the specific day of the week
    list_users: Union[List[SimpleUserHour] | None] = await getCache(False, f"GuildUserAutoDay:{guild_id}:{day_of_week_number}")
    reaction_users_cache_key = f"ReactionUsers:{message_id}"

    message_votes = get_empty_votes()  # Start with nothing for the day

    # Loop for the user+hours
    for userHour in list_users:
        # Assign for each hour the user
        message_votes[userHour.hour].append(userHour.simpleUser)

    setCache(False, reaction_users_cache_key, message_votes, ALWAYS_TTL)


def is_today(date_time):
    # Get today's date
    today_utc = datetime.now(timezone.utc).date()
    date_time_utc = date_time.date()

    return date_time_utc == today_utc


bot.run(TOKEN)


def on_exit():
    print("Script is exiting, saving the object...")
    save_to_file(dataCache.cache, CACHE_FILE)


# Register the on_exit function to be called when the script exits
atexit.register(on_exit)
