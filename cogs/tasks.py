from datetime import datetime, time, timezone
from discord.ext import commands, tasks
import pytz
from deps.bot_common_actions import (
    check_voice_channel,
    persist_siege_matches_cross_guilds,
    post_queued_user_stats,
    send_daily_question_to_a_guild,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_log

local_tz = pytz.timezone("America/Los_Angeles")
utc_tz = pytz.timezone("UTC")
time_send_daily_message = time(hour=7, minute=0, second=0, tzinfo=local_tz)
time_fetch_matches = time(hour=23, minute=0, second=0, tzinfo=local_tz)


class MyTasksCog(commands.Cog):
    """Code that run a schedule"""

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.bot.loop.create_task(self.start_task())  # Schedule the task to start when ready

    async def start_task(self):
        """Wait for the bot to be ready, then start the task"""
        await self.bot.wait_until_ready()  # Wait until the bot is ready
        self.check_voice_channel_task.start()  # Start the task when the cog is loaded
        self.send_queue_user_stats.start()  # Start the task when the cog is loaded
        self.send_daily_question_to_all_guild_task.start()  # Start the task when the cog is loaded
        self.daily_saving_active_user_match_stats_task.start()  # Start the task when the cog is loaded

    @tasks.loop(minutes=16)
    async def check_voice_channel_task(self):
        """
        Every x minutes capture who is in the voice channel and reflects the people in the schedule
        """
        try:
            await check_voice_channel(self.bot)
        except Exception as e:
            print_error_log(f"check_voice_channel_task task: {e}")

    @tasks.loop(minutes=3)
    async def send_queue_user_stats(self):
        """
        Every x minutes post to the gaming stats channel the queued user awaiting for their gaming session
        """
        try:
            await post_queued_user_stats()
        except Exception as e:
            print_error_log(f"send_queue_user_stats task: {e}")

    @tasks.loop(time=time_send_daily_message)
    async def send_daily_question_to_all_guild_task(self):
        """
        Send only once every day the question for each guild who has the bot
        """
        print_log(f"Sending daily schedule message, current time {datetime.now()}")
        for guild in self.bot.guilds:
            await send_daily_question_to_a_guild(self.bot, guild)

    @tasks.loop(time=time_send_daily_message)
    async def daily_saving_active_user_match_stats_task(self):
        """
        Send only once every day the question for each guild who has the bot
        """
        print_log(f"Daily fetch stats and save in database, current time {datetime.now()}")
        now_utc = datetime.now(timezone.utc)
        beginning_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        await persist_siege_matches_cross_guilds(beginning_of_day, end_of_day)

    ### ============================ BEFORE LOOP ============================ ###

    @check_voice_channel_task.before_loop
    async def before_check_voice_channel_task(self):
        """Wait for the Voice Channel Task to have the bot ready"""
        print_log("MyTasksCog>check_voice_channel: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @send_daily_question_to_all_guild_task.before_loop
    async def before_send_daily_question_to_all_guild_task(self):
        """Wait for the Send Daily Message Task to have the bot ready"""
        print_log("MyTasksCog>send_daily_question_to_all_guild_task: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @daily_saving_active_user_match_stats_task.before_loop
    async def before_daily_saving_active_user_match_stats_task(self):
        """Wait for the download matches task for the bot ready"""
        print_log("MyTasksCog>daily_saving_active_user_match_stats_task: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    async def cog_unload(self):
        self.check_voice_channel_task.cancel()


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(MyTasksCog(bot))
