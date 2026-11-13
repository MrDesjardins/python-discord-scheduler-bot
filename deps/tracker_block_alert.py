"""Poke the bot owner by DM when tracker.gg needs a human to solve its challenge."""

import getpass
from pathlib import Path

import discord

from deps.log import print_error_log, print_log
from deps.mybot import MyBot
from deps.tracker_pacing import (
    request_tracker_attention,
    take_tracker_attention_request,
    tracker_block_remaining_seconds,
)
from ui.tracker_block_view import TrackerBlockView

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
# The PC cannot resolve the server hostname (mini-pc), so the DM gives its LAN address.
BOT_SERVER_ADDRESS = "10.0.0.181"


def build_tracker_block_message(cooldown_seconds: float) -> str:
    """The DM text, with the exact command to open this machine's Chrome profile."""
    status = (
        f"All tracker.gg requests are paused for another {cooldown_seconds / 60:.0f} min."
        if cooldown_seconds > 0
        else "tracker.gg requests are failing until it is solved."
    )
    command = (
        f"ssh -Y {getpass.getuser()}@{BOT_SERVER_ADDRESS} "
        f"'cd {REPOSITORY_ROOT} && ENV=dev .venv/bin/python deployment/validate_tracker_cloudflare.py'"
    )
    return (
        f"**tracker.gg wants a human check.** {status}\n"
        f"1. From WSL on your PC, not PowerShell, run (no need to stop the bot):\n```sh\n{command}\n```\n"
        "2. Tick the box in the Chrome window, then press Enter in the terminal.\n"
        "3. If the terminal says it worked, press **Solved, retry now**."
    )


async def fetch_application_owner(bot: MyBot) -> discord.User:
    """
    The person who owns the Discord application. A team-owned application reports a team
    pseudo-user as its owner, which Discord refuses to DM (error 50007), so use the team's owner.
    """
    app_info = await bot.application_info()
    team_owner_id = app_info.team.owner_id if app_info.team else None
    owner_id = team_owner_id or app_info.owner.id
    return await bot.fetch_user(owner_id)


async def send_tracker_block_alert(bot: MyBot) -> None:
    """DM the owner of the Discord application when a tracker.gg challenge is waiting for them."""
    if not take_tracker_attention_request():
        return
    try:
        owner = await fetch_application_owner(bot)
        await owner.send(build_tracker_block_message(tracker_block_remaining_seconds()), view=TrackerBlockView())
        print_log("send_tracker_block_alert: Asked the bot owner to solve the tracker.gg challenge")
    except Exception as e:
        print_error_log(f"send_tracker_block_alert: Could not DM the bot owner: {e}")
        request_tracker_attention()  # Tried again once the gap between alerts has passed
