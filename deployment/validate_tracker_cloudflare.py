"""Open the persistent Tracker browser profile for an operator to solve Cloudflare."""

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from selenium.common.exceptions import InvalidSessionIdException, NoSuchWindowException

# Running this file directly makes deployment/ the import root; add the repository root so
# it can use the same deps package as the bot.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deps.browser_context_manager import BrowserContextManager
from deps.browser_exceptions import BrowserException, BrowserLockContentionException


def clearance_works(context: BrowserContextManager) -> bool:
    """Send one real tracker.gg API request and report whether it was answered."""
    print("Checking with tracker.gg, this can take up to a minute...")
    try:
        context.download_current_season_rank(context.default_profile)
    except BrowserException as e:
        print(f"Still not cleared: {e}")
        return False
    except (InvalidSessionIdException, NoSuchWindowException) as e:
        # Closing the window ends Chrome, so nothing was checked with tracker.gg.
        raise SystemExit(
            "The Chrome window was closed before the check, so nothing was tested. "
            "Run this again and leave the window open; it closes by itself when the check is done."
        ) from e
    return True


def main() -> None:
    load_dotenv()
    profile_dir = os.getenv("BROWSER_PROFILE_DIR", "").strip()
    if not profile_dir:
        raise SystemExit("Set BROWSER_PROFILE_DIR to the same persistent profile used by the bot.")
    if not os.getenv("DISPLAY"):
        raise SystemExit(
            "No display to open Chrome on: X11 forwarding is not active. "
            "Run the ssh -Y command from a terminal with an X server (WSL on Windows, not PowerShell)."
        )

    profile_path = Path(profile_dir).expanduser()
    print(f"Using Chrome profile: {profile_path}")
    print("A visible Chrome window should open on a tracker.gg profile page. Do not close it.")

    # ENV=dev keeps this maintenance command on the caller's forwarded display; the profile
    # itself is shared with production so the clearance cookie survives the bot's restart.
    # The context holds the browser lock, which keeps the running bot out of the profile.
    try:
        with BrowserContextManager() as context:
            input("Tick the box if one shows up, wait for the page to load, then press Enter: ")
            if clearance_works(context):
                print("It worked. Press 'Solved, retry now' in the Discord DM.")
            else:
                print("tracker.gg is still refusing requests. Leave the bot paused and try again later.")
    except BrowserLockContentionException as e:
        raise SystemExit(f"The bot is using the browser right now, try again in a few minutes. ({e})") from e


if __name__ == "__main__":
    main()
