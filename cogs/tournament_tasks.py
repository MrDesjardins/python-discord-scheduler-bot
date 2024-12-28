from datetime import datetime, time
from discord.ext import commands, tasks
import pytz
from deps.mybot import MyBot
from deps.log import print_log
from deps.tournament_discord_actions import (
    send_tournament_registration_to_a_guild,
    send_tournament_starting_to_a_guild,
)

local_tz = pytz.timezone("America/Los_Angeles")
time_send_daily_registration_tournament = time(hour=9, minute=0, second=0, tzinfo=local_tz)
time_send_daily_starting_tournament = time(hour=9, minute=10, second=0, tzinfo=local_tz)


class TournamentTasksCog(commands.Cog):
    """Tasks for the tournament bot"""

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.bot.loop.create_task(self.start_task())  # Schedule the task to start when ready

    async def start_task(self):
        """Wait for the bot to be ready, then start the task"""
        await self.bot.wait_until_ready()  # Wait until the bot is ready
        self.send_daily_tournament_registration_message.start()  # Start the task when the cog is loaded
        self.send_daily_tournament_start_message.start()  # Start the task when the cog is loaded

    @tasks.loop(time=time_send_daily_registration_tournament)
    async def send_daily_tournament_registration_message(self):
        """
        Send only once every day a message for the registration for each guild who has the bot
        """
        print_log(f"send_daily_tournament_registration_message: Sending daily registration reminder {datetime.now()}")
        for guild in self.bot.guilds:
            guild_id = guild.id
            await send_tournament_registration_to_a_guild(guild_id)

    @send_daily_tournament_registration_message.before_loop
    async def before_send_daily_tournament_registration_message_task(self):
        """Wait for the Send Daily Message Task to have the bot ready"""
        print_log("TournamentTasksCog>send_daily_tournament_registration_message: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @tasks.loop(time=time_send_daily_starting_tournament)
    async def send_daily_tournament_start_message(self):
        """
        Send only once every day a message for the registration for each guild who has the bot
        """
        print_log(f"send_daily_tournament_start_message: Sending starting tournament message {datetime.now()}")
        for guild in self.bot.guilds:
            guild_id = guild.id
            await send_tournament_starting_to_a_guild(guild_id)

    @send_daily_tournament_start_message.before_loop
    async def before_send_daily_tournament_start_message_task(self):
        """Wait for the Send Daily Message Task to have the bot ready"""
        print_log("TournamentTasksCog>send_daily_tournament_start_message: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    async def cog_unload(self):
        self.send_daily_tournament_registration_message.cancel()
        self.send_daily_tournament_start_message.cancel()


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(TournamentTasksCog(bot))
