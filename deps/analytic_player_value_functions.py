"""
Player value computation for tournament/custom-game team balancing.

Each algorithm produces a single scalar "value" per user on the community's
familiar rank-dollar scale (Copper 10 ... Champion 120, extrapolated above):

1. CURRENT_FORM: rank dollars from a blend of recent-peak and all-time-peak
   rank points, multiplied by the recent (shrunk) K/D. Modernized version of
   the manual spreadsheet method.
2. PERFORMANCE: rank-anchored composite. The effective rank points set the base
   value; per-round performance metrics (kills/deaths per round, opening duels,
   clutches, win rates) z-scored against peers at a similar rank adjust it up
   or down. Rewards players who carry their lobbies, penalizes coasting.
3. PERFORMANCE_ELO: Elo-style rating seeded from rank points and replayed
   over the full match history; the outcome of each match blends the win/loss
   with the per-round performance (kills/deaths per round versus the community
   average), compared against the expected outcome at the player's lobby level.
4. TIME_DECAYED: rank dollars of the time-decayed peak rank points multiplied
   by the exponentially recency-weighted K/D over the whole history. No hard
   windows: recent form dominates but sparsely captured players keep their
   (discounted) history's signal.
"""

import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
from deps.analytic_player_value_data_access import (
    data_access_fetch_all_user_ids_with_matches,
    data_access_upsert_player_value,
)
from deps.log import print_log
from deps.models import PlayerValueAlgorithm, PlayerValueResult, UserFullMatchStats

# Community rank-dollar scale: (rank floor in rank points, dollar value)
RANK_DOLLAR_TABLE = [
    (1000, 10.0),  # Copper
    (1500, 10.0),  # Bronze
    (2000, 20.0),  # Silver
    (2500, 30.0),  # Gold
    (3000, 50.0),  # Platinum
    (3500, 70.0),  # Emerald
    (4000, 90.0),  # Diamond
    (4500, 120.0),  # Champion
]
# Dollars per rank point above the Champion threshold (same slope as Diamond->Champion)
DOLLAR_SLOPE_ABOVE_CHAMPION = (120.0 - 90.0) / 500.0

RECENT_WINDOW_DAYS = 90
RECENT_WINDOW_EXTENDED_DAYS = 180
MIN_RECENT_MATCHES = 10
RECENT_FALLBACK_MATCH_COUNT = 20

# Number of kills/deaths of prior (at K/D 1.0) blended into the recent K/D
KD_SHRINKAGE_PRIOR = 20
# Weight of the recent-peak rank points versus the all-time peak
CURRENT_FORM_RECENT_RP_WEIGHT = 0.65

# Composite z-score weights (must sum to 1.0)
PERFORMANCE_WEIGHTS = {
    "kills_per_round": 0.30,
    "deaths_per_round": 0.20,  # inverted: fewer deaths is better
    "opening_duel_rate": 0.12,
    "clutch_rate": 0.08,
    "round_win_rate": 0.15,
    "match_win_rate": 0.10,
    "multi_kill_per_round": 0.05,
}
PERFORMANCE_Z_CLAMP = 2.0
PERFORMANCE_SHRINKAGE_MATCHES = 15
# Users within this rank-point distance are the peer group for the z-scores;
# widened progressively until enough peers are found.
PERFORMANCE_PEER_RP_WINDOWS = [400.0, 800.0, float("inf")]
PERFORMANCE_MIN_PEERS = 8
# Value adjustment per composite z-score unit (z=+2 -> +70% of base value)
PERFORMANCE_Z_MULTIPLIER = 0.35
VALUE_MIN = 10.0
VALUE_MAX = 170.0

ELO_DEFAULT_SEED = 2500.0
ELO_RP_DIFF_CLAMP = 600.0
ELO_IDLE_DECAY_PER_MONTH = 0.05
ELO_IDLE_DECAY_MAX = 0.5
# Weight of the per-round performance score versus pure win/loss in the match outcome
ELO_PERF_WEIGHT = 0.6
# Community per-match averages and spreads, calibrated from the stored ranked matches
ELO_EXPECTED_KILLS_PER_ROUND = 0.72
ELO_KILLS_PER_ROUND_STD = 0.44
ELO_EXPECTED_DEATHS_PER_ROUND = 0.74
ELO_DEATHS_PER_ROUND_STD = 0.21
ELO_PERF_KPR_WEIGHT = 0.7
ELO_PERF_DPR_WEIGHT = 0.3
ELO_PERF_SCORE_CLAMP = 0.95
# Matches with a rank-point swing this large are placements/seasonal resets where
# rank points misrepresent the lobby strength; they update the rating at half K.
ELO_RESET_POINTS_GAINED_THRESHOLD = 60
# The lobby strength proxy is a running max of the rank points with a slow decay,
# because seasonal resets crash the visible rank points while the hidden-MMR
# matchmaking keeps putting the player in lobbies at their real level.
ELO_LOBBY_DECAY_PER_MATCH = 0.995

