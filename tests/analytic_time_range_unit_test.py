"""Unit tests for the shared analytics day-range presets."""

import pytest

from deps.analytic_time_range import (
    PERIOD_LABELS,
    get_from_to_days,
    resolve_day_range,
)


def test_presets_have_one_label_per_index():
    assert len(PERIOD_LABELS) == 6
    for index in range(len(PERIOD_LABELS)):
        from_day, to_day = get_from_to_days(index)
        assert from_day >= 0
        assert to_day >= 0


def test_last_30_days_is_thirty_days_back_until_today():
    assert get_from_to_days(0) == (30, 0)


def test_unknown_index_falls_back_to_today():
    assert get_from_to_days(99) == (0, 0)


def test_custom_offsets_override_the_preset():
    assert resolve_day_range(0, 7, 1) == (7, 1)


def test_custom_offsets_can_override_only_the_end():
    assert resolve_day_range(0, to_day_ago=3) == (30, 3)


def test_reversed_custom_range_is_rejected():
    with pytest.raises(ValueError):
        resolve_day_range(0, 1, 7)


def test_negative_custom_offset_is_rejected():
    with pytest.raises(ValueError):
        resolve_day_range(0, -1, 0)
