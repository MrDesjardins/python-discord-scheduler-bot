""" Custom bot class for Discord bot """

import discord
from discord.ext import commands
import os

from deps.log import print_log, print_error_log


class MyBot(commands.Bot):
    """Add attribute to the Discord bot"""

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.guild_emoji = {}  # Dict[str, Dict[str, str]]

    async def setup_hook(self):
        await self.load_cogs()

    async def load_cogs(self):
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename != "__init__.py":
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print_log(f"✅ Loaded {filename}")
                except Exception as e:
                    print_error_log(f"❌ Failed to load {filename}: {e}")