# TIME_DECAYED: no hard windows, every match counts with exponential recency decay
# so recent form dominates but sparse-capture players keep their history's signal.
TIME_DECAY_KD_HALF_LIFE_DAYS = 210
# A peak in rank points loses this much per day of age (~440 rank points per year)
TIME_DECAY_PEAK_FADE_RP_PER_DAY = 1.2
# Kills/deaths of prior (at K/D 1.0) blended into the decayed K/D
TIME_DECAY_KD_PRIOR = 15


# The algorithm consumers (team balancing) read. Change here once an algorithm is chosen.
PLAYER_VALUE_OFFICIAL_ALGORITHM = PlayerValueAlgorithm.TIME_DECAYED


@dataclass
class PerformanceMetrics:
    """Raw per-user metrics used by the PERFORMANCE algorithm before normalization."""

    kills_per_round: float
    deaths_per_round: float
    opening_duel_rate: float
    clutch_rate: float
    round_win_rate: float
    match_win_rate: float
    multi_kill_per_round: float
    effective_rank_points: float
    match_count: int
    last_match_timestamp: Optional[datetime]


def rank_points_to_dollar(rank_points: float) -> float:
    """Map rank points to the community dollar scale with linear interpolation between ranks."""
    if rank_points <= RANK_DOLLAR_TABLE[0][0]:
        return RANK_DOLLAR_TABLE[0][1]
    last_rp, last_dollar = RANK_DOLLAR_TABLE[-1]
    if rank_points >= last_rp:
        return last_dollar + (rank_points - last_rp) * DOLLAR_SLOPE_ABOVE_CHAMPION
    for (low_rp, low_dollar), (high_rp, high_dollar) in zip(RANK_DOLLAR_TABLE, RANK_DOLLAR_TABLE[1:]):
        if low_rp <= rank_points < high_rp:
            ratio = (rank_points - low_rp) / (high_rp - low_rp)
            return low_dollar + ratio * (high_dollar - low_dollar)
    return last_dollar


def _usable_matches_newest_first(matches: List[UserFullMatchStats]) -> List[UserFullMatchStats]:
    """Keep matches that count for skill (no rollback, rounds actually played), newest first."""
    usable = [m for m in matches if not m.is_rollback and m.round_played_count > 0]
    usable.sort(key=lambda m: m.match_timestamp, reverse=True)
    return usable


def _select_recent_matches(matches_newest_first: List[UserFullMatchStats], now: datetime) -> List[UserFullMatchStats]:
    """
    Matches from the last 90 days; widen to 180 days then to the last 20 matches
    when the sample is too small to be meaningful.
    """
    for days in (RECENT_WINDOW_DAYS, RECENT_WINDOW_EXTENDED_DAYS):
        cutoff = now - timedelta(days=days)
        recent = [m for m in matches_newest_first if m.match_timestamp >= cutoff]
        if len(recent) >= MIN_RECENT_MATCHES:
            return recent
    return matches_newest_first[:RECENT_FALLBACK_MATCH_COUNT]


def _compute_effective_rank_points(
    usable_newest_first: List[UserFullMatchStats], recent: List[UserFullMatchStats]
) -> Optional[float]:
    """Blend of the recent-peak and all-time-peak rank points, None when never ranked."""
    ranked_points_seen = [m.rank_points for m in usable_newest_first if m.rank_points > 0]
    if not ranked_points_seen:
        return None
    max_rp = max(ranked_points_seen)
    recent_peak_rp = max((m.rank_points for m in recent if m.rank_points > 0), default=max_rp)
    return CURRENT_FORM_RECENT_RP_WEIGHT * recent_peak_rp + (1 - CURRENT_FORM_RECENT_RP_WEIGHT) * max_rp


