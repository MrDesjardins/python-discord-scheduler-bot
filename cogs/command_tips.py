"""Post a daily command lesson in each guild?s configured general channel."""

from datetime import time
from zoneinfo import ZoneInfo

from discord.ext import commands, tasks

from deps.command_tips import send_daily_command_tip
from deps.log import print_error_log


class CommandTipsCog(commands.Cog):
    """Own the daily command spotlight schedule."""

    def __init__(self, bot):
        self.bot = bot
        self.daily_command_tip.start()

    @tasks.loop(time=time(hour=10, tzinfo=ZoneInfo("America/Los_Angeles")))
    async def daily_command_tip(self):
        """Keep one guild?s delivery failure from stopping other guilds? lessons."""
        for guild in self.bot.guilds:
            try:
                await send_daily_command_tip(guild)
            except Exception as exc:
                print_error_log(f"Daily command tip failed for guild {guild.id}: {exc}")

    @daily_command_tip.before_loop
    async def before_daily_command_tip(self):
        """Wait until guilds and channels are available."""
        await self.bot.wait_until_ready()

    def cog_unload(self):
        self.daily_command_tip.cancel()


async def setup(bot):
    """Load the command spotlight cog."""
    await bot.add_cog(CommandTipsCog(bot))
