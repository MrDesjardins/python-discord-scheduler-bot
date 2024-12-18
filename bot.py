#!/usr/bin/env python3
""" Entry file for the Discord bot """

import os
from dotenv import load_dotenv
from deps.bot_singleton import BotSingleton
from deps.mybot import MyBot
from deps.log import print_log
from deps.tournament_data_access import fetch_tournament_by_id, fetch_tournament_games_by_tournament_id
from deps.tournament_visualizer import plot_tournament_bracket
from deps.tournament_functions import build_tournament_tree

load_dotenv()

ENV = os.getenv("ENV")
TOKEN = os.getenv("BOT_TOKEN_DEV") if ENV == "dev" else os.getenv("BOT_TOKEN")

bot: MyBot = BotSingleton().bot

print_log(f"Env: {ENV}")
print_log(f"Token: {TOKEN}")


def main() -> None:
    """Start the bot"""

    # tournament = fetch_tournament_by_id(123123)
    # tournament_games = fetch_tournament_games_by_tournament_id(tournament.id)
    # tournament_tree = build_tournament_tree(tournament_games)
    # plot_tournament_bracket(tournament, tournament_tree, True)
    bot.run(TOKEN)


if __name__ == "__main__":
    main()