def compute_value_current_form(matches: List[UserFullMatchStats], now: datetime) -> Optional[PlayerValueResult]:
    """
    Algorithm 1: rank dollars of the effective rank points (blend of recent peak
    and all-time peak) multiplied by the recent shrunk K/D.
    """
    usable = _usable_matches_newest_first(matches)
    if not usable:
        return None
    recent = _select_recent_matches(usable, now)
    effective_rp = _compute_effective_rank_points(usable, recent)
    if effective_rp is None:
        return None

    kills = sum(m.kill_count for m in recent)
    deaths = sum(m.death_count for m in recent)
    kd_shrunk = (kills + KD_SHRINKAGE_PRIOR) / (deaths + KD_SHRINKAGE_PRIOR)

    value = min(max(rank_points_to_dollar(effective_rp) * kd_shrunk, VALUE_MIN), VALUE_MAX)
    return PlayerValueResult(
        value=value,
        rating=effective_rp,
        match_count=len(recent),
        last_match_timestamp=usable[0].match_timestamp,
    )


def compute_performance_metrics(matches: List[UserFullMatchStats], now: datetime) -> Optional[PerformanceMetrics]:
    """Extract the raw recent metrics of one user for the PERFORMANCE algorithm."""
    usable = _usable_matches_newest_first(matches)
    if not usable:
        return None
    recent = _select_recent_matches(usable, now)
    rounds = sum(m.round_played_count for m in recent)
    effective_rp = _compute_effective_rank_points(usable, recent)
    if rounds == 0 or effective_rp is None:
        return None

    kills = sum(m.kill_count for m in recent)
    deaths = sum(m.death_count for m in recent)
    first_kills = sum(m.first_kill_count for m in recent)
    first_deaths = sum(m.first_death_count for m in recent)
    clutch_wins = sum(m.clutches_win_count for m in recent)
    clutch_losses = sum(m.clutches_loss_count for m in recent)
    rounds_won = sum(m.round_won_count for m in recent)
    match_wins = sum(1 for m in recent if m.has_win)
    # Kills beyond the first in multi-kill rounds reward high-impact rounds
    extra_kills = sum(m.kill_2_count + 2 * m.kill_3_count + 3 * m.kill_4_count + 4 * m.kill_5_count for m in recent)

    return PerformanceMetrics(
        kills_per_round=kills / rounds,
        deaths_per_round=deaths / rounds,
        # Shrunk toward 0.5 so a few lucky duels do not dominate
        opening_duel_rate=(first_kills + 5) / (first_kills + first_deaths + 10),
        clutch_rate=(clutch_wins + 3) / (clutch_wins + clutch_losses + 6),
        round_win_rate=rounds_won / rounds,
        match_win_rate=match_wins / len(recent),
        multi_kill_per_round=extra_kills / rounds,
        effective_rank_points=effective_rp,
        match_count=len(recent),
        last_match_timestamp=usable[0].match_timestamp,
    )


def _select_peer_group(metrics: PerformanceMetrics, all_metrics: List[PerformanceMetrics]) -> List[PerformanceMetrics]:
    """Users at a similar rank, widening the rank-point window until enough peers exist."""
    for window in PERFORMANCE_PEER_RP_WINDOWS:
        peers = [
            peer for peer in all_metrics if abs(peer.effective_rank_points - metrics.effective_rank_points) <= window
        ]
        if len(peers) >= PERFORMANCE_MIN_PEERS:
            return peers
    return all_metrics


def _compute_composite_z_versus_peers(metrics: PerformanceMetrics, peers: List[PerformanceMetrics]) -> float:
    """Weighted z-score of the user's metrics against the peer distribution."""
    composite = 0.0
    for metric_name, weight in PERFORMANCE_WEIGHTS.items():
        series = [getattr(peer, metric_name) for peer in peers]
        std = statistics.pstdev(series) if len(series) > 1 else 0.0
        if std < 1e-9:
            continue
        z = (getattr(metrics, metric_name) - statistics.fmean(series)) / std
        if metric_name == "deaths_per_round":
            z = -z
        composite += weight * z
    return min(max(composite, -PERFORMANCE_Z_CLAMP), PERFORMANCE_Z_CLAMP)


def compute_values_performance(
    metrics_by_user: Dict[int, PerformanceMetrics],
) -> Dict[int, PlayerValueResult]:
    """
    Algorithm 2: the effective rank points set the base dollar value; the user's
    performance metrics z-scored against peers at a similar rank adjust it up or
    down, with small samples shrunk toward no adjustment.
    """
    all_metrics = list(metrics_by_user.values())
    results: Dict[int, PlayerValueResult] = {}
    for user_id, metrics in metrics_by_user.items():
        peers = _select_peer_group(metrics, all_metrics)
        composite = _compute_composite_z_versus_peers(metrics, peers)
        composite *= metrics.match_count / (metrics.match_count + PERFORMANCE_SHRINKAGE_MATCHES)
        base_value = rank_points_to_dollar(metrics.effective_rank_points)
        value = min(max(base_value * (1 + PERFORMANCE_Z_MULTIPLIER * composite), VALUE_MIN), VALUE_MAX)
        results[user_id] = PlayerValueResult(
            value=value,
            rating=composite,
            match_count=metrics.match_count,
            last_match_timestamp=metrics.last_match_timestamp,
        )
    return results


