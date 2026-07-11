"""Unit tests for monthly analytics report helpers."""

from datetime import date

import pytest

from deps.data_access import (
    data_access_get_analytics_report_text_channel_id,
    data_access_get_monthly_analytics_report_sent,
    data_access_set_analytics_report_text_channel_id,
    data_access_set_monthly_analytics_report_sent,
)
from deps.monthly_report import get_monthly_report_windows
from deps.monthly_report import UserWindowMetrics, collect_monthly_report_data, render_monthly_report_pdf
from deps.monthly_report_style import TOC_ROWS_PER_PAGE, TocEntry, toc_page_count
from deps.system_database import DATABASE_NAME, DATABASE_NAME_TEST, database_manager


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Setup and teardown for cache-backed report tests."""
    database_manager.set_database_name(DATABASE_NAME_TEST)
    database_manager.drop_all_tables()
    database_manager.init_database()
    yield
    database_manager.set_database_name(DATABASE_NAME)


def test_monthly_report_windows_for_regular_month():
    """The report on July 1 covers June as the previous complete month."""
    report_month, windows = get_monthly_report_windows(date(2026, 7, 1))

    assert report_month == "2026-06"
    assert windows[0].start.date() == date(2026, 6, 1)
    assert windows[0].end_exclusive.date() == date(2026, 7, 1)
    assert windows[1].start.date() == date(2026, 4, 1)
    assert windows[2].start.date() == date(2026, 1, 1)


def test_monthly_report_windows_for_january_boundary():
    """The January 1 report covers December and uses the prior year for YTD."""
    report_month, windows = get_monthly_report_windows(date(2026, 1, 1))

    assert report_month == "2025-12"
    assert windows[0].start.date() == date(2025, 12, 1)
    assert windows[0].end_exclusive.date() == date(2026, 1, 1)
    assert windows[1].start.date() == date(2025, 10, 1)
    assert windows[2].start.date() == date(2025, 1, 1)


def test_user_window_metric_percentages_use_classified_ranked_rows():
    """User ranked percentages are based on classified in/out rows."""
    user = UserWindowMetrics(
        user_id=1,
        display_name="User",
        voice_hours=12.5,
        ranked_matches=20,
        in_server_matches=3,
        outside_server_matches=7,
        outside_partners=[("Partner", 2, 2, 100.0)],
    )

    assert user.classified_ranked_matches == 10
    assert user.in_server_percent == 30.0
    assert user.outside_server_percent == 70.0
    assert user.outside_partner_match_count == 2


def test_collect_monthly_report_data_can_filter_windows():
    """Manual report generation can focus on one range without changing defaults."""
    report = collect_monthly_report_data(date(2026, 7, 1), top_n=5, window_keys=["previous_month"])

    assert report.report_month == "2026-06"
    assert [data.window.key for data in report.windows] == ["previous_month"]


def test_render_monthly_report_pdf_smoke(tmp_path):
    """Rendering succeeds without AI or production data."""
    report = collect_monthly_report_data(date(2026, 7, 1), top_n=3, window_keys=["previous_month"])

    output_path = render_monthly_report_pdf(report, "AI conclusion disabled for this test.", tmp_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_render_monthly_report_pdf_multi_window_smoke(tmp_path):
    """Rendering with several windows produces the section dividers without failing."""
    report = collect_monthly_report_data(date(2026, 7, 1), top_n=2, window_keys=["previous_month", "year_to_date"])

    output_path = render_monthly_report_pdf(report, "AI conclusion disabled for this test.", tmp_path)

    assert output_path.exists()
    assert output_path.stat().st_size > 0


def test_toc_page_count_uses_rows_per_page():
    """TOC pagination is one page minimum and grows with the row capacity."""
    assert toc_page_count(0) == 1
    assert toc_page_count(TOC_ROWS_PER_PAGE) == 1
    assert toc_page_count(TOC_ROWS_PER_PAGE + 1) == 2


def test_toc_entry_shift_preserves_title_and_level():
    """Shifting a TOC entry by the front-matter offset only moves its page number."""
    entry = TocEntry(title="Executive Summary", level=0, page_number=3)

    shifted = entry.shifted(4)

    assert shifted.page_number == 7
    assert shifted.title == "Executive Summary"
    assert shifted.level == 0


@pytest.mark.asyncio
async def test_analytics_report_channel_accessors():
    """The analytics report channel is persisted through the normal cache table."""
    assert await data_access_get_analytics_report_text_channel_id(123) is None

    data_access_set_analytics_report_text_channel_id(123, 456)

    assert await data_access_get_analytics_report_text_channel_id(123) == 456


@pytest.mark.asyncio
async def test_monthly_report_sent_guard_accessors():
    """The report sent guard is keyed by guild and report month."""
    assert await data_access_get_monthly_analytics_report_sent(123, "2026-06") is False

    data_access_set_monthly_analytics_report_sent(123, "2026-06")

    assert await data_access_get_monthly_analytics_report_sent(123, "2026-06") is True
    assert await data_access_get_monthly_analytics_report_sent(123, "2026-05") is False
