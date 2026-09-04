"""Open the persistent Tracker browser profile for an operator to solve Cloudflare."""

import os
from pathlib import Path

from dotenv import load_dotenv

from deps.browser_context_manager import BrowserContextManager


def main() -> None:
    load_dotenv()
    profile_dir = os.getenv("BROWSER_PROFILE_DIR", "").strip()
    if not profile_dir:
        raise SystemExit("Set BROWSER_PROFILE_DIR to the same persistent profile used by the bot.")

    profile_path = Path(profile_dir).expanduser()
    print(f"Using Chrome profile: {profile_path}")
    print("A visible Chrome window should open. Complete any Cloudflare check, then press Enter.")

    # ENV=dev keeps this maintenance command on the caller's forwarded display; the profile
    # itself is shared with production so the clearance cookie survives the bot's restart.
    with BrowserContextManager() as context:
        driver = context._active_driver()  # pylint: disable=protected-access
        driver.get("https://tracker.gg")
        input("After validation succeeds, press Enter to close Chrome: ")


if __name__ == "__main__":
    main()
