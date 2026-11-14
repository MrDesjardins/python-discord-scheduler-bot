#! /usr/bin/env python3
"""Generate the single-file HTML analytics report."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deps.reporting.data import build_report  # noqa: E402
from deps.reporting.html import render_report_html  # noqa: E402


def _next_month_start(month: str) -> date:
    year_str, month_str = month.split("-", 1)
    year = int(year_str)
    month_number = int(month_str)
    if month_number == 12:
        return date(year + 1, 1, 1)
    return date(year, month_number + 1, 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the GameTime analytics HTML report.")
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=None,
        help="Date used to choose the previous report month, formatted YYYY-MM-DD. Defaults to today.",
    )
    parser.add_argument(
        "--report-month",
        type=str,
        default=None,
        help="Pin the report month directly, formatted YYYY-MM. Derives the reference date.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=Path("user_activity.db"),
        help="SQLite database path. Defaults to user_activity.db.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/monthly"),
        help="Base output directory. Defaults to reports/monthly.",
    )
    parser.add_argument(
        "--window",
        action="append",
        choices=["previous_month", "previous_three_months", "year_to_date", "all_data", "last_28_days"],
        default=None,
        help="Limit generation to specific windows. Can be passed multiple times.",
    )
    parser.add_argument("--no-ai", action="store_true", help="Skip the grounded AI narrative.")
    parser.add_argument("--open", action="store_true", help="Open the generated HTML in the default browser.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reference_date = args.reference_date
    if args.report_month:
        reference_date = _next_month_start(args.report_month)
    if reference_date is None:
        reference_date = date.today()
    report = build_report(
        database_path=args.database,
        reference_date=reference_date,
        include_ai=not args.no_ai,
        window_keys=args.window,
    )
    output_base = args.output_dir / report.report_month
    output_base.mkdir(parents=True, exist_ok=True)
    output_path = output_base / f"gametime_report_{report.report_month}.html"
    output_path.write_text(render_report_html(report), encoding="utf-8")
    print(output_path)
    if args.open:
        webbrowser.open(output_path.resolve().as_uri())


if __name__ == "__main__":
    main()
