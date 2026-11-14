"""Small inline-SVG chart primitives for the single-file HTML report."""

from __future__ import annotations

import html
import math
from typing import Any, Iterable, Optional, Sequence

from deps.reporting.models import NetworkEdge, NetworkNode

NAVY = "#0F1B2D"
ORANGE = "#F18F01"
GREEN = "#1BAF7A"
RED = "#E34948"
BLUE = "#2A78D6"
MUTED = "#6B7280"
GRID = "#E5E7EB"
INK = "#1F2937"
PALE = "#F4F6F8"
PALETTE = ("#2A78D6", "#1BAF7A", "#EDA100", "#008300", "#4A3AA7", "#E34948", "#E87BA4", "#EB6834")


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt(value: float, digits: int = 0) -> str:
    if digits:
        return f"{value:,.{digits}f}"
    return f"{value:,.0f}"


def _svg(content: str, width: int, height: int, label: str) -> str:
    return (
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_esc(label)}" '
        f'preserveAspectRatio="xMidYMid meet">{content}</svg>'
    )


def bar_chart(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    color: str = BLUE,
    title: str = "",
    digits: int = 1,
    width: int = 760,
    height: int = 280,
    max_labels: int = 24,
) -> str:
    if not values:
        return '<p class="empty">No data for this chart.</p>'
    labels = list(labels)
    values = list(values)
    if len(values) > max_labels:
        order = sorted(range(len(values)), key=lambda i: -values[i])[:max_labels]
        labels = [labels[i] for i in order]
        values = [values[i] for i in order]
    left, right, top, bottom = 56, 18, 26, 92
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_value = max(values) or 1.0
    slot = plot_w / max(1, len(values))
    bar_w = max(6.0, slot * 0.62)
    parts = [f'<text x="{left}" y="18" class="chart-title">{_esc(title)}</text>']
    for tick in range(4):
        value = max_value * tick / 3
        y = top + plot_h - (value / max_value) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(
            f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" class="axis">{_fmt(value, digits)}</text>'
        )
    for index, (label, value) in enumerate(zip(labels, values)):
        x = left + index * slot + (slot - bar_w) / 2
        bar_h = (value / max_value) * plot_h
        y = top + plot_h - bar_h
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" rx="3" fill="{color}" '
            f'opacity="0.9"><title>{_esc(label)}: {_fmt(value, digits)}</title></rect>'
        )
        if len(values) <= 16:
            parts.append(
                f'<text x="{x + bar_w / 2:.1f}" y="{y - 5:.1f}" text-anchor="middle" class="value">{_fmt(value, digits)}</text>'
            )
        text = label if len(label) <= 18 else label[:16] + "..."
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 14}" text-anchor="end" class="axis" '
            f'transform="rotate(-40 {x + bar_w / 2:.1f} {top + plot_h + 14})">{_esc(text)}</text>'
        )
    return _svg("".join(parts), width, height, title)


def horizontal_bar_chart(
    labels: Sequence[str],
    values: Sequence[float],
    *,
    color: str = GREEN,
    title: str = "",
    digits: int = 1,
    width: int = 760,
    height: Optional[int] = None,
    max_rows: int = 20,
) -> str:
    if not values:
        return '<p class="empty">No data for this chart.</p>'
    rows = list(zip(labels, values))[:max_rows]
    labels = [row[0] for row in rows]
    values = [row[1] for row in rows]
    if height is None:
        height = 54 + len(rows) * 26
    left, right, top, bottom = 180, 70, 30, 20
    plot_w = width - left - right
    max_value = max(values) or 1.0
    parts = [f'<text x="0" y="18" class="chart-title">{_esc(title)}</text>']
    for index, (label, value) in enumerate(zip(labels, values)):
        y = top + index * 26
        bar_w = (value / max_value) * plot_w
        parts.append(f'<text x="{left - 10}" y="{y + 14}" text-anchor="end" class="axis">{_esc(label)}</text>')
        parts.append(
            f'<rect x="{left}" y="{y + 3}" width="{bar_w:.1f}" height="16" rx="3" fill="{color}" opacity="0.9">'
            f"<title>{_esc(label)}: {_fmt(value, digits)}</title></rect>"
        )
        parts.append(f'<text x="{left + bar_w + 8:.1f}" y="{y + 15}" class="value">{_fmt(value, digits)}</text>')
    return _svg("".join(parts), width, height, title)


