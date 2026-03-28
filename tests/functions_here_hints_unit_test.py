"""Unit tests for @here / LFG message hint helpers."""

from deps.functions_here_hints import content_suggests_ten_man_lfg


def test_content_suggests_ten_man_lfg_positive_variants():
    """Known 10-man / custom-game phrases match the allowlist."""
    assert content_suggests_ten_man_lfg("Anyone for 10-man tonight?")
    assert content_suggests_ten_man_lfg("10 MAN stack")
    assert content_suggests_ten_man_lfg("need 10MAN")
    assert content_suggests_ten_man_lfg("Ten-man when?")
    assert content_suggests_ten_man_lfg("TEN MAN in 1h")
    assert content_suggests_ten_man_lfg("TENMAN go")
    assert content_suggests_ten_man_lfg("custom game @here")
    assert content_suggests_ten_man_lfg("CUSTOMGAME now")


def test_content_suggests_ten_man_lfg_negative():
    """Generic LFG text without allowlisted substrings does not match."""
    assert not content_suggests_ten_man_lfg("ranked @here anyone on")
    assert not content_suggests_ten_man_lfg("")
    assert not content_suggests_ten_man_lfg("looking for stack")
