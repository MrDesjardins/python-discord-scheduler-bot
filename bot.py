import discord
from discord import app_commands
import os
from dotenv import load_dotenv
from discord.ext import commands, tasks
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord.ext.commands import Bot
import pytz
from typing import List, Dict
from types import MappingProxyType
from copy import deepcopy
import asyncio
from datetime import datetime, timedelta, date
import time
from enum import Enum
load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

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
print(f"Channel ID: {CHANNEL_ID}")


class DayOfWeek(Enum):
    monday = 1
    tuesday = 2
    wednesday = 3
    thursday = 4
    friday = 5
    saturday = 6
    sunday = 7


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

poll_message = f"What time will you play today ?\n⚠️Time in Eastern Time. If you are Pacific adds 3, Central adds 2.\nReact with all the time you plan to be available."
reactions = ['4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣',
             '9️⃣', '🔟', '🕚', '🕛', '1️⃣', '2️⃣', '3️⃣']

# Scheduler to send daily message
scheduler = AsyncIOScheduler()
cache = TTLCache(default_ttl=60)  # Cache with 60 seconds TTL
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


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord! Getting channel {CHANNEL_ID}')
    print(f'Bot latency: {bot.latency} seconds')
    for guild in bot.guilds:
        print(f"Checking in guild: {guild.name} ({guild.id})")
        channel = bot.get_channel(CHANNEL_ID)

        if channel:
            permissions = check_bot_permissions(channel)
            print(f"Bot permissions in channel {CHANNEL_ID}: {permissions}")
        else:
            print(f"Channel ID {CHANNEL_ID} not found in guild {guild.name}")

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
    # await send_daily_question()  # Test


# Function to send the poll message
async def send_daily_question():
    channel: discord.TextChannel = bot.get_channel(CHANNEL_ID)
    message: discord.Message = await channel.send(poll_message)
    for reaction in reactions:
        await message.add_reaction(reaction)


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


async def adjust_reaction(reaction: discord.RawReactionActionEvent, remove: bool):
    print("Start Adjusting reaction")
    channel = cache.get(f"Channel:{reaction.channel_id}")
    if not channel:
        channel = await bot.fetch_channel(reaction.channel_id)
        if channel:
            print(f"Channel {reaction.channel_id} found and setting in cache")
            cache.set(f"Channel:{reaction.channel_id}", channel, ttl=30*60)
        else:
            print(f"Channel {reaction.channel_id} not found by api")
    else:
        print(f"Channel {reaction.channel_id} found in cache")
    if not channel:
        print(f"Channel {reaction.channel_id} not found")
        return

    message = cache.get(f"Message:{reaction.message_id}")
    if not message:
        message = await channel.fetch_message(reaction.message_id)
        if message:
            print(f"Message {reaction.message_id} found and setting in cache")
            cache.set(f"Message:{reaction.message_id}", message,  ttl=10)
        else:
            print(f"Message {reaction.message_id} not found by api")
    else:
        print(f"Message {reaction.message_id} found in cache")

    user = cache.get(f"User:{reaction.user_id}")
    if not user:
        user = await bot.fetch_user(reaction.user_id)
        if user:
            print(f"User {reaction.user_id} found and setting in cache")
            cache.set(f"User:{reaction.user_id}", user, ttl=10*60)
        else:
            print(f"User {reaction.user_id} not found by api")
    else:
        print(f"User {reaction.user_id} found in cache")

    guild = cache.get(f"Guild:{reaction.guild_id}")
    if not guild:
        guild = bot.get_guild(reaction.guild_id)
        if guild:
            print(f"Guild {reaction.guild_id} found and setting in cache")
            cache.set(f"Guild:{reaction.guild_id}", user, ttl=10*60)
        else:
            print(f"Guild {reaction.guild_id} not found by api")
    else:
        print(f"Guild {reaction.guild_id} found in cache")

    member = cache.get(f"Member:{user.id}")
    if not member:
        member = await guild.fetch_member(user.id)
        if member:
            print(f"Member {user.id} found and setting in cache")
            cache.set(f"Member:{user.id}", user, ttl=10*60)
        else:
            print(f"Member {user.id} not found by api")
    else:
        print(f"Member {user.id} found in cache")

    if not channel or not message or not user or not guild or not member:
        print("End-Before Adjusting reaction")
        return

    if user.bot:
        return  # Ignore reactions from bots

    # Cache all users for this message's reactions to avoid redundant API calls
    reaction_users_cache_key = f"ReactionUsers:{message.id}"
    message_votes = cache.get(reaction_users_cache_key)
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
        cache.set(reaction_users_cache_key, message_votes, ttl=10*60)
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
                message_votes[time_voted].append(
                    SimpleUser(user.id, user.display_name, getUserRankEmoji(member)))
                print(
                    f"Updating reaction users for message {message.id} in cache")
        # Always update the cache
        cache.set(reaction_users_cache_key, message_votes, ttl=10*60)

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


@bot.tree.command(name="setautoschedule")
@app_commands.choices(hourday=[
    app_commands.Choice(name='1 am', value=1),
    app_commands.Choice(name='2 am', value=2),
    app_commands.Choice(name='3 am', value=3),
    app_commands.Choice(name='4 am', value=4),
    app_commands.Choice(name='5 am', value=5),
    app_commands.Choice(name='6 am', value=6),
    app_commands.Choice(name='7 am', value=7),
    app_commands.Choice(name='8 am', value=8),
    app_commands.Choice(name='9 am', value=9),
    app_commands.Choice(name='10 am', value=10),
    app_commands.Choice(name='11 am', value=11),
    app_commands.Choice(name='12 pm', value=12),
    app_commands.Choice(name='1 pm', value=13),
    app_commands.Choice(name='2 pm', value=14),
    app_commands.Choice(name='3 pm', value=15),
    app_commands.Choice(name='4 pm', value=16),
    app_commands.Choice(name='5 pm', value=17),
    app_commands.Choice(name='6 pm', value=18),
    app_commands.Choice(name='7 pm', value=19),
    app_commands.Choice(name='8 pm', value=20),
    app_commands.Choice(name='9 pm', value=21),
    app_commands.Choice(name='10 pm', value=22),
    app_commands.Choice(name='11 pm', value=23),
    app_commands.Choice(name='12 am', value=24)
])
@app_commands.describe(day="The day of the week")
@app_commands.describe(hourday="The time of the day")
async def setSchedule(interaction: discord.Interaction, day: DayOfWeek, hourday: app_commands.Choice[int]):
    await interaction.response.send_message(f"Set for {hourday.name} and {repr(day)}")


@bot.tree.command(name="removeautoschedule")
@app_commands.describe(day="The day of the week")
async def removeSchedule(interaction: discord.Interaction, day: DayOfWeek):
    await interaction.response.send_message(f"Remove for {repr(day)}")


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


bot.run(TOKEN)
