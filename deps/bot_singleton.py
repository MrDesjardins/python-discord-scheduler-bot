"""A singleton class for the bot instance"""

import discord
from deps.mybot import MyBot
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
