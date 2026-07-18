#!/usr/bin/env python3
"""
Generate one CSV per player-value algorithm to compare them side by side.

Usage:
    python3 player_value_report.py [--output-dir DIR] [--active-since YYYY-MM-DD]

Reads the configured database (user_activity.db), computes the team-balancing
values for every user with a match since --active-since (default 2026-01-01),
and writes:
    player_values_algo1_current_form.csv
    player_values_algo2_performance.csv
    player_values_algo3_elo.csv
    player_values_algo4_time_decayed.csv
"""

import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from deps.analytic_activity_data_access import fetch_user_info_by_user_id_list
from deps.analytic_match_data_access import data_access_fetch_user_matches_in_time_range
from deps.analytic_player_value_data_access import data_access_fetch_all_user_ids_with_matches
from deps.analytic_player_value_functions import compute_all_player_values
from deps.data_access_data_class import UserInfo
from deps.models import PlayerValueAlgorithm, UserFullMatchStats

DEFAULT_ACTIVE_SINCE = "2026-01-01"

CSV_FILE_NAMES = {
    PlayerValueAlgorithm.CURRENT_FORM: "player_values_algo1_current_form.csv",
    PlayerValueAlgorithm.PERFORMANCE: "player_values_algo2_performance.csv",
    PlayerValueAlgorithm.PERFORMANCE_ELO: "player_values_algo3_elo.csv",
    PlayerValueAlgorithm.TIME_DECAYED: "player_values_algo4_time_decayed.csv",
}
RATING_COLUMN_NAMES = {
    PlayerValueAlgorithm.CURRENT_FORM: "effective_rank_points",
    PlayerValueAlgorithm.PERFORMANCE: "composite_z_score",
    PlayerValueAlgorithm.PERFORMANCE_ELO: "elo_rating",
    PlayerValueAlgorithm.TIME_DECAYED: "decayed_peak_rank_points",
}


def main() -> None:
    """Compute the values for every recently active user and write one CSV per algorithm."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=".", help="Directory for the CSV files")
    parser.add_argument(
        "--active-since",
        default=DEFAULT_ACTIVE_SINCE,
        help="Only include users with at least one match on/after this date (YYYY-MM-DD)",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    active_since = datetime.fromisoformat(args.active_since).replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)

    user_ids = data_access_fetch_all_user_ids_with_matches()
    all_matches: Dict[int, List[UserFullMatchStats]] = data_access_fetch_user_matches_in_time_range(
        user_ids, None, None
    )
    # Too-inactive users are excluded entirely, including from the community
    # baselines the PERFORMANCE algorithm normalizes against.
    matches_by_user = {
        user_id: matches
        for user_id, matches in all_matches.items()
        if max(m.match_timestamp for m in matches) >= active_since
    }
    users_info: List[Optional[UserInfo]] = fetch_user_info_by_user_id_list(user_ids)
    user_info_by_id = {user.id: user for user in users_info if user is not None}
    results = compute_all_player_values(matches_by_user, now)

    for algorithm, file_name in CSV_FILE_NAMES.items():
        rows: List[Dict[str, object]] = []
        for user_id, user_results in results.items():
            if algorithm not in user_results:
                continue
            result = user_results[algorithm]
            matches = matches_by_user.get(user_id, [])
            user_info = user_info_by_id.get(user_id)
            latest_rp = next((m.rank_points for m in sorted(matches, key=lambda m: m.match_timestamp, reverse=True)), 0)
            max_rp = max((m.rank_points for m in matches), default=0)
            days_since_last = (
                (now - result.last_match_timestamp).days if result.last_match_timestamp is not None else None
            )
            rows.append(
                {
                    "display_name": user_info.display_name if user_info else str(user_id),
                    "ubisoft_username": (user_info.ubisoft_username_active or "") if user_info else "",
                    "value": round(result.value, 1),
                    RATING_COLUMN_NAMES[algorithm]: round(result.rating, 2),
                    "matches_used": result.match_count,
                    "matches_total": len(matches),
                    "current_rank_points": latest_rp,
                    "max_rank_points": max_rp,
                    "days_since_last_match": days_since_last,
                }
            )
        rows.sort(key=lambda row: float(str(row["value"])), reverse=True)

        file_path = output_dir / file_name
        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {len(rows)} users to {file_path}")


if __name__ == "__main__":
    main()
