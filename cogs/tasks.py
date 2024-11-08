from datetime import datetime, time
from discord.ext import commands, tasks
import pytz
from deps.bot_common_actions import check_voice_channel, send_daily_question_to_a_guild
from deps.mybot import MyBot
from deps.log import print_log

HOUR_SEND_DAILY_MESSAGE = 7
local_tz = pytz.timezone("America/Los_Angeles")
time_send_daily_message = time(hour=HOUR_SEND_DAILY_MESSAGE, minute=0, second=0, tzinfo=local_tz)


class MyTasksCog(commands.Cog):
    """Code that run a schedule"""

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.check_voice_channel_task.start()  # Start the task when the cog is loaded
        self.send_daily_question_to_all_guild_task.start()  # Start the task when the cog is loaded

    @tasks.loop(minutes=16)
    async def check_voice_channel_task(self):
        """
        Every x minutes capture who is in the voice channel and reflects the people in the schedule
        """
        await check_voice_channel(self.bot)

    @tasks.loop(time=time_send_daily_message)
    async def send_daily_question_to_all_guild_task(self):
        """
        Send only once every day the question for each guild who has the bot
        """
        print_log(f"Sending daily schedule message, current time {datetime.now()}")
        for guild in self.bot.guilds:
            await send_daily_question_to_a_guild(self.bot, guild)

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

    async def cog_unload(self):
        self.check_voice_channel_task.cancel()


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(MyTasksCog(bot))