def line_chart(
    series: Sequence[tuple[str, Sequence[tuple[object, float]]]],
    *,
    title: str = "",
    digits: int = 1,
    width: int = 760,
    height: int = 300,
    y_label: str = "",
) -> str:
    all_points = [point for _, points in series for point in points]
    if not all_points:
        return '<p class="empty">No data for this chart.</p>'
    left, right, top, bottom = 56, 18, 28, 54
    plot_w = width - left - right
    plot_h = height - top - bottom
    xs = [i for i, _ in enumerate(all_points)]
    ys = [value for _, value in all_points]
    max_value = max(ys) or 1.0
    count = max(len(points) for _, points in series)
    parts = [f'<text x="{left}" y="18" class="chart-title">{_esc(title)}</text>']
    for tick in range(4):
        value = max_value * tick / 3
        y = top + plot_h - (value / max_value) * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(
            f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" class="axis">{_fmt(value, digits)}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="12" y="{top + plot_h / 2}" transform="rotate(-90 12 {top + plot_h / 2})" class="axis">{_esc(y_label)}</text>'
        )
    for series_index, (label, points) in enumerate(series):
        color = PALETTE[series_index % len(PALETTE)]
        coords: list[str] = []
        for index, (_, value) in enumerate(points):
            x = left + (index / max(1, count - 1)) * plot_w
            y = top + plot_h - (value / max_value) * plot_h
            coords.append(f"{x:.1f},{y:.1f}")
        if len(coords) > 1:
            parts.append(
                f'<polyline points="{" ".join(coords)}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round"/>'
            )
        for index, ((point_label, value), coord) in enumerate(zip(points, coords)):
            cx, cy = coord.split(",")
            parts.append(
                f'<circle cx="{cx}" cy="{cy}" r="3" fill="{color}"><title>{_esc(label)} {_esc(point_label)}: {_fmt(value, digits)}</title></circle>'
            )
        parts.append(
            f'<text x="{left + series_index * 150}" y="{height - 8}" class="legend" fill="{color}">{_esc(label)}</text>'
        )
    for index in range(0, count, max(1, count // 8)):
        tick_label = str(series[0][1][index][0]) if index < len(series[0][1]) else ""
        x = left + (index / max(1, count - 1)) * plot_w
        parts.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle" class="axis">{_esc(tick_label)}</text>'
        )
    return _svg("".join(parts), width, height, title)


def _blend(start: str, end: str, ratio: float) -> str:
    ratio = max(0.0, min(1.0, ratio))
    a = tuple(int(start[i : i + 2], 16) for i in (1, 3, 5))
    b = tuple(int(end[i : i + 2], 16) for i in (1, 3, 5))
    return "#" + "".join(f"{round(a[i] + (b[i] - a[i]) * ratio):02x}" for i in range(3))


def heatmap(
    values: dict[tuple[int, int], float],
    row_labels: Sequence[str],
    col_labels: Sequence[str],
    *,
    title: str = "",
    width: int = 760,
    height: int = 360,
    digits: int = 1,
    unit: str = "",
) -> str:
    if not values:
        return '<p class="empty">No data for this chart.</p>'
    left, right, top, bottom = 56, 16, 30, 44
    plot_w = width - left - right
    plot_h = height - top - bottom
    cell_w = plot_w / len(col_labels)
    cell_h = plot_h / len(row_labels)
    max_value = max(values.values()) or 1.0
    parts = [f'<text x="0" y="18" class="chart-title">{_esc(title)}</text>']
    for row_index, row in enumerate(row_labels):
        parts.append(
            f'<text x="{left - 8}" y="{top + row_index * cell_h + cell_h / 2 + 4:.1f}" text-anchor="end" class="axis">{_esc(row)}</text>'
        )
        for col_index, col in enumerate(col_labels):
            value = values.get((row_index, col_index), 0.0)
            color = _blend("#EAF2FB", NAVY, value / max_value)
            x = left + col_index * cell_w
            y = top + row_index * cell_h
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w + 0.4:.1f}" height="{cell_h + 0.4:.1f}" fill="{color}">'
                f"<title>{_esc(row)} {_esc(col)}: {_fmt(value, digits)}{_esc(unit)}</title></rect>"
            )
    for col_index, col in enumerate(col_labels):
        if col_index % 2 == 0:
            x = left + col_index * cell_w + cell_w / 2
            parts.append(
                f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle" class="axis">{_esc(col)}</text>'
            )
    return _svg("".join(parts), width, height, title)


