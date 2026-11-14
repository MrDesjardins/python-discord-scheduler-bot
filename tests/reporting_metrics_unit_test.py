"""Integration-style metrics test for the reporting data layer."""

from datetime import date

from deps.reporting.data import build_report
from tests.reporting_helpers import create_reporting_db


def test_october_report_metrics_from_fixture(tmp_path) -> None:
    db = create_reporting_db(tmp_path)
    report = build_report(db, date(2026, 11, 1), include_ai=False)
    window = report.primary

    assert report.report_month == "2026-10"
    assert window.voice_users == 3
    assert window.session_count == 4
    assert round(window.total_voice_hours, 1) == 6.0
    assert window.match_users == 3
    assert window.match_rows == 4
    assert window.distinct_matches == 3
    assert round(window.match_hours, 1) == 2.0
    assert window.in_rows == 2
    assert window.out_rows == 2
    assert round(window.in_percent, 1) == 50.0
    assert round(window.out_percent, 1) == 50.0
    assert window.peak_concurrent == 2
    assert window.messages == 1
    assert window.new_users == 4
    assert window.data_quality.stale_days == 22
    assert window.data_quality.voice_only_users == 1
    assert window.data_quality.match_only_users == 1

    alice = window.user(1)
    bob = window.user(2)
    carol = window.user(3)
    mallory = window.user(4)
    assert alice is not None and alice.in_rows == 1 and alice.out_rows == 1
    assert bob is not None and bob.in_rows == 1
    assert carol is not None and carol.out_rows == 1
    assert mallory is not None and mallory.classification == "voice_only"

    assert any(action.category == "reengage" and action.user_ids == (1,) for action in report.actions)
    assert any(action.category == "integrate" for action in report.actions)
    assert any(action.category == "data" for action in report.actions)
    assert len(report.actions) <= 30


def test_all_windows_are_built(tmp_path) -> None:
    db = create_reporting_db(tmp_path)
    report = build_report(db, date(2026, 11, 1), include_ai=False)
    keys = {window.window.key for window in report.windows}
    assert keys == {"previous_month", "previous_three_months", "year_to_date", "all_data", "last_28_days"}
