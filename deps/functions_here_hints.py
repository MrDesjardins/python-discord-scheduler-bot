"""Helpers for interpreting message content (e.g. @here education)."""

_TEN_MAN_LFG_SUBSTRINGS = (
    "10-man",
    "10 man",
    "10man",
    "ten-man",
    "ten man",
    "tenman",
    "custom game",
    "customgame",
)


def content_suggests_ten_man_lfg(content: str) -> bool:
    """Return True if message content plausibly refers to a 10-man / custom game LFG."""
    lowered = content.lower()
    return any(fragment in lowered for fragment in _TEN_MAN_LFG_SUBSTRINGS)
