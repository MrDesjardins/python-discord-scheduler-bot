"""Unit tests for map artwork lookup and per-map stats aggregation."""

import pytest

from deps.analytic_match_data_access import summarize_map_matches
from deps.map_images import MAPS_DIR, load_map_image, map_slug


@pytest.mark.parametrize(
    "name, slug",
    [
        ("Kafe Dostoyevsky", "cafedostoyevsky"),
        ("Café Dostoyevsky", "cafedostoyevsky"),
        ("Club House", "clubhouse"),
        ("Clubhouse", "clubhouse"),
        ("Close Quarter", "closequarters"),
        ("Hereford Base", "herefordbase"),
        ("Nighthaven Labs", "nighthavenlabs"),
        ("Theme Park", "themepark"),
    ],
)
def test_map_slug_unifies_spellings(name: str, slug: str) -> None:
    assert map_slug(name) == slug


def test_load_map_image_returns_artwork_for_known_map() -> None:
    image = load_map_image("Kafe Dostoyevsky")
    assert image is not None
    assert image.size == (800, 450)


@pytest.mark.parametrize("name", [None, "", "Not A Real Map"])
def test_load_map_image_returns_none_without_artwork(name: str | None) -> None:
    assert load_map_image(name) is None


def test_every_artwork_file_has_a_slug_that_resolves() -> None:
    for path in MAPS_DIR.glob("*.jpg"):
        assert map_slug(path.stem) == path.stem


def test_summarize_map_matches_counts_record_and_top_operators() -> None:
    rows = [
        ("Villa", True, "Ash,Ash,Mira"),
        ("Villa", False, "Ash,Doc"),
        ("Club House", True, "Zero"),
        ("Chalet", True, "Jackal"),
    ]

    stats = summarize_map_matches(rows, "Villa", top_operators=2)

    assert (stats.matches, stats.wins) == (2, 1)
    assert stats.win_rate == 50.0
    assert stats.top_operators == [("Ash", 3), ("Mira", 1)]


def test_summarize_map_matches_matches_spelling_variants() -> None:
    stats = summarize_map_matches([("Kafe Dostoyevsky", True, "Ash")], "Café Dostoyevsky")

    assert stats.matches == 1


def test_summarize_map_matches_handles_unplayed_map_and_empty_operators() -> None:
    stats = summarize_map_matches([("Villa", True, "")], "Bank")

    assert (stats.matches, stats.wins, stats.top_operators) == (0, 0, [])
    assert stats.win_rate == 0.0
    assert summarize_map_matches([("Villa", True, "")], "Villa").top_operators == []
