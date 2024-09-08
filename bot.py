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
from deps.cache import getCache, setCache, ALWAYS_TTL
from deps.models import SimpleUser, SimpleUserHour, get_empty_votes, emoji_to_time, days_of_week, DayOfWeek, supported_times
import pytz
from deps.ratelimiter import RateLimiter
load_dotenv()

ENV = os.getenv('ENV')
TOKEN = os.getenv('BOT_TOKEN_DEV') if ENV == 'dev' else os.getenv('BOT_TOKEN')

COMMAND_SCHEDULE_SET = "addschedule"
COMMAND_SCHEDULE_REMOVE = "removeschedule"
COMMAND_SCHEDULE_SEE = "seeschedule"
COMMAND_SCHEDULE_CHANNEL_SELECTION = "channel"

intents = discord.Intents.default()
intents.messages = True  # Enable the messages intent
intents.members = True  # Enable the messages intent
intents.reactions = True  # Enable the reactions intent
intents.message_content = True  # Enable the message content intent
intents.guild_reactions = True  # Enable the guild reactions intent

bot = commands.Bot(command_prefix='/', intents=intents)

print(f"Token: {TOKEN}")


poll_message = f"What time will you play today ?\n⚠️Time in Eastern Time (Pacific adds 3, Central adds 1).\nReact with all the time you plan to be available. You can use /{COMMAND_SCHEDULE_SET} to set recurrent day and hours."
reactions = ['4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣',
             '9️⃣', '🔟', '🕚', '🕛', '1️⃣', '2️⃣', '3️⃣']

# Scheduler to send daily message
scheduler = AsyncIOScheduler()
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
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot latency: {bot.latency} seconds')
    for guild in bot.guilds:
        print(f"Checking in guild: {guild.name} ({guild.id})")
        print(
            f"\tGuild {guild.name} has {guild.member_count} members, setting the commands")
        guildObj = discord.Object(id=guild.id)
        bot.tree.copy_global_to(guild=guildObj)
        synced = await bot.tree.sync(guild=guildObj)
        print(f"Synced {len(synced)} commands for guild {guild.name}.")
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

        # Debug
        list_users: Union[List[SimpleUserHour] | None] = await getCache(False, f"GuildUserAutoDay:{guild.id}:{datetime.now().weekday()}")
        if list_users:
            for userHour in list_users:
                print(
                    f"User {userHour.simpleUser.display_name} will play at {userHour.hour}")

    # Waiting the commands
    # print("Waiting for commands to load")
    # synced = await bot.tree.sync()
    # print(f"Synced {len(synced)} commands.")

    # Start the reaction worker
    bot.reaction_queue = asyncio.Queue()
    bot.loop.create_task(reaction_worker())
    # Schedule the daily question to be sent every day
    pacific = pytz.timezone('America/Los_Angeles')
    scheduler.add_job(send_daily_question, 'cron',
                      hour=10, minute=0, timezone=pacific)
    scheduler.start()
    # Run it for today (won't duplicate)
    await send_daily_question()


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
            await auto_assign_user_to_daily_question(
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


@bot.event
async def on_raw_reaction_add(reaction: discord.RawReactionActionEvent):
    await bot.reaction_queue.put((reaction, False))


@bot.event
async def on_raw_reaction_remove(reaction:  discord.RawReactionActionEvent):
    await bot.reaction_queue.put((reaction, True))


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
    if message.created_at < datetime.now(timezone.utc) - timedelta(days=1):
        await user.send("You can't vote on a message that is older than 24 hours.")
        return

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
            options=list(map(lambda x:
                             discord.SelectOption(
                                 value=x.value, label=x.label, description=x.description), supported_times)),
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
                f"Your schedule has been saved. You can see your schedule with /{COMMAND_SCHEDULE_SEE} or remove it with /{COMMAND_SCHEDULE_REMOVE}",
                ephemeral=True
            )
            return True

        return False


@bot.tree.command(name=COMMAND_SCHEDULE_SET)
async def setSchedule(interaction: discord.Interaction):
    view = CombinedView()

    await interaction.response.send_message(f"Choose your day and hour. If you already have a schedule, this new one will override your previous one.", view=view, ephemeral=True)


@bot.tree.command(name=COMMAND_SCHEDULE_REMOVE)
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


@bot.tree.command(name=COMMAND_SCHEDULE_SEE)
async def seeSchedule(interaction: discord.Interaction):
    response = ''
    for day in range(len(days_of_week)):
        list_users: Union[List[SimpleUserHour] | None] = await getCache(False, f"GuildUserAutoDay:{interaction.guild_id}:{day}")
        print(list_users)
        if list_users is not None:
            for userHour in list_users:
                if userHour.simpleUser.user_id == interaction.user.id:
                    response += f"{days_of_week[day]}: {userHour.hour}\n"
    if response == '':
        response = "No schedule found"

    await interaction.response.send_message(response)


@bot.tree.command(name=COMMAND_SCHEDULE_CHANNEL_SELECTION)
@commands.has_permissions(administrator=True)
async def setDailyChannel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = interaction.guild.id
    setCache(False, f"Guild_Channel:{guild_id}", channel.id, ALWAYS_TTL)
    await interaction.response.send_message(f"Confirmed to send a daily message into #{channel.name}.")


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


bot.run(TOKEN)
