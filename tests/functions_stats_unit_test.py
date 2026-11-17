"""
Unit tests for the stats message helpers
"""

from deps.functions_stats import (
    CODE_BLOCK_FENCE,
    available_daily_stats_numbers,
    build_msg_2_columns,
    fit_code_block_message,
)


def test_available_daily_stats_numbers_skips_stats_stats_cc_cannot_produce(monkeypatch):
    """17 would duplicate 18 and 23 has no stats.cc source, so both leave the rotation."""
    monkeypatch.delenv("MATCH_STATS_PROVIDER", raising=False)
    numbers = available_daily_stats_numbers()
    assert numbers == [number for number in range(27) if number not in (17, 23)]


def test_available_daily_stats_numbers_keeps_everything_under_tracker(monkeypatch):
    monkeypatch.setenv("MATCH_STATS_PROVIDER", "tracker")
    assert available_daily_stats_numbers() == list(range(27))


def test_fit_code_block_message_short_message_unchanged():
    """A message under the limit is returned as-is"""
    msg = f"Title\n{CODE_BLOCK_FENCE}row 1\nrow 2\n{CODE_BLOCK_FENCE}"
    assert fit_code_block_message(msg) == msg


def test_fit_code_block_message_drops_rows_and_keeps_block_closed():
    """A too-long table loses its last rows but still ends with a closed code block"""
    rows = "".join(f"row {i:04d}\n" for i in range(500))
    msg = f"Title\n{CODE_BLOCK_FENCE}{rows}{CODE_BLOCK_FENCE}"

    result = fit_code_block_message(msg, max_length=100)

    assert len(result) <= 100
    assert result.startswith(f"Title\n{CODE_BLOCK_FENCE}row 0000\n")
    assert result.endswith(f"\n{CODE_BLOCK_FENCE}")
    assert result.count(CODE_BLOCK_FENCE) == 2


def test_fit_code_block_message_on_real_stats_table():
    """A stats table with many long names fits in Discord's 2000 characters"""
    stats = [(f"player_with_a_long_name_{i}", i) for i in range(200)]
    msg = build_msg_2_columns("matches", "in the last 30 days", ["Name", "Count"], stats, 30)
    assert len(msg) > 2000

    result = fit_code_block_message(msg)

    assert len(result) <= 2000
    assert result.endswith(f"\n{CODE_BLOCK_FENCE}")
    assert result.count(CODE_BLOCK_FENCE) == 2


def test_build_msg_header_uses_actual_row_count():
    """A short list is not announced as a top 30 list"""
    msg = build_msg_2_columns("breaching count", "in the last 30 days", ["Name", "Count"], [("only", 5)], 30)
    assert "Here is the top 1 breaching count" in msg


def test_fit_code_block_message_without_code_block_is_cut():
    """A plain message is simply cut at the limit"""
    assert fit_code_block_message("a" * 3000) == "a" * 2000
