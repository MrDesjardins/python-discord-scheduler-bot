"""A singleton class for the bot instance"""

import discord
from discord import Intents

from deps.mybot import MyBot

intents = Intents.default()
intents.messages = True  # Enable the messages intent
intents.members = True  # Enable the messages intent
intents.reactions = True  # Enable the reactions intent
intents.message_content = True  # Enable the message content intent
intents.guild_reactions = True  # Enable the guild reactions intent
intents.voice_states = True  # Enable voice states to track who is in voice channel


class BotSingleton:
    """A singleton class for the bot instance"""

    _instance: "BotSingleton" = None

    def __new__(cls):
        if not cls._instance:
            cls._instance = super(BotSingleton, cls).__new__(cls)
            cls._instance._bot = MyBot()
        return cls._instance

    @property
    def bot(self) -> discord.Client:
        """Get the bot instance"""
        return self._bot  # pylint: disable=no-member
