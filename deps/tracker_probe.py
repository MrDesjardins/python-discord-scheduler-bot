"""One live tracker.gg request so the bot owner can check the integration on demand."""

from deps.browser_context_manager import BrowserContextManager, is_browser_busy
from deps.browser_exceptions import BrowserLockContentionException, TrackerBlockedException
from deps.tracker_pacing import tracker_block_remaining_seconds

# Startup errors can embed a whole chromedriver stack trace; Discord refuses messages over 2000.
MAX_DETAIL_CHARACTERS = 500

STATE_LABELS = {
    "ok": "reachable",
    "challenge": "Cloudflare challenge not solved",
    "blocked": "blocked / cooling down",
    "unreachable": "no JSON and no challenge page",
    "browser_busy": "browser busy with another task",
    "browser_unavailable": "browser could not start",
}


def probe_tracker_api() -> dict[str, str]:
    """Run one tracker.gg request and return {'state', 'detail'}.

    The state drives the wording only; a Warden block raised by the probe is the same
    block the normal job would have hit, so it starts the usual cooldown.
    """
    remaining = tracker_block_remaining_seconds()
    if remaining > 0:
        return {"state": "blocked", "detail": f"cooldown with {remaining / 60:.0f} min left"}
    if is_browser_busy():
        # __enter__ would otherwise wait up to 120 s for the lock before reporting it.
        return {"state": "browser_busy", "detail": "another task is using the browser"}
    try:
        with BrowserContextManager() as context:
            return context.probe_api(context.default_profile)
    except TrackerBlockedException as e:
        return {"state": "blocked", "detail": str(e)}
    except BrowserLockContentionException as e:
        return {"state": "browser_busy", "detail": str(e)}
    except Exception as e:  # pylint: disable=broad-except
        return {"state": "browser_unavailable", "detail": str(e)[:MAX_DETAIL_CHARACTERS]}
