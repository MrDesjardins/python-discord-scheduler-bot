#!/usr/bin/env python3
""" Entry file for the Discord bot """

import os
from dotenv import load_dotenv
from deps.bot_singleton import BotSingleton
from deps.mybot import MyBot
from deps.log import print_log


load_dotenv()

ENV = os.getenv("ENV")
TOKEN = os.getenv("BOT_TOKEN_DEV") if ENV == "dev" else os.getenv("BOT_TOKEN")

bot: MyBot = BotSingleton().bot

print_log(f"Env: {ENV}")
print_log(f"Token: {TOKEN}")


def main() -> None:
    """Start the bot"""
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
