"""Reusable analytics report generation for the GameTime community."""

from deps.reporting.data import build_report
from deps.reporting.html import render_report_html

__all__ = ["build_report", "render_report_html"]
