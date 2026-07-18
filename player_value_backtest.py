#!/usr/bin/env python3
"""
Backtest the Performance Elo algorithm: replay each user's first 80% of matches
to build a rating, then predict the win probability of the remaining 20% and
score the predictions (Brier score, accuracy).

Compares the current Elo implementation against the previous version (raw-K/D
multiplier, kept here only as a benchmark) and a coin-flip baseline, and reports
how each algorithm's ordering correlates with the others.

Usage:
    python3 player_value_backtest.py
"""

from typing import Callable, Dict, List, Sequence, Tuple

from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
from deps.analytic_player_value_data_access import data_access_fetch_all_user_ids_with_matches
from deps.analytic_player_value_functions import (
    ELO_DEFAULT_SEED,
    ELO_RP_DIFF_CLAMP,
    PerformanceEloState,
    apply_performance_elo_match,
    compute_all_player_values,
)
from deps.models import PlayerValueAlgorithm, UserFullMatchStats

MIN_MATCHES_FOR_BACKTEST = 60
HOLDOUT_RATIO = 0.2

# A stepper consumes one match and returns the expected outcome it predicted for it
Stepper = Callable[[UserFullMatchStats], float]


def make_old_elo_stepper(seed: float) -> Stepper:
    """Previous algorithm (benchmark only): win/loss outcome scaled by a raw-K/D multiplier"""
    state = {"rating": seed, "index": 0}

    def step(match: UserFullMatchStats) -> float:
        rating = state["rating"]
        lobby_rp = float(match.rank_points) if match.rank_points > 0 else rating
        rp_diff = min(max(lobby_rp - rating, -ELO_RP_DIFF_CLAMP), ELO_RP_DIFF_CLAMP)
        expected = 1.0 / (1.0 + 10.0 ** (rp_diff / 400.0))
        outcome = 1.0 if match.has_win else 0.0
        kd = match.kill_count / max(match.death_count, 1)
        if match.has_win:
            multiplier = min(max(0.7 + 0.3 * kd, 0.5), 1.5)
        else:
            multiplier = min(max(1.3 - 0.3 * kd, 0.5), 1.5)
        if state["index"] < 50:
            k_factor = 40.0
        elif state["index"] < 150:
            k_factor = 24.0
        else:
            k_factor = 16.0
        state["rating"] = rating + k_factor * multiplier * (outcome - expected)
        state["index"] += 1
        return expected

    return step


def make_new_elo_stepper(seed: float) -> Stepper:
    """Current production algorithm, reusing the module's per-match update"""
    state = PerformanceEloState(rating=seed)

    def step(match: UserFullMatchStats) -> float:
        return apply_performance_elo_match(state, match)

    return step


def backtest_variant(
    matches_by_user: Dict[int, List[UserFullMatchStats]],
    make_stepper: Callable[[float], Stepper],
) -> Tuple[float, float, int]:
    """Train on the first 80% of each user's matches, score win predictions on the rest"""
    squared_errors: List[float] = []
    correct = 0
    for matches in matches_by_user.values():
        usable = [m for m in matches if not m.is_rollback and m.round_played_count > 0]
        if len(usable) < MIN_MATCHES_FOR_BACKTEST:
            continue
        usable.sort(key=lambda m: m.match_timestamp)
        split = int(len(usable) * (1 - HOLDOUT_RATIO))
        seed = next((float(m.rank_points) for m in usable if m.rank_points > 0), ELO_DEFAULT_SEED)
        step = make_stepper(seed)
        for index, match in enumerate(usable):
            expected = step(match)
            if index >= split:
                win = 1.0 if match.has_win else 0.0
                squared_errors.append((expected - win) ** 2)
                correct += 1 if (expected > 0.5) == match.has_win else 0
    brier = sum(squared_errors) / len(squared_errors) if squared_errors else 0.0
    accuracy = correct / len(squared_errors) if squared_errors else 0.0
    return brier, accuracy, len(squared_errors)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation between two same-length series"""

    def ranks(values: Sequence[float]) -> List[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        result = [0.0] * len(values)
        for position, index in enumerate(order):
            result[index] = float(position)
        return result

    rank_x, rank_y = ranks(xs), ranks(ys)
    n = len(xs)
    mean_x, mean_y = sum(rank_x) / n, sum(rank_y) / n
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(rank_x, rank_y))
    denominator = (sum((a - mean_x) ** 2 for a in rank_x) * sum((b - mean_y) ** 2 for b in rank_y)) ** 0.5
    return numerator / denominator if denominator else 0.0


def report_ordering_correlations(matches_by_user: Dict[int, List[UserFullMatchStats]]) -> None:
    """How the current Elo ordering relates to algo 1 and to the raw current rank points"""
    results = compute_all_player_values(matches_by_user)
    rows = []
    for user_id, user_results in results.items():
        if (
            PlayerValueAlgorithm.CURRENT_FORM not in user_results
            or PlayerValueAlgorithm.PERFORMANCE_ELO not in user_results
        ):
            continue
        newest = max(matches_by_user[user_id], key=lambda m: m.match_timestamp)
        rows.append(
            (
                user_results[PlayerValueAlgorithm.CURRENT_FORM].value,
                user_results[PlayerValueAlgorithm.PERFORMANCE_ELO].value,
                float(newest.rank_points),
            )
        )
    algo1 = [r[0] for r in rows]
    elo = [r[1] for r in rows]
    current_rp = [r[2] for r in rows]
    print(f"\nOrdering correlations over {len(rows)} users (Spearman):")
    print(f"  Elo vs algo 1 (current form): {spearman(elo, algo1):.3f}")
    print(f"  Elo vs current rank points:   {spearman(elo, current_rp):.3f}")
    print(f"  algo 1 vs current rank points: {spearman(algo1, current_rp):.3f}")


def main() -> None:
    """Run the backtest for both Elo variants and print the comparison"""
    user_ids = data_access_fetch_all_user_ids_with_matches()
    matches_by_user = data_access_fetch_user_matches_in_time_range(user_ids, None, None)

    print(f"Backtest: users with >= {MIN_MATCHES_FOR_BACKTEST} matches, last {HOLDOUT_RATIO:.0%} of matches held out")
    print(f"{'variant':<28}{'brier (lower=better)':<24}{'accuracy':<12}{'predictions'}")
    for label, make_stepper in (
        ("old Elo (raw K/D scaling)", make_old_elo_stepper),
        ("new Elo (per-round blend)", make_new_elo_stepper),
    ):
        brier, accuracy, count = backtest_variant(matches_by_user, make_stepper)
        print(f"{label:<28}{brier:<24.4f}{accuracy:<12.3f}{count}")
    print(f"{'coin flip baseline':<28}{0.25:<24.4f}{'0.500':<12}-")

    report_ordering_correlations(matches_by_user)


if __name__ == "__main__":
    main()
