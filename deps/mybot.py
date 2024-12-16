""" Custom bot class for Discord bot """

import discord
from discord.ext import commands
import os

from deps.log import print_log, print_error_log


class MyBot(commands.Bot):
    """Add attribute to the Discord bot"""

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.messages = True  # Enable the messages intent
        intents.members = True  # Enable the messages intent
        intents.reactions = True  # Enable the reactions intent
        intents.message_content = True  # Enable the message content intent
        intents.guild_reactions = True  # Enable the guild reactions intent
        intents.voice_states = True  # Enable voice states to track who is in voice channel
        super().__init__(command_prefix="!", intents=intents)
        self.allowed_mentions = discord.AllowedMentions(everyone=True, roles=True, users=True)
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
