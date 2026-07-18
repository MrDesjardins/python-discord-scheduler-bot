"""Unit tests for the player value (team balancing) algorithms"""

from datetime import datetime, timedelta, timezone

import pytest

from deps.analytic_player_value_functions import (
    compute_all_player_values,
    compute_match_performance_score,
    compute_performance_metrics,
    compute_value_current_form,
    compute_value_performance_elo,
    compute_value_time_decayed,
    compute_values_performance,
    rank_points_to_dollar,
)
from deps.models import PlayerValueAlgorithm, UserFullMatchStats

NOW = datetime(2026, 7, 15, 12, 0, 0, tzinfo=timezone.utc)


def make_match(**overrides) -> UserFullMatchStats:
    """Create a match with sensible defaults, overridable per test"""
    values = {
        "id": None,
        "match_uuid": "uuid-1",
        "user_id": 1,
        "match_timestamp": NOW - timedelta(days=1),
        "match_duration_ms": 1800000,
        "data_center": "US East",
        "session_type": "Ranked",
        "map_name": "Bank",
        "is_surrender": False,
        "is_forfeit": False,
        "is_rollback": False,
        "r6_tracker_user_uuid": "tracker-uuid",
        "ubisoft_username": "test_user",
        "operators": "Ash,Jager",
        "round_played_count": 8,
        "round_won_count": 4,
        "round_lost_count": 4,
        "round_disconnected_count": 0,
        "kill_count": 8,
        "death_count": 8,
        "assist_count": 2,
        "head_shot_count": 4,
        "tk_count": 0,
        "ace_count": 0,
        "first_kill_count": 1,
        "first_death_count": 1,
        "clutches_win_count": 0,
        "clutches_loss_count": 0,
        "clutches_win_count_1v1": 0,
        "clutches_win_count_1v2": 0,
        "clutches_win_count_1v3": 0,
        "clutches_win_count_1v4": 0,
        "clutches_win_count_1v5": 0,
        "clutches_lost_count_1v1": 0,
        "clutches_lost_count_1v2": 0,
        "clutches_lost_count_1v3": 0,
        "clutches_lost_count_1v4": 0,
        "clutches_lost_count_1v5": 0,
        "kill_1_count": 4,
        "kill_2_count": 2,
        "kill_3_count": 0,
        "kill_4_count": 0,
        "kill_5_count": 0,
        "rank_points": 3000,
        "rank_name": "PLATINUM V",
        "points_gained": 20,
        "rank_previous": 2980,
        "kd_ratio": 1.0,
        "head_shot_percentage": 50.0,
        "kills_per_round": 1.0,
        "deaths_per_round": 1.0,
        "assists_per_round": 0.25,
        "has_win": True,
    }
    values.update(overrides)
    return UserFullMatchStats(**values)


class TestRankPointsToDollar:
    def test_below_copper_floor(self):
        assert rank_points_to_dollar(500) == 10.0

    def test_exact_rank_thresholds(self):
        assert rank_points_to_dollar(2000) == 20.0
        assert rank_points_to_dollar(4000) == 90.0
        assert rank_points_to_dollar(4500) == 120.0

    def test_interpolates_between_ranks(self):
        assert rank_points_to_dollar(2250) == 25.0  # halfway Silver -> Gold
        assert rank_points_to_dollar(4250) == 105.0  # halfway Diamond -> Champion

    def test_extrapolates_above_champion(self):
        assert rank_points_to_dollar(5000) == 150.0


class TestComputeValueCurrentForm:
    def test_no_matches_returns_none(self):
        assert compute_value_current_form([], NOW) is None

    def test_never_ranked_returns_none(self):
        matches = [make_match(rank_points=0)]
        assert compute_value_current_form(matches, NOW) is None

    def test_rollback_only_returns_none(self):
        matches = [make_match(is_rollback=True)]
        assert compute_value_current_form(matches, NOW) is None

    def test_even_kd_gives_rank_dollar_value(self):
        matches = [make_match(match_uuid=f"m{i}", match_timestamp=NOW - timedelta(days=i)) for i in range(20)]
        result = compute_value_current_form(matches, NOW)
        assert result is not None
        # Same recent and max rank points -> effective is 3000 (Platinum floor, 50$), K/D exactly 1.0
        assert result.rating == 3000.0
        assert result.value == 50.0

    def test_higher_kd_gives_higher_value(self):
        even = [make_match(match_uuid=f"m{i}", match_timestamp=NOW - timedelta(days=i)) for i in range(20)]
        fragger = [
            make_match(match_uuid=f"m{i}", match_timestamp=NOW - timedelta(days=i), kill_count=16, death_count=4)
            for i in range(20)
        ]
        result_even = compute_value_current_form(even, NOW)
        result_fragger = compute_value_current_form(fragger, NOW)
        assert result_fragger.value > result_even.value

    def test_stale_peak_weighs_less_than_recent(self):
        # One old Champion match, recent matches at Gold
        matches = [make_match(match_uuid="old", match_timestamp=NOW - timedelta(days=400), rank_points=4500)]
        matches += [
            make_match(match_uuid=f"m{i}", match_timestamp=NOW - timedelta(days=i), rank_points=2500) for i in range(15)
        ]
        result = compute_value_current_form(matches, NOW)
        # Effective rank points: 0.65 * 2500 + 0.35 * 4500 = 3200, well below the old peak
        assert result.rating == 3200.0