def scatter(
    points: Sequence[tuple[float, float, str, str]],
    *,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    width: int = 760,
    height: int = 360,
) -> str:
    if not points:
        return '<p class="empty">No data for this chart.</p>'
    left, right, top, bottom = 60, 22, 30, 54
    plot_w = width - left - right
    plot_h = height - top - bottom
    max_x = max(point[0] for point in points) or 1.0
    max_y = max(point[1] for point in points) or 1.0
    parts = [f'<text x="{left}" y="18" class="chart-title">{_esc(title)}</text>']
    for tick in range(4):
        x = left + plot_w * tick / 3
        y = top + plot_h - plot_h * tick / 3
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width - right}" y2="{y:.1f}" stroke="{GRID}"/>')
        parts.append(
            f'<text x="{left - 8}" y="{y + 3:.1f}" text-anchor="end" class="axis">{_fmt(max_y * tick / 3)}</text>'
        )
        parts.append(
            f'<text x="{x:.1f}" y="{top + plot_h + 16}" text-anchor="middle" class="axis">{_fmt(max_x * tick / 3)}</text>'
        )
    if x_label:
        parts.append(
            f'<text x="{left + plot_w / 2}" y="{height - 6}" text-anchor="middle" class="axis">{_esc(x_label)}</text>'
        )
    if y_label:
        parts.append(
            f'<text x="12" y="{top + plot_h / 2}" transform="rotate(-90 12 {top + plot_h / 2})" class="axis">{_esc(y_label)}</text>'
        )
    for x_value, y_value, label, color in points:
        x = left + (x_value / max_x) * plot_w
        y = top + plot_h - (y_value / max_y) * plot_h
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" opacity="0.85">'
            f"<title>{_esc(label)}: {_fmt(x_value, 1)} / {_fmt(y_value, 1)}</title></circle>"
        )
    return _svg("".join(parts), width, height, title)


def stacked_split_chart(
    labels: Sequence[str],
    in_values: Sequence[float],
    out_values: Sequence[float],
    *,
    title: str = "",
    width: int = 760,
    height: Optional[int] = None,
    max_rows: int = 20,
) -> str:
    if not labels:
        return '<p class="empty">No data for this chart.</p>'
    rows = list(zip(labels, in_values, out_values))[:max_rows]
    if height is None:
        height = 54 + len(rows) * 26
    left, right, top, bottom = 180, 70, 30, 20
    plot_w = width - left - right
    max_value = max((a + b for _, a, b in rows), default=1.0) or 1.0
    parts = [
        f'<text x="0" y="18" class="chart-title">{_esc(title)}</text>',
        f'<text x="{left}" y="{height - 4}" class="legend" fill="{GREEN}">in server</text>',
        f'<text x="{left + 90}" y="{height - 4}" class="legend" fill="{RED}">outside</text>',
    ]
    for index, (label, in_value, out_value) in enumerate(rows):
        y = top + index * 26
        in_w = (in_value / max_value) * plot_w
        out_w = (out_value / max_value) * plot_w
        parts.append(f'<text x="{left - 10}" y="{y + 14}" text-anchor="end" class="axis">{_esc(label)}</text>')
        parts.append(
            f'<rect x="{left}" y="{y + 3}" width="{in_w:.1f}" height="16" fill="{GREEN}" opacity="0.9"><title>{_esc(label)} in: {_fmt(in_value, 1)}</title></rect>'
        )
        parts.append(
            f'<rect x="{left + in_w:.1f}" y="{y + 3}" width="{out_w:.1f}" height="16" fill="{RED}" opacity="0.9"><title>{_esc(label)} outside: {_fmt(out_value, 1)}</title></rect>'
        )
        parts.append(
            f'<text x="{left + in_w + out_w + 8:.1f}" y="{y + 15}" class="value">{_fmt(in_value + out_value, 1)}</text>'
        )
    return _svg("".join(parts), width, height, title)