def compute_match_performance_score(match: UserFullMatchStats) -> float:
    """
    Per-round performance of one match on a 0-1 scale, 0.5 being the community
    average. Uses kills and deaths per round so volume matters: 12 kills over 9
    rounds scores far above 2 kills over 4 rounds despite a similar K/D ratio.
    """
    rounds = max(match.round_played_count, 1)
    kpr_z = (match.kill_count / rounds - ELO_EXPECTED_KILLS_PER_ROUND) / ELO_KILLS_PER_ROUND_STD
    dpr_z = (match.death_count / rounds - ELO_EXPECTED_DEATHS_PER_ROUND) / ELO_DEATHS_PER_ROUND_STD
    score = 1.0 / (1.0 + math.exp(-(ELO_PERF_KPR_WEIGHT * kpr_z - ELO_PERF_DPR_WEIGHT * dpr_z)))
    return min(max(score, 1.0 - ELO_PERF_SCORE_CLAMP), ELO_PERF_SCORE_CLAMP)


@dataclass
class PerformanceEloState:
    """Mutable state of the Elo replay over one user's chronological matches."""

    rating: float
    lobby_estimate: float = 0.0
    match_index: int = 0


def apply_performance_elo_match(state: PerformanceEloState, match: UserFullMatchStats) -> float:
    """
    Update the Elo state with one match and return the expected outcome that was
    used. The outcome blends the win/loss with the per-round performance score
    (a hard-carried loss is nearly neutral, a passenger win gains little).
    """
    if match.rank_points > 0:
        state.lobby_estimate = max(float(match.rank_points), state.lobby_estimate * ELO_LOBBY_DECAY_PER_MATCH)
    elif state.lobby_estimate > 0:
        state.lobby_estimate *= ELO_LOBBY_DECAY_PER_MATCH
    lobby_rp = state.lobby_estimate if state.lobby_estimate > 0 else state.rating

    rp_diff = min(max(lobby_rp - state.rating, -ELO_RP_DIFF_CLAMP), ELO_RP_DIFF_CLAMP)
    expected = 1.0 / (1.0 + 10.0 ** (rp_diff / 400.0))
    win = 1.0 if match.has_win else 0.0
    outcome = (1.0 - ELO_PERF_WEIGHT) * win + ELO_PERF_WEIGHT * compute_match_performance_score(match)
    if state.match_index < 50:
        k_factor = 40.0
    elif state.match_index < 150:
        k_factor = 24.0
    else:
        k_factor = 16.0
    if abs(match.points_gained) >= ELO_RESET_POINTS_GAINED_THRESHOLD:
        k_factor /= 2.0
    state.rating += k_factor * (outcome - expected)
    state.match_index += 1
    return expected


def compute_value_performance_elo(matches: List[UserFullMatchStats], now: datetime) -> Optional[PlayerValueResult]:
    """
    Algorithm 3: replay the full match history chronologically. Each match moves
    the rating by K * (outcome - expected), where the outcome blends win/loss with
    per-round performance and expected comes from the gap between the rating and
    the smoothed lobby strength. Idle players drift back toward the smoothed
    lobby estimate.
    """
    usable = _usable_matches_newest_first(matches)
    if not usable:
        return None
    chronological = list(reversed(usable))

    seed = next((float(m.rank_points) for m in chronological if m.rank_points > 0), ELO_DEFAULT_SEED)
    state = PerformanceEloState(rating=seed)
    for match in chronological:
        apply_performance_elo_match(state, match)
    rating = state.rating

    last_match = chronological[-1]
    idle_months = (now - last_match.match_timestamp).days / 30.0
    if idle_months > 1.0:
        baseline = state.lobby_estimate if state.lobby_estimate > 0 else rating
        decay = min(ELO_IDLE_DECAY_PER_MONTH * (idle_months - 1.0), ELO_IDLE_DECAY_MAX)
        rating += (baseline - rating) * decay

    value = min(max(rank_points_to_dollar(rating), VALUE_MIN), VALUE_MAX)
    return PlayerValueResult(
        value=value,
        rating=rating,
        match_count=len(chronological),
        last_match_timestamp=last_match.match_timestamp,
    )