class TestComputeValuesPerformance:
    def test_better_performer_at_same_rank_gets_higher_value(self):
        metrics_by_user = {}
        for user_id in range(1, 10):
            matches = [
                make_match(user_id=user_id, match_uuid=f"u{user_id}m{i}", match_timestamp=NOW - timedelta(days=i))
                for i in range(20)
            ]
            metrics_by_user[user_id] = compute_performance_metrics(matches, NOW)
        strong_matches = [
            make_match(
                user_id=99,
                match_uuid=f"u99m{i}",
                match_timestamp=NOW - timedelta(days=i),
                kill_count=16,
                death_count=4,
                first_kill_count=3,
                first_death_count=0,
                round_won_count=6,
                round_lost_count=2,
            )
            for i in range(20)
        ]
        metrics_by_user[99] = compute_performance_metrics(strong_matches, NOW)
        results = compute_values_performance(metrics_by_user)
        assert results[99].value > results[1].value
        assert results[99].rating > 0

    def test_empty_returns_empty(self):
        assert compute_values_performance({}) == {}


class TestComputeMatchPerformanceScore:
    def test_average_match_scores_near_half(self):
        match = make_match(round_played_count=8, kill_count=6, death_count=6)
        assert 0.4 < compute_match_performance_score(match) < 0.6

    def test_kill_volume_beats_kill_ratio(self):
        # 12 kills / 6 deaths over 9 rounds is a bigger contribution than
        # 2 kills / 1 death over 4 rounds, even though both are a 2.0 K/D
        high_volume = make_match(round_played_count=9, kill_count=12, death_count=6)
        low_volume = make_match(round_played_count=4, kill_count=2, death_count=1)
        assert compute_match_performance_score(high_volume) > compute_match_performance_score(low_volume)


class TestComputeValuePerformanceElo:
    def test_no_matches_returns_none(self):
        assert compute_value_performance_elo([], NOW) is None

    def test_high_volume_fragger_gains_more_than_low_volume_same_kd(self):
        high_volume = [make_match(match_uuid="m1", round_played_count=9, kill_count=12, death_count=6, has_win=True)]
        low_volume = [make_match(match_uuid="m1", round_played_count=4, kill_count=2, death_count=1, has_win=True)]
        result_high = compute_value_performance_elo(high_volume, NOW)
        result_low = compute_value_performance_elo(low_volume, NOW)
        assert result_high.rating > result_low.rating

    def test_dominant_loss_costs_less_than_passive_loss(self):
        dominant = [make_match(match_uuid="m1", round_played_count=9, kill_count=13, death_count=5, has_win=False)]
        passive = [make_match(match_uuid="m1", round_played_count=9, kill_count=2, death_count=8, has_win=False)]
        result_dominant = compute_value_performance_elo(dominant, NOW)
        result_passive = compute_value_performance_elo(passive, NOW)
        assert result_dominant.rating > result_passive.rating

    def test_season_reset_rp_crash_does_not_crater_rating(self):
        # 20 matches at Champion level, then the season resets the rank points to 2400.
        # The smoothed lobby estimate must keep treating the lobby as ~4400-strength,
        # so the post-reset loss costs about the same as losing at the old rank points.
        history = [
            make_match(
                match_uuid=f"m{i}",
                match_timestamp=NOW - timedelta(days=30) + timedelta(hours=i),
                rank_points=4400,
            )
            for i in range(20)
        ]
        reset_loss = make_match(
            match_uuid="reset",
            match_timestamp=NOW - timedelta(days=1),
            rank_points=2400,
            points_gained=-30,
            has_win=False,
        )
        normal_loss = make_match(
            match_uuid="normal",
            match_timestamp=NOW - timedelta(days=1),
            rank_points=4400,
            points_gained=-30,
            has_win=False,
        )
        rating_after_reset = compute_value_performance_elo(history + [reset_loss], NOW).rating
        rating_after_normal = compute_value_performance_elo(history + [normal_loss], NOW).rating
        assert abs(rating_after_reset - rating_after_normal) < 20

    def test_reset_volatility_match_moves_rating_less(self):
        normal = [make_match(match_uuid="m1", kill_count=12, death_count=4, points_gained=30, has_win=True)]
        placement = [make_match(match_uuid="m1", kill_count=12, death_count=4, points_gained=150, has_win=True)]
        result_normal = compute_value_performance_elo(normal, NOW)
        result_placement = compute_value_performance_elo(placement, NOW)
        assert result_normal.rating - 3000.0 == pytest.approx(2 * (result_placement.rating - 3000.0))

    def test_win_streak_raises_rating_above_seed(self):
        matches = [
            make_match(
                match_uuid=f"m{i}",
                match_timestamp=NOW - timedelta(days=30) + timedelta(hours=i),
                has_win=True,
                kill_count=12,
                death_count=5,
            )
            for i in range(30)
        ]
        result = compute_value_performance_elo(matches, NOW)
        assert result.rating > 3000.0

    def test_loss_streak_lowers_rating_below_seed(self):
        matches = [
            make_match(
                match_uuid=f"m{i}",
                match_timestamp=NOW - timedelta(days=30) + timedelta(hours=i),
                has_win=False,
                kill_count=4,
                death_count=9,
            )
            for i in range(30)
        ]
        result = compute_value_performance_elo(matches, NOW)
        assert result.rating < 3000.0

    def test_idle_rating_drifts_toward_rank_points(self):
        winner = [
            make_match(
                match_uuid=f"m{i}",
                match_timestamp=NOW - timedelta(days=300) + timedelta(hours=i),
                has_win=True,
                kill_count=12,
                death_count=5,
            )
            for i in range(30)
        ]
        active = compute_value_performance_elo(winner, NOW - timedelta(days=298))
        idle = compute_value_performance_elo(winner, NOW)
        # The idle rating decays toward the last match rank points (3000), below the active rating
        assert idle.rating < active.rating
        assert idle.rating > 3000.0


