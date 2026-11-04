"""Poke the bot owner by DM when tracker.gg needs a human to solve its challenge."""

import getpass
from pathlib import Path
import socket

from deps.log import print_error_log, print_log
from deps.mybot import MyBot
from deps.tracker_pacing import (
    request_tracker_attention,
    take_tracker_attention_request,
    tracker_block_remaining_seconds,
)
from ui.tracker_block_view import TrackerBlockView

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_tracker_block_message(cooldown_seconds: float) -> str:
    """The DM text, with the exact command to open this machine's Chrome profile."""
    status = (
        f"All tracker.gg requests are paused for another {cooldown_seconds / 60:.0f} min."
        if cooldown_seconds > 0
        else "tracker.gg requests are failing until it is solved."
    )
    command = (
        f"ssh -Y {getpass.getuser()}@{socket.gethostname()} "
        f"'cd {REPOSITORY_ROOT} && ENV=dev .venv/bin/python deployment/validate_tracker_cloudflare.py'"
    )
    return (
        f"**tracker.gg wants a human check.** {status}\n"
        f"1. From WSL on your PC, not PowerShell, run (no need to stop the bot):\n```sh\n{command}\n```\n"
        "2. Tick the box in the Chrome window, then press Enter in the terminal.\n"
        "3. If the terminal says it worked, press **Solved, retry now**."
    )


async def send_tracker_block_alert(bot: MyBot) -> None:
    """DM the owner of the Discord application when a tracker.gg challenge is waiting for them."""
    if not take_tracker_attention_request():
        return
    try:
        owner = (await bot.application_info()).owner
        await owner.send(build_tracker_block_message(tracker_block_remaining_seconds()), view=TrackerBlockView())
        print_log("send_tracker_block_alert: Asked the bot owner to solve the tracker.gg challenge")
    except Exception as e:
        print_error_log(f"send_tracker_block_alert: Could not DM the bot owner: {e}")
        request_tracker_attention()  # Tried again once the gap between alerts has passed