def compute_value_time_decayed(matches: List[UserFullMatchStats], now: datetime) -> Optional[PlayerValueResult]:
    """
    Algorithm 4: rank dollars of the time-decayed peak rank points (a peak fades
    the older it is) multiplied by the exponentially recency-weighted K/D over the
    whole match history. Recent form dominates, but players with sparse recent
    data fall back on their (discounted) history instead of a tiny sample.
    """
    usable = _usable_matches_newest_first(matches)
    if not usable:
        return None
    decayed_peak = 0.0
    weighted_kills = 0.0
    weighted_deaths = 0.0
    for match in usable:
        age_days = max((now - match.match_timestamp).days, 0)
        if match.rank_points > 0:
            decayed_peak = max(decayed_peak, match.rank_points - TIME_DECAY_PEAK_FADE_RP_PER_DAY * age_days)
        weight = 0.5 ** (age_days / TIME_DECAY_KD_HALF_LIFE_DAYS)
        weighted_kills += weight * match.kill_count
        weighted_deaths += weight * match.death_count
    if decayed_peak <= 0:
        return None
    decayed_kd = (weighted_kills + TIME_DECAY_KD_PRIOR) / (weighted_deaths + TIME_DECAY_KD_PRIOR)

    value = min(max(rank_points_to_dollar(decayed_peak) * decayed_kd, VALUE_MIN), VALUE_MAX)
    return PlayerValueResult(
        value=value,
        rating=decayed_peak,
        match_count=len(usable),
        last_match_timestamp=usable[0].match_timestamp,
    )


def compute_all_player_values(
    matches_by_user: Dict[int, List[UserFullMatchStats]],
    now: Optional[datetime] = None,
    only_user_ids: Optional[List[int]] = None,
) -> Dict[int, Dict[PlayerValueAlgorithm, PlayerValueResult]]:
    """
    Compute every algorithm's value for the requested users. The PERFORMANCE
    community baseline always uses every user in matches_by_user, so pass the full
    community even when recomputing a subset (only_user_ids).
    """
    now = now or datetime.now(timezone.utc)
    target_ids = set(only_user_ids) if only_user_ids is not None else set(matches_by_user.keys())

    metrics_by_user: Dict[int, PerformanceMetrics] = {}
    for user_id, matches in matches_by_user.items():
        metrics = compute_performance_metrics(matches, now)
        if metrics is not None:
            metrics_by_user[user_id] = metrics
    performance_results = compute_values_performance(metrics_by_user)

    results: Dict[int, Dict[PlayerValueAlgorithm, PlayerValueResult]] = {}
    for user_id in target_ids:
        matches = matches_by_user.get(user_id, [])
        user_results: Dict[PlayerValueAlgorithm, PlayerValueResult] = {}
        current_form = compute_value_current_form(matches, now)
        if current_form is not None:
            user_results[PlayerValueAlgorithm.CURRENT_FORM] = current_form
        if user_id in performance_results:
            user_results[PlayerValueAlgorithm.PERFORMANCE] = performance_results[user_id]
        elo = compute_value_performance_elo(matches, now)
        if elo is not None:
            user_results[PlayerValueAlgorithm.PERFORMANCE_ELO] = elo
        time_decayed = compute_value_time_decayed(matches, now)
        if time_decayed is not None:
            user_results[PlayerValueAlgorithm.TIME_DECAYED] = time_decayed
        if user_results:
            results[user_id] = user_results
    return results


def compute_and_store_player_values(
    only_user_ids: Optional[List[int]] = None,
    now: Optional[datetime] = None,
) -> Dict[int, Dict[PlayerValueAlgorithm, PlayerValueResult]]:
    """
    Compute and persist every algorithm's value for the given users (all users
    with matches when None). The whole community's matches are always loaded
    because the PERFORMANCE algorithm normalizes against everyone.
    """
    now = now or datetime.now(timezone.utc)
    all_user_ids = data_access_fetch_all_user_ids_with_matches()
    matches_by_user = data_access_fetch_user_matches_in_time_range(all_user_ids, None, None)
    results = compute_all_player_values(matches_by_user, now, only_user_ids)
    for user_id, user_results in results.items():
        for algorithm, result in user_results.items():
            data_access_upsert_player_value(user_id, algorithm, result, now)
    print_log(f"compute_and_store_player_values: Stored values for {len(results)} users")
    return results