class TestComputeValueTimeDecayed:
    def test_no_matches_returns_none(self):
        assert compute_value_time_decayed([], NOW) is None

    def test_old_peak_is_worth_less_than_recent_identical_peak(self):
        recent_peak = [make_match(match_uuid="m1", rank_points=4400, match_timestamp=NOW - timedelta(days=10))]
        old_peak = [make_match(match_uuid="m1", rank_points=4400, match_timestamp=NOW - timedelta(days=400))]
        result_recent = compute_value_time_decayed(recent_peak, NOW)
        result_old = compute_value_time_decayed(old_peak, NOW)
        assert result_recent.rating > result_old.rating
        assert result_recent.value > result_old.value

    def test_recent_form_outweighs_old_form_in_kd(self):
        # Same matches, opposite chronology: strong recently vs strong long ago
        strong_now = [
            make_match(match_uuid=f"s{i}", match_timestamp=NOW - timedelta(days=i), kill_count=14, death_count=5)
            for i in range(10)
        ] + [
            make_match(match_uuid=f"w{i}", match_timestamp=NOW - timedelta(days=400 + i), kill_count=4, death_count=10)
            for i in range(10)
        ]
        strong_before = [
            make_match(match_uuid=f"w{i}", match_timestamp=NOW - timedelta(days=i), kill_count=4, death_count=10)
            for i in range(10)
        ] + [
            make_match(match_uuid=f"s{i}", match_timestamp=NOW - timedelta(days=400 + i), kill_count=14, death_count=5)
            for i in range(10)
        ]
        result_now = compute_value_time_decayed(strong_now, NOW)
        result_before = compute_value_time_decayed(strong_before, NOW)
        assert result_now.value > result_before.value

    def test_history_still_counts_for_sparse_recent_data(self):
        # A strong history with 2 recent average matches beats an identical
        # recent sample with a weak history
        strong_history = [
            make_match(match_uuid=f"h{i}", match_timestamp=NOW - timedelta(days=100 + i), kill_count=14, death_count=5)
            for i in range(30)
        ] + [make_match(match_uuid=f"r{i}", match_timestamp=NOW - timedelta(days=i)) for i in range(2)]
        weak_history = [
            make_match(match_uuid=f"h{i}", match_timestamp=NOW - timedelta(days=100 + i), kill_count=4, death_count=10)
            for i in range(30)
        ] + [make_match(match_uuid=f"r{i}", match_timestamp=NOW - timedelta(days=i)) for i in range(2)]
        result_strong = compute_value_time_decayed(strong_history, NOW)
        result_weak = compute_value_time_decayed(weak_history, NOW)
        assert result_strong.value > result_weak.value


class TestComputeAllPlayerValues:
    def test_returns_all_four_algorithms(self):
        matches_by_user = {
            1: [make_match(user_id=1, match_uuid=f"m{i}", match_timestamp=NOW - timedelta(days=i)) for i in range(20)]
        }
        results = compute_all_player_values(matches_by_user, NOW)
        assert set(results[1].keys()) == {
            PlayerValueAlgorithm.CURRENT_FORM,
            PlayerValueAlgorithm.PERFORMANCE,
            PlayerValueAlgorithm.PERFORMANCE_ELO,
            PlayerValueAlgorithm.TIME_DECAYED,
        }

    def test_only_user_ids_filters_output_but_keeps_community_baseline(self):
        matches_by_user = {
            user_id: [
                make_match(user_id=user_id, match_uuid=f"u{user_id}m{i}", match_timestamp=NOW - timedelta(days=i))
                for i in range(20)
            ]
            for user_id in (1, 2, 3)
        }
        results = compute_all_player_values(matches_by_user, NOW, only_user_ids=[2])
        assert list(results.keys()) == [2]

    def test_user_without_matches_is_absent(self):
        results = compute_all_player_values({1: []}, NOW)
        assert not results
