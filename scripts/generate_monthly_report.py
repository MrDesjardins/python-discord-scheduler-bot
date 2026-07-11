#! /usr/bin/env python3
"""Generate the monthly analytics PDF report."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deps.monthly_report import generate_monthly_report


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate monthly analytics PDF report.")
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=None,
        help="Date used to choose the previous report month, formatted YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/monthly"),
        help="Base output directory. Defaults to reports/monthly.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of top active users to include per window. Defaults to 20.",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip AI conclusion generation.",
    )
    parser.add_argument(
        "--window",
        action="append",
        choices=["previous_month", "previous_three_months", "year_to_date", "all_data"],
        default=None,
        help="Limit generation to one report window. Can be passed multiple times. Defaults to all windows.",
    )
    return parser.parse_args()


def main() -> None:
    """Generate the report and print the output path."""
    args = parse_args()
    path = generate_monthly_report(
        reference_day=args.reference_date,
        output_dir=args.output_dir,
        top_n=args.top,
        include_ai=not args.no_ai,
        window_keys=args.window,
    )
    print(path)


if __name__ == "__main__":
    main()
