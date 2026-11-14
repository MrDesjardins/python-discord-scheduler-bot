"""Tests for the single-file HTML renderer."""

from datetime import date

from deps.reporting.data import build_report
from deps.reporting.html import render_report_html
from tests.reporting_helpers import create_reporting_db


def test_html_is_self_contained_and_escapes_names(tmp_path) -> None:
    db = create_reporting_db(tmp_path)
    report = build_report(db, date(2026, 11, 1), include_ai=False)
    html = render_report_html(report)

    assert html.startswith("<!DOCTYPE html>")
    assert 'href="#pulse"' in html
    assert 'id="pulse"' in html
    assert 'id="actions"' in html
    assert 'id="person-1"' in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    assert "http://" not in html
    assert "https://" not in html


def test_html_contains_action_copy_buttons(tmp_path) -> None:
    db = create_reporting_db(tmp_path)
    report = build_report(db, date(2026, 11, 1), include_ai=False)
    html = render_report_html(report)
    assert "copy-button" in html
    assert "Copy message" in html
