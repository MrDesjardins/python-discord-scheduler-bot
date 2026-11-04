"""Pacing and block cooldown shared by every tracker.gg request, across all browser sessions."""

import random
import time
from typing import Any

from deps.browser_exceptions import TrackerBlockedException
from deps.log import print_error_log, print_log

# Random gap between two tracker.gg requests. Warden flagged the bot on 2026-11-02 with 3-12 s gaps.
MIN_REQUEST_GAP_SECONDS = 20.0
MAX_REQUEST_GAP_SECONDS = 50.0
# Pause all traffic after a block, escalating while tracker.gg keeps blocking: requests sent to a
# blocked IP only keep it blocked.
BLOCK_COOLDOWNS_SECONDS = (60 * 60, 2 * 60 * 60, 4 * 60 * 60, 6 * 60 * 60)
WARDEN_CHALLENGE_CODE = "Warden::Challenge"

# Requests are serialized by the browser FileLock, so this state needs no lock of its own.
_last_request_at: float = float("-inf")
_blocked_until: float = 0.0
_consecutive_blocks: int = 0


def tracker_block_remaining_seconds() -> float:
    """Seconds left before tracker.gg may be queried again (0 when not blocked)."""
    return max(0.0, _blocked_until - time.monotonic())


def wait_before_request(log_name: str) -> None:
    """Sleep a random gap since the previous request; raise instead while a block cooldown is active."""
    global _last_request_at  # pylint: disable=global-statement
    remaining = tracker_block_remaining_seconds()
    if remaining > 0:
        raise TrackerBlockedException(remaining)
    wait = _last_request_at + random.uniform(MIN_REQUEST_GAP_SECONDS, MAX_REQUEST_GAP_SECONDS) - time.monotonic()
    if wait > 0:
        print_log(f"{log_name}: Waiting {wait:.0f}s before the next tracker.gg request")
        time.sleep(wait)
    _last_request_at = time.monotonic()


def check_tracker_response(data: Any, log_name: str) -> None:
    """Raise TrackerBlockedException and start a cooldown when the response is a Warden block."""
    global _blocked_until, _consecutive_blocks  # pylint: disable=global-statement
    errors = data.get("errors") if isinstance(data, dict) else None
    if not (
        isinstance(errors, list)
        and any(isinstance(err, dict) and err.get("code") == WARDEN_CHALLENGE_CODE for err in errors)
    ):
        _consecutive_blocks = 0
        return
    cooldown = BLOCK_COOLDOWNS_SECONDS[min(_consecutive_blocks, len(BLOCK_COOLDOWNS_SECONDS) - 1)]
    _consecutive_blocks += 1
    _blocked_until = time.monotonic() + cooldown
    print_error_log(
        f"{log_name}: tracker.gg Warden block ({_consecutive_blocks} in a row); "
        f"pausing all tracker.gg requests for {cooldown / 60:.0f} min"
    )
    raise TrackerBlockedException(cooldown)
