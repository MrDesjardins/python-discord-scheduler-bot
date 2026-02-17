"""
Tasks are running code that is scheduled to run at a specific time or interval.
"""

from datetime import datetime, time, timedelta, timezone
from discord.ext import commands, tasks
import pytz
from deps.ai.ai_bot_functions import send_daily_ai_summary_guild
from deps.bot_common_actions import (
    check_voice_channel,
    persist_siege_matches_cross_guilds,
    persist_user_full_information_cross_guilds,
    post_queued_user_stats,
    send_daily_question_to_a_guild,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_log
from deps.system_database import run_wal_checkpoint
from deps.functions_stats import send_daily_stats_to_a_guild

local_tz = pytz.timezone("America/Los_Angeles")
utc_tz = pytz.timezone("UTC")
time_send_daily_message = time(hour=7, minute=0, second=0, tzinfo=local_tz)
time_fetch_matches = time(hour=23, minute=30, second=0, tzinfo=local_tz)
time_fetch_user_information = time(hour=1, minute=0, second=0, tzinfo=local_tz)
time_send_daily_stats = time(hour=11, minute=35, second=0, tzinfo=local_tz)
time_run_db_checkpoint = time(hour=3, minute=9, second=0, tzinfo=local_tz)
time_generate_ai_summary = time(hour=8, minute=45, second=0, tzinfo=local_tz)


class MyTasksCog(commands.Cog):
    """Code that run a schedule"""

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.bot.loop.create_task(self.start_task())  # Schedule the task to start when ready

    async def start_task(self):
        """Wait for the bot to be ready, then start the task"""
        await self.bot.wait_until_ready()  # Wait until the bot is ready
        # await self.bot.ready_event.wait()  # Wait for on_ready() to fully complete
        print_log("MyTasksCog>start_task: Bot is ready, starting tasks...")
        self.check_voice_channel_task.start()  # Start the task when the cog is loaded
        self.send_queue_user_stats.start()  # Start the task when the cog is loaded
        self.send_daily_question_to_all_guild_task.start()  # Start the task when the cog is loaded
        self.daily_saving_active_user_match_stats_task.start()  # Start the task when the cog is loaded
        self.daily_saving_active_user_information_task.start()  # Start the task when the cog is loaded
        self.send_daily_stats_to_all_guild_task.start()  # Start the task when the cog is loaded
        self.run_db_checkpoint_task.start()  # Start the task when the cog is loaded
        self.send_daily_ai_summary.start()  # Start the task when the cog is loaded
        print_log("MyTasksCog>start_task: Bot is ready, all tasks started")

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

    @tasks.loop(time=time_fetch_matches)
    async def daily_saving_active_user_match_stats_task(self):
        """
        Find the active users in the last 24 hours and save their stats in the database
        """
        print_log(f"Daily fetch stats and save in database, current time {datetime.now()}")
        now_utc = datetime.now(timezone.utc)
        # beginning_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        # end_of_day = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        begin_time = now_utc - timedelta(days=1)
        end_time = now_utc
        await persist_siege_matches_cross_guilds(begin_time, end_time)

    @tasks.loop(time=time_fetch_user_information)
    async def daily_saving_active_user_information_task(self):
        """
        Find the active users in the last 24 hours and save their user information in the database
        """
        print_log(f"Daily fetch user information and save in database, current time {datetime.now()}")
        now_utc = datetime.now(timezone.utc)
        # beginning_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        # end_of_day = now_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
        begin_time = now_utc - timedelta(days=1)
        end_time = now_utc
        await persist_user_full_information_cross_guilds(begin_time, end_time)

    @tasks.loop(time=time_send_daily_stats)
    async def send_daily_stats_to_all_guild_task(self):
        """
        Send only once every day the question for each guild who has the bot
        """
        print_log(f"Sending daily stats message, current time {datetime.now()}")
        for guild in self.bot.guilds:
            await send_daily_stats_to_a_guild(guild)

    @tasks.loop(time=time_run_db_checkpoint)
    async def run_db_checkpoint_task(self):
        """
        Every day, ensure the database is checkpointed
        """
        print_log(f"Running SQL Lite Checkpoint, current time {datetime.now()}")
        try:
            run_wal_checkpoint()
        except Exception as e:
            print_error_log(f"run_db_checkpoint_task task: {e}")

    @tasks.loop(time=time_generate_ai_summary)
    async def send_daily_ai_summary(self):
        """
        Every day, send a message
        """
        print_log(f"send_daily_ai_summary, current time {datetime.now()}")

        # Download matches for active users in the last 24 hours BEFORE generating the summary
        # This ensures users still in voice get their matches included
        now_utc = datetime.now(timezone.utc)
        begin_time = now_utc - timedelta(hours=24)
        end_time = now_utc
        print_log(f"send_daily_ai_summary: Downloading matches for active users from {begin_time} to {end_time}")
        await persist_siege_matches_cross_guilds(begin_time, end_time)

        for guild in self.bot.guilds:
            await send_daily_ai_summary_guild(guild)

    ### ============================ BEFORE LOOP ============================ ###

    @check_voice_channel_task.before_loop
    async def before_check_voice_channel_task(self):
        """Wait for the Voice Channel Task to have the bot ready"""
        print_log("MyTasksCog>check_voice_channel: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @send_queue_user_stats.before_loop
    async def before_send_queue_user_stats(self):
        """Wait for the Send Daily Message Task to have the bot ready"""
        print_log("MyTasksCog>send_queue_user_stats: Waiting for bot to be ready...")
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

    @daily_saving_active_user_information_task.before_loop
    async def before_daily_saving_active_user_information_task(self):
        """Wait for the download user information task for the bot ready"""
        print_log("MyTasksCog>daily_saving_active_user_match_stats_task: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @send_daily_stats_to_all_guild_task.before_loop
    async def before_send_daily_stats_to_all_guild_task(self):
        """Wait for the daily stats task for the bot ready"""
        print_log("MyTasksCog>send_daily_stats_to_all_guild_task: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @run_db_checkpoint_task.before_loop
    async def before_run_db_checkpoint_task(self):
        """Wait for the checkpoint task for the bot ready"""
        print_log("MyTasksCog>run_db_checkpoint_task: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    @send_daily_ai_summary.before_loop
    async def before_send_daily_ai_summary(self):
        """Wait for the AI summary task for the bot ready"""
        print_log("MyTasksCog>send_daily_ai_summary: Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

    ### ============================ UNLOAD COG ============================ ###
    async def cog_unload(self):
        self.check_voice_channel_task.cancel()
        self.send_queue_user_stats.cancel()
        self.send_daily_question_to_all_guild_task.cancel()
        self.daily_saving_active_user_match_stats_task.cancel()
        self.daily_saving_active_user_information_task.cancel()
        self.send_daily_stats_to_all_guild_task.cancel()
        self.run_db_checkpoint_task.cancel()
        self.send_daily_ai_summary.cancel()


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(MyTasksCog(bot))
