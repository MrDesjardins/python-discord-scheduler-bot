#!uv run
"""Entry file for the Discord bot"""

import os
from dotenv import load_dotenv, dotenv_values
from deps.bot_singleton import BotSingleton
from deps.mybot import MyBot
from deps.log import print_log

# Load .env file first
load_dotenv()

# Get ENV from environment (could be set by systemd or .env)
ENV = os.getenv("ENV")

# In production, ensure .env values take precedence over system environment variables
if ENV == "prod":
    # Load .env values directly and override specific environment variables
    env_values = dotenv_values()

    # Override key environment variables with .env values
    for key in ['BOT_TOKEN', 'BOT_TOKEN_DEV', 'GEMINI_API_KEY', 'OPENAI_API_KEY', 'ENV']:
        if key in env_values and env_values[key] is not None:
            os.environ[key] = env_values[key]

    # Re-read ENV in case it was overridden
    ENV = os.getenv("ENV")

    print_log(f"Production mode: Using .env file values (ENV={ENV})")

TOKEN = os.getenv("BOT_TOKEN_DEV") if ENV == "dev" else os.getenv("BOT_TOKEN")

if TOKEN is None:
    print_log("BOT_TOKEN_DEV not found")
    exit()

TOKEN_STR: str = str(TOKEN)

bot: MyBot = BotSingleton().bot

print_log(f"Env: {ENV}")
print_log(f"Token: {TOKEN}")


def main() -> None:
    """Start the bot"""
    bot.run(TOKEN_STR)


if __name__ == "__main__":
    main()
