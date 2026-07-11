"""Visual theme and page chrome for the monthly analytics PDF report.

All colors, page geometry, and reusable drawing helpers (cover page, section
dividers, table of contents, styled tables and axes) live here so that
deps/monthly_report.py only deals with report content.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402
from matplotlib.colorbar import Colorbar  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.table import Table  # noqa: E402

PAGE_WIDTH_INCHES = 11.0
PAGE_HEIGHT_INCHES = 8.5

# Brand chrome colors (navy + orange theme).
COLOR_NAVY = "#0F1B2D"
COLOR_NAVY_LIGHT = "#1E3A5F"
COLOR_ORANGE = "#F18F01"
COLOR_TEXT = "#1F2937"
COLOR_MUTED = "#6B7280"
COLOR_FAINT = "#9CA3AF"
COLOR_ON_NAVY_MUTED = "#9FB3C8"
COLOR_ROW_ALT = "#F4F6F8"
COLOR_GRID = "#E1E0D9"
COLOR_AXIS = "#C3C2B7"
COLOR_HAIRLINE = "#E5E7EB"

# Validated categorical palette (fixed order, never cycled).
CHART_PALETTE = ["#2A78D6", "#1BAF7A", "#EDA100", "#008300", "#4A3AA7", "#E34948", "#E87BA4", "#EB6834"]
COLOR_SERIES_PRIMARY = CHART_PALETTE[0]
COLOR_IN_SERVER = "#1BAF7A"
COLOR_OUTSIDE = "#E34948"
COLOR_NETWORK_EDGE = "#9CA3AF"

# Single-hue sequential ramp for magnitude encodings (heatmaps).
SEQUENTIAL_CMAP = LinearSegmentedColormap.from_list(
    "report_blues", ["#CDE2FB", "#86B6EF", "#3987E5", "#256ABF", "#0D366B"]
)

HEADER_BAND_BOTTOM = 0.925
HEADER_RULE_HEIGHT = 0.006
FOOTER_LINE_Y = 0.062
CONTENT_RECT = (0.08, 0.12, 0.86, 0.74)
# Taller bottom margin for charts with rotated x tick labels, so the axis label clears the footer.
CONTENT_RECT_ROTATED_XLABELS = (0.08, 0.18, 0.86, 0.68)
TEXT_PAGE_TOP_Y = 0.87
TOC_ROWS_PER_PAGE = 22


@dataclass(frozen=True)
class TocEntry:
    """One table-of-contents row pointing at a rendered page."""

    title: str
    level: int
    page_number: int

    def shifted(self, offset: int) -> "TocEntry":
        """Return a copy pointing `offset` pages later (for cover/TOC front matter)."""
        return replace(self, page_number=self.page_number + offset)


def toc_page_count(entry_count: int) -> int:
    """Number of TOC pages needed for the given entry count."""
    return max(1, math.ceil(entry_count / TOC_ROWS_PER_PAGE))


def new_page_figure(facecolor: str = "white") -> Figure:
    """Create a fixed-size report page figure (never saved with a tight bounding box)."""
    return plt.figure(figsize=(PAGE_WIDTH_INCHES, PAGE_HEIGHT_INCHES), facecolor=facecolor)


def content_axes(fig: Figure, rect: Optional[tuple[float, float, float, float]] = None) -> Axes:
    """Add the main content axes inside the header/footer chrome."""
    return fig.add_axes(rect or CONTENT_RECT)


def blank_axes(fig: Figure, rect: Optional[tuple[float, float, float, float]] = None) -> Axes:
    """Add invisible content axes for free-form text pages."""
    ax = content_axes(fig, rect)
    ax.axis("off")
    return ax


def _figure_rect(fig: Figure, x: float, y: float, width: float, height: float, color: str) -> None:
    fig.add_artist(Rectangle((x, y), width, height, transform=fig.transFigure, facecolor=color, edgecolor="none"))


def apply_page_chrome(
    fig: Figure,
    *,
    page_title: str,
    section_title: str,
    page_number: int,
    report_month: str,
    total_pages: Optional[int] = None,
    subtitle: str = "",
) -> None:
    """Draw the navy header band, orange rule, and footer on a content page."""
    _figure_rect(fig, 0.0, HEADER_BAND_BOTTOM, 1.0, 1.0 - HEADER_BAND_BOTTOM, COLOR_NAVY)
    _figure_rect(fig, 0.0, HEADER_BAND_BOTTOM - HEADER_RULE_HEIGHT, 1.0, HEADER_RULE_HEIGHT, COLOR_ORANGE)
    band_center_y = HEADER_BAND_BOTTOM + (1.0 - HEADER_BAND_BOTTOM) / 2
    fig.text(0.045, band_center_y, page_title, color="white", fontsize=14, fontweight="bold", va="center")
    if section_title:
        fig.text(0.955, band_center_y, section_title.upper(), color=COLOR_ORANGE, fontsize=8.5, va="center", ha="right")
    if subtitle:
        fig.text(0.955, HEADER_BAND_BOTTOM - 0.018, subtitle, color=COLOR_MUTED, fontsize=7.5, va="top", ha="right")
    _figure_rect(fig, 0.045, FOOTER_LINE_Y, 0.91, 0.0015, COLOR_AXIS)
    fig.text(0.045, 0.042, f"GAMETIME ANALYTICS — {report_month}", color=COLOR_MUTED, fontsize=7, va="center")
    page_label = f"PAGE {page_number}" if total_pages is None else f"PAGE {page_number} / {total_pages}"
    fig.text(0.955, 0.042, page_label, color=COLOR_MUTED, fontsize=7, va="center", ha="right")


def draw_stat_cards(
    fig: Figure,
    cards: Sequence[tuple[str, str]],
    *,
    y: float,
    height: float = 0.13,
    x_start: float = 0.045,
    x_end: float = 0.955,
    dark: bool = False,
) -> None:
    """Draw a row of rounded stat cards; each card is a (value, label) pair."""
    if not cards:
        return
    gap = 0.018
    card_width = (x_end - x_start - gap * (len(cards) - 1)) / len(cards)
    face = COLOR_NAVY_LIGHT if dark else "white"
    value_color = "white" if dark else COLOR_NAVY
    label_color = COLOR_ON_NAVY_MUTED if dark else COLOR_MUTED
    for index, (value, label) in enumerate(cards):
        x = x_start + index * (card_width + gap)
        fig.add_artist(
            FancyBboxPatch(
                (x, y),
                card_width,
                height,
                boxstyle="round,pad=0,rounding_size=0.012",
                transform=fig.transFigure,
                facecolor=face,
                edgecolor="none" if dark else COLOR_HAIRLINE,
                linewidth=0.8,
            )
        )
        _figure_rect(fig, x + 0.012, y + height - 0.012, card_width - 0.024, 0.004, COLOR_ORANGE)
        fig.text(x + 0.012, y + height * 0.52, value, color=value_color, fontsize=17, fontweight="bold", va="center")
        fig.text(x + 0.012, y + 0.022, label.upper(), color=label_color, fontsize=6.5, va="center")


def draw_cover_page(
    *,
    month_display: str,
    report_month: str,
    generated_display: str,
    stats: Sequence[tuple[str, str]],
) -> Figure:
    """Build the full-bleed navy cover page."""
    fig = new_page_figure(facecolor=COLOR_NAVY)
    _figure_rect(fig, 0.0, 0.0, 1.0, 1.0, COLOR_NAVY)
    _figure_rect(fig, 0.0, 0.965, 1.0, 0.035, COLOR_NAVY_LIGHT)
    fig.text(
        0.045,
        0.9825,
        "R A I N B O W   S I X   S I E G E   C O M M U N I T Y",
        color=COLOR_ON_NAVY_MUTED,
        fontsize=7,
        va="center",
    )
    _figure_rect(fig, 0.045, 0.56, 0.007, 0.27, COLOR_ORANGE)
    fig.text(0.075, 0.80, "GAMETIME", color=COLOR_ORANGE, fontsize=16, fontweight="bold", va="center")
    fig.text(0.075, 0.71, "Monthly Analytics Report", color="white", fontsize=34, fontweight="bold", va="center")
    fig.text(0.075, 0.615, month_display, color=COLOR_ORANGE, fontsize=21, fontweight="bold", va="center")
    fig.text(0.075, 0.53, f"Generated {generated_display}", color=COLOR_ON_NAVY_MUTED, fontsize=8.5, va="center")
    fig.text(0.075, 0.435, "PREVIOUS MONTH AT A GLANCE", color=COLOR_ON_NAVY_MUTED, fontsize=8, va="center")
    draw_stat_cards(fig, stats, y=0.27, height=0.14, x_start=0.075, x_end=0.925, dark=True)
    _figure_rect(fig, 0.045, 0.085, 0.91, 0.0015, COLOR_NAVY_LIGHT)
    fig.text(
        0.045,
        0.06,
        "Voice activity · Ranked match tracking · Community relationships",
        color=COLOR_ON_NAVY_MUTED,
        fontsize=7.5,
        va="center",
    )
    fig.text(0.955, 0.06, report_month, color=COLOR_ON_NAVY_MUTED, fontsize=7.5, va="center", ha="right")
    return fig


def draw_section_divider(
    *,
    section_number: int,
    title: str,
    date_range: str,
    bullets: Sequence[str],
) -> Figure:
    """Build a full-bleed navy divider page introducing one report window."""
    fig = new_page_figure(facecolor=COLOR_NAVY)
    _figure_rect(fig, 0.0, 0.0, 1.0, 1.0, COLOR_NAVY)
    _figure_rect(fig, 0.0, 0.0, 0.012, 1.0, COLOR_ORANGE)
    fig.text(
        0.075,
        0.76,
        f"{section_number:02d}",
        color=COLOR_ORANGE,
        fontsize=88,
        fontweight="bold",
        va="center",
        alpha=0.95,
    )
    fig.text(0.075, 0.575, title, color="white", fontsize=30, fontweight="bold", va="center")
    fig.text(0.075, 0.505, date_range, color=COLOR_ON_NAVY_MUTED, fontsize=10.5, va="center")
    _figure_rect(fig, 0.075, 0.455, 0.10, 0.004, COLOR_ORANGE)
    fig.text(0.075, 0.395, "IN THIS SECTION", color=COLOR_ON_NAVY_MUTED, fontsize=8, va="center")
    y = 0.35
    for bullet in bullets:
        _figure_rect(fig, 0.075, y - 0.006, 0.008, 0.012, COLOR_ORANGE)
        fig.text(0.095, y, bullet, color="white", fontsize=9.5, va="center")
        y -= 0.042
    return fig


def draw_toc_entries(fig: Figure, entries: Sequence[TocEntry]) -> None:
    """Draw TOC rows with dotted leaders and right-aligned page numbers."""
    renderer = fig.canvas.get_renderer()  # type: ignore[attr-defined]
    inverse_figure = fig.transFigure.inverted()
    number_x = 0.945
    y = TEXT_PAGE_TOP_Y
    for entry in entries:
        top_level = entry.level == 0
        if top_level and y < TEXT_PAGE_TOP_Y:
            y -= 0.010
        title_x = 0.055 if top_level else 0.085
        color = COLOR_NAVY if top_level else COLOR_TEXT
        weight = "bold" if top_level else "normal"
        size = 10.5 if top_level else 9.0
        text = fig.text(title_x, y, entry.title, color=color, fontsize=size, fontweight=weight, va="center")
        fig.text(
            number_x + 0.010,
            y,
            str(entry.page_number),
            color=color,
            fontsize=size,
            fontweight=weight,
            va="center",
            ha="right",
        )
        title_end_x = inverse_figure.transform(text.get_window_extent(renderer))[1][0]
        leader_start = min(title_end_x + 0.012, number_x - 0.06)
        fig.add_artist(
            Line2D(
                [leader_start, number_x - 0.045],
                [y, y],
                transform=fig.transFigure,
                color=COLOR_FAINT,
                linewidth=0.8,
                linestyle=(0, (1, 3)),
            )
        )
        y -= 0.033


def style_table(ax: Axes, columns: Sequence[str], rows: Sequence[Sequence[object]]) -> Table:
    """Render a styled table: navy header, alternating row fill, horizontal hairlines only."""
    ax.axis("off")
    table = ax.table(
        cellText=[[str(value) for value in row] for row in rows],
        colLabels=list(columns),
        loc="upper center",
        cellLoc="left",
        colLoc="left",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.5)
    table.scale(1, 1.45)
    for (row_index, _), cell in table.get_celld().items():
        cell.PAD = 0.02
        if row_index == 0:
            cell.set_facecolor(COLOR_NAVY)
            cell.set_edgecolor(COLOR_NAVY)
            cell.set_linewidth(0.5)
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor(COLOR_ROW_ALT if row_index % 2 == 0 else "white")
            cell.set_edgecolor(COLOR_HAIRLINE)
            cell.set_linewidth(0.5)
            cell.visible_edges = "B"
            cell.set_text_props(color=COLOR_TEXT)
    return table


def style_axes(ax: Axes, grid_axis: Optional[Literal["x", "y", "both"]] = "x") -> None:
    """Apply the report chart style: open spines, dotted grid, muted ticks."""
    ax.set_facecolor("white")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(COLOR_AXIS)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=COLOR_MUTED, labelsize=8, length=0)
    if grid_axis is not None:
        ax.grid(axis=grid_axis, color=COLOR_GRID, linewidth=0.7, linestyle=(0, (1, 3)))
        ax.set_axisbelow(True)
    ax.xaxis.label.set_color(COLOR_MUTED)
    ax.xaxis.label.set_fontsize(8.5)
    ax.yaxis.label.set_color(COLOR_MUTED)
    ax.yaxis.label.set_fontsize(8.5)


def style_colorbar(colorbar: Colorbar, label: str) -> None:
    """Apply muted styling to a heatmap colorbar."""
    colorbar.ax.tick_params(colors=COLOR_MUTED, labelsize=7, length=0)
    colorbar.set_label(label, color=COLOR_MUTED, fontsize=8.5)
    colorbar.outline.set_visible(False)  # type: ignore[operator]  # stub maps Spines.__getattr__ to Spine


def label_bar_values(ax: Axes, positions: Sequence[float], values: Sequence[float], fmt: str = "{:.0f}") -> None:
    """Write muted value labels just past the end of horizontal bars."""
    for position, value in zip(positions, values):
        ax.annotate(
            fmt.format(value),
            xy=(value, position),
            xytext=(3, 0),
            textcoords="offset points",
            va="center",
            fontsize=6.5,
            color=COLOR_MUTED,
        )


def draw_empty_message(ax: Axes, message: str = "No data available for this section.") -> None:
    """Show a muted placeholder message on a page without data."""
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=11, color=COLOR_MUTED, style="italic")