def network_graph(
    nodes: Sequence[NetworkNode],
    edges: Sequence[NetworkEdge],
    *,
    title: str = "",
    width: int = 760,
    height: int = 480,
) -> str:
    if not nodes:
        return '<p class="empty">Not enough shared activity for a network graph.</p>'
    positions: dict[int, tuple[float, float]] = {}
    try:
        import networkx as nx

        graph: Any = nx.Graph()
        for node in nodes:
            graph.add_node(node.user_id)
        for edge in edges:
            graph.add_edge(edge.user_a, edge.user_b, weight=max(0.01, edge.score))
        positions = {
            int(node): (float(point[0]), float(point[1]))
            for node, point in nx.spring_layout(graph, seed=42, k=0.7, iterations=80, weight="weight").items()
        }
    except Exception:
        count = len(nodes)
        for index, node in enumerate(nodes):
            angle = 2 * math.pi * index / max(1, count)
            positions[node.user_id] = (math.cos(angle), math.sin(angle))
    xs = [position[0] for position in positions.values()] or [0.0]
    ys = [position[1] for position in positions.values()] or [0.0]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    left, right, top, bottom = 30, 30, 30, 30
    plot_w = width - left - right
    plot_h = height - top - bottom

    def project(user_id: int) -> tuple[float, float]:
        x, y = positions.get(user_id, (0.0, 0.0))
        px = left + ((x - min_x) / (max_x - min_x or 1.0)) * plot_w
        py = top + ((y - min_y) / (max_y - min_y or 1.0)) * plot_h
        return px, py

    parts = [f'<text x="0" y="18" class="chart-title">{_esc(title)}</text>']
    max_score = max((edge.score for edge in edges), default=1.0) or 1.0
    for edge in edges:
        x1, y1 = project(edge.user_a)
        x2, y2 = project(edge.user_b)
        opacity = 0.15 + 0.55 * (edge.score / max_score)
        parts.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{MUTED}" '
            f'stroke-width="{1 + 3 * (edge.score / max_score):.1f}" opacity="{opacity:.2f}">'
            f"<title>{_esc(edge.label_a)} &amp; {_esc(edge.label_b)}: {edge.co_voice_hours:.1f}h voice, {edge.co_matches} co-matches</title></line>"
        )
    max_hours = max((node.voice_hours for node in nodes), default=1.0) or 1.0
    for node in nodes:
        x, y = project(node.user_id)
        radius = 5 + 12 * math.sqrt(node.voice_hours / max_hours)
        color = PALETTE[node.community % len(PALETTE)]
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" stroke="white" stroke-width="1.2">'
            f"<title>{_esc(node.label)}: {node.voice_hours:.1f}h voice, degree {node.degree}</title></circle>"
        )
        parts.append(
            f'<text x="{x:.1f}" y="{y + radius + 11:.1f}" text-anchor="middle" class="node-label">{_esc(node.label)}</text>'
        )
    return _svg("".join(parts), width, height, title)


def sparkline(values: Sequence[float], *, width: int = 160, height: int = 36, color: str = BLUE) -> str:
    if not values:
        return ""
    max_value = max(values) or 1.0
    count = max(1, len(values) - 1)
    points = " ".join(
        f"{index / count * width:.1f},{height - (value / max_value) * (height - 4) - 2:.1f}"
        for index, value in enumerate(values)
    )
    return _svg(
        f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>',
        width,
        height,
        "trend",
    )
