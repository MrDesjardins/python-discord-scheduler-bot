"""Custom bot class for Discord bot"""

import os
import logging
import discord
from discord.ext import commands
from deps.log import print_log, print_error_log


class MyBot(commands.Bot):
    """Add attribute to the Discord bot"""

    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True  # Enable the messages intent
        intents.members = True  # Enable the messages intent
        intents.reactions = True  # Enable the reactions intent
        intents.message_content = True  # Enable the message content intent
        intents.guild_reactions = True  # Enable the guild reactions intent
        intents.voice_states = True  # Enable voice states to track who is in voice channel
        intents.presences = True  # Needed to see member activities
        super().__init__(command_prefix="!", intents=intents)
        self.allowed_mentions = discord.AllowedMentions(everyone=False, roles=False, users=True)
        self.guild_emoji = {}  # Dict[str, Dict[str, str]]

    async def setup_hook(self) -> None:
        """Load bot extensions during discord.py startup."""
        await self.load_cogs()

    async def load_cogs(self) -> None:
        """Load every cog module from the local `cogs/` package."""
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print_log(f"✅ Loaded {filename}")
                except Exception as e:  # pylint: disable=broad-exception-caught
                    print_error_log(f"❌ Failed to load {filename}: {e}")

    async def close(self) -> None:
        """Run bot shutdown hooks before closing the Discord client."""
        events_cog = self.cogs.get("MyEventsCog")
        if events_cog is not None and hasattr(events_cog, "handle_bot_shutdown"):
            try:
                await events_cog.handle_bot_shutdown()
            except Exception as e:  # pylint: disable=broad-exception-caught
                print_error_log(f"MyBot.close: Failed bot shutdown cleanup: {e}")
        await super().close()


class ClockDriftFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """Suppress noisy discord task-loop clock drift warnings."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Return False for known harmless clock drift warnings."""
        # Filter out the clock drift warning
        return "Clock drift detected" not in record.getMessage()


# Apply the filter to the discord.ext.tasks logger
logger = logging.getLogger("discord.ext.tasks")
logger.addFilter(ClockDriftFilter())
