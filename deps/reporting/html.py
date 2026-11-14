"""Render the single-file HTML analytics report."""

from __future__ import annotations

import html
from datetime import date, datetime
from typing import Optional, Sequence

from deps.reporting import charts
from deps.reporting.models import ActionItem, ReportData, UserMetrics

CLASS_LABELS = {
    "core_in_server": ("Core in-server", "good"),
    "mixed": ("Mixed", "info"),
    "elsewhere_heavy": ("Elsewhere-heavy", "bad"),
    "voice_only": ("Voice only", "warn"),
    "match_only": ("Match only", "violet"),
    "inactive": ("Inactive", "muted"),
}
CATEGORY_LABELS = {
    "reengage": ("Re-engage", "bad"),
    "integrate": ("Integrate", "info"),
    "elsewhere": ("Elsewhere", "bad"),
    "voice_only": ("Voice only", "good"),
    "match_only": ("Match only", "violet"),
    "celebrate": ("Celebrate", "warn"),
    "data": ("Data", "muted"),
    "schedule": ("Schedule", "info"),
    "coaching": ("Coaching", "warn"),
}
PRIORITY_LABELS = {"P0": "P0", "P1": "P1", "P2": "P2"}
PERFORMANCE_COLUMNS = ("User", "Matches", "In win %", "Out win %", "Rank delta", "K/D context")


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _fmt_int(value: int | float) -> str:
    return f"{int(value):,}"


def _fmt_float(value: float, digits: int = 1) -> str:
    return f"{value:,.{digits}f}"


def _fmt_pct(value: float) -> str:
    return f"{value:.1f}%"


def _fmt_rate(wins: int, rows: int) -> str:
    return _fmt_pct(wins * 100.0 / rows) if rows else "n/a"


def _fmt_hours(seconds: float) -> str:
    return _fmt_float(seconds / 3600.0, 1)


def _fmt_minutes(seconds: float) -> str:
    return _fmt_float(seconds / 60.0, 0)


def _fmt_date(value: Optional[datetime | date]) -> str:
    if value is None:
        return "never"
    if isinstance(value, datetime):
        return value.date().isoformat()
    return value.isoformat()


def _fmt_datetime(value: Optional[datetime]) -> str:
    return "never" if value is None else value.strftime("%Y-%m-%d %H:%M UTC")


def _badge(text: str, kind: str = "muted") -> str:
    return f'<span class="badge badge-{kind}">{_esc(text)}</span>'


def _class_badge(classification: str) -> str:
    label, kind = CLASS_LABELS.get(classification, (classification, "muted"))
    return _badge(label, kind)


def _priority_badge(priority: str) -> str:
    kind = {"P0": "bad", "P1": "warn", "P2": "info"}.get(priority, "muted")
    return _badge(priority, kind)


def _category_badge(category: str) -> str:
    label, kind = CATEGORY_LABELS.get(category, (category, "muted"))
    return _badge(label, kind)


def _stat_cards(cards: Sequence[tuple[str, str, str]]) -> str:
    items = "".join(
        f'<div class="stat"><div class="stat-value">{_esc(value)}</div>'
        f'<div class="stat-label">{_esc(label)}</div>'
        f'<div class="stat-hint">{_esc(hint)}</div></div>'
        for value, label, hint in cards
    )
    return f'<div class="stat-grid">{items}</div>'


def _section(section_id: str, title: str, subtitle: str, body: str) -> str:
    return (
        f'<section id="{section_id}" class="section">'
        f'<div class="section-head"><div><div class="eyebrow">{_esc(subtitle)}</div>'
        f"<h2>{_esc(title)}</h2></div></div>"
        f"{body}</section>"
    )


def _table(
    headers: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    table_id: str = "",
    caption: str = "",
    empty: str = "No rows.",
    row_attributes: Optional[Sequence[str]] = None,
) -> str:
    if not rows:
        return f'<p class="empty">{_esc(empty)}</p>'
    head = "".join(f"<th>{_esc(header)}</th>" for header in headers)
    body_rows = []
    for index, row in enumerate(rows):
        attrs = row_attributes[index] if row_attributes and index < len(row_attributes) else ""
        cells = "".join(f"<td>{cell}</td>" for cell in row)
        body_rows.append(f"<tr {attrs}>{cells}</tr>")
    caption_html = f"<caption>{_esc(caption)}</caption>" if caption else ""
    id_attr = f' id="{table_id}"' if table_id else ""
    return (
        f'<div class="table-wrap"><table{id_attr}>{caption_html}<thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(body_rows)}</tbody></table></div>"
    )


def _narrative_html(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    parts: list[str] = []
    in_list = False
    for line in lines:
        if not line:
            if in_list:
                parts.append("</ul>")
                in_list = False
            continue
        if line.startswith("#"):
            if in_list:
                parts.append("</ul>")
                in_list = False
            heading = line.lstrip("#").strip()
            parts.append(f"<h3>{_esc(heading)}</h3>")
        elif line.startswith("- "):
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{_esc(line[2:])}</li>")
        else:
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(f"<p>{_esc(line)}</p>")
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


def _user_link(user_id: int, label: str) -> str:
    return f'<a class="person-link" href="#person-{user_id}">{_esc(label)}</a>'


def _action_user_links(action: ActionItem, report: ReportData) -> str:
    names = []
    for user_id in action.user_ids:
        info = report.users.get(user_id)
        names.append(_user_link(user_id, info.display_name if info else str(user_id)))
    return ", ".join(names)


def _action_card(action: ActionItem, report: ReportData) -> str:
    evidence = "".join(f"<li>{_esc(item)}</li>" for item in action.evidence)
    caveats = "".join(f"<li>{_esc(item)}</li>" for item in action.caveats)
    caveat_html = f'<div class="action-caveat"><strong>Caveats</strong><ul>{caveats}</ul></div>' if caveats else ""
    mention = " ".join(f"<@{user_id}>" for user_id in action.user_ids)
    mention_button = (
        f'<button class="copy-button copy-mention" type="button" data-copy="{_esc(mention)}">Copy mention</button>'
        if mention
        else ""
    )
    return f"""
    <article class="action-card" data-priority="{_esc(action.priority)}" data-category="{_esc(action.category)}"
      data-search="{_esc(action.headline + ' ' + ' '.join(action.evidence))}">
      <div class="action-top">{_priority_badge(action.priority)} {_category_badge(action.category)}
        <span class="confidence">confidence: {_esc(action.confidence)}</span></div>
      <h4>{_esc(action.headline)}</h4>
      <div class="action-people">{_action_user_links(action, report)}</div>
      <div class="action-evidence"><strong>Evidence</strong><ul>{evidence}</ul></div>
      <p><strong>Why it matters.</strong> {_esc(action.why_it_matters)}</p>
      <p><strong>Suggested action.</strong> {_esc(action.suggested_action)}</p>
      {caveat_html}
      <div class="copy-block"><pre>{_esc(action.message)}</pre>
        <button class="copy-button" type="button" data-copy="{_esc(action.message)}">Copy message</button>
        {mention_button}</div>
    </article>
    """


def _person_profile(user: UserMetrics, report: ReportData) -> str:
    actions = [action for action in report.actions if user.user_id in action.user_ids]
    action_links = (
        " ".join(f'<a class="chip" href="#actions">{_esc(action.headline)}</a>' for action in actions[:4])
        or '<span class="muted">No specific action queued.</span>'
    )
    heatmap_values = {(weekday, hour): seconds for (weekday, hour), seconds in user.weekday_hour_voice.items()}
    profile_charts = (
        charts.heatmap(
            heatmap_values,
            charts_chart_row_labels(),
            charts_chart_col_labels(),
            title="Voice hours by local weekday/hour",
            width=720,
            height=250,
            unit="h",
            digits=2,
        )
        if heatmap_values
        else '<p class="empty">No voice activity in this window.</p>'
    )
    partners = _table(
        ["Voice partner", "Shared hours"],
        [[_esc(name), _fmt_float(hours, 1)] for name, hours in user.top_voice_partners],
        empty="No shared voice time above the pair threshold.",
        caption="Top co-voice partners",
    )
    match_partners = _table(
        ["Co-match partner", "Shared matches"],
        [[_esc(name), _fmt_int(count)] for name, count in user.top_match_partners],
        empty="No shared tracked matches.",
        caption="Top co-match partners (likely teammate when the result matches)",
    )
    outside_partners = _table(
        ["Outside partner", "Shared outside matches"],
        [[_esc(name), _fmt_int(count)] for name, count in user.top_outside_partners],
        empty="No repeated outside co-match partner.",
        caption="Partners in outside-server matches",
    )
    split_rows = [
        [
            "In server voice",
            _fmt_int(user.in_rows),
            _fmt_float(user.in_hours, 1),
            _fmt_rate(user.in_wins, user.in_rows),
        ],
        [
            "Outside server voice",
            _fmt_int(user.out_rows),
            _fmt_float(user.out_hours, 1),
            _fmt_rate(user.out_wins, user.out_rows),
        ],
    ]
    split_table = _table(["Split", "Rows", "Match hours", "Win rate"], split_rows)
    spark = charts.sparkline(user.weekly_voice_seconds)
    return f"""
    <details class="profile" id="person-{user.user_id}">
      <summary>
        <span class="profile-name">{_esc(user.display_name)}</span>
        {_class_badge(user.classification)}
        <span class="profile-meta">{_fmt_float(user.voice_hours, 1)}h voice · {_fmt_int(user.match_rows)} ranked rows · last seen {_esc(_fmt_date(user.last_seen))}</span>
      </summary>
      <div class="profile-body">
        <div class="profile-head">
          <div><div class="eyebrow">Player profile</div><h3>{_esc(user.display_name)}</h3>
            <p class="muted">Ubisoft: {_esc(user.ubisoft_name or "unknown")} · Time zone: {_esc(user.time_zone)} · Max MMR: {_fmt_int(user.max_mmr)}</p></div>
          <div class="profile-trend">{spark}<div class="muted small">Last 8 weeks voice trend</div></div>
        </div>
        {_stat_cards([
            (_fmt_float(user.voice_hours, 1), "Voice hours", f"{user.session_count} sessions"),
            (_fmt_int(user.match_rows), "Ranked rows", f"{user.distinct_matches} distinct matches"),
            (_fmt_pct(user.out_percent), "Outside share", f"{user.out_rows} rows outside voice"),
            (_fmt_int(user.messages), "Messages", "human messages, excluding mod audit"),
        ])}
        <div class="two-col">
          <div><h4>Server vs elsewhere</h4>{split_table}</div>
          <div><h4>Flags</h4><p>{''.join(_badge(flag.replace('_', ' '), 'warn') + ' ' for flag in user.flags) or '<span class="muted">No flags.</span>'}</p>
            <h4>Actions</h4><p>{action_links}</p></div>
        </div>
        <h4>Local play pattern</h4>{profile_charts}
        <div class="two-col">
          <div>{partners}</div>
          <div>{match_partners}</div>
        </div>
        <div class="two-col">
          <div>{outside_partners}</div>
          <div><h4>Recent voice by week</h4>{spark}<p class="muted small">Values are hours per ISO week, oldest to newest.</p></div>
        </div>
      </div>
    </details>
    """


def charts_chart_row_labels() -> list[str]:
    return ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def charts_chart_col_labels() -> list[str]:
    return [f"{hour:02d}" for hour in range(24)]


def _window_comparison(report: ReportData) -> str:
    rows = []
    for window in report.windows:
        rows.append(
            [
                _esc(window.window.title),
                _esc(window.window.label),
                _fmt_int(window.voice_users),
                _fmt_float(window.total_voice_hours, 1),
                _fmt_int(window.match_users),
                _fmt_int(window.match_rows),
                _fmt_int(window.distinct_matches),
                _fmt_pct(window.out_percent),
                _fmt_int(window.messages),
            ]
        )
    return _table(
        [
            "Window",
            "Range",
            "Voice users",
            "Voice hours",
            "Match users",
            "Ranked rows",
            "Distinct matches",
            "Outside %",
            "Messages",
        ],
        rows,
        table_id="window-comparison",
        caption="Window comparison. Detailed sections use the previous-month window.",
    )


def _data_quality_section(report: ReportData) -> str:
    dq = report.primary.data_quality
    rows = [
        [
            "Unmatched disconnects",
            _fmt_int(dq.unmatched_disconnects),
            "Disconnect with no open connect; can distort session length.",
        ],
        [
            "Open sessions at window end",
            _fmt_int(dq.open_sessions_at_end),
            "Connect with no disconnect before the window end.",
        ],
        [
            "Sessions over 12 hours",
            _fmt_int(dq.long_sessions),
            "Usually a missing disconnect; verify before treating as real.",
        ],
        [
            "Rollback rows excluded",
            _fmt_int(dq.rollback_rows_excluded),
            "Rows corrected by the tracker; excluded from all match metrics.",
        ],
        [
            "Missing match duration",
            _fmt_int(dq.missing_duration_rows),
            "Overlap uses a point-in-time fallback for these rows.",
        ],
        [
            "Users without a usable time zone",
            _fmt_int(dq.missing_timezone_users),
            "Local-time analysis falls back to UTC.",
        ],
        [
            "Users without an Ubisoft name",
            _fmt_int(dq.missing_ubisoft_users),
            "Identity gap, not necessarily a missing player.",
        ],
        ["Voice-only users (all time)", _fmt_int(dq.voice_only_users), "No tracked ranked rows ever."],
        ["Match-only users (all time)", _fmt_int(dq.match_only_users), "No voice rows ever."],
        ["Duplicate display names", _fmt_int(dq.duplicate_display_names), "Disambiguate by user id or Ubisoft name."],
        ["Snapshot max activity", _esc(_fmt_datetime(dq.snapshot_max_activity)), "Latest row in user_activity."],
        ["Snapshot max match", _esc(_fmt_datetime(dq.snapshot_max_match)), "Latest row in user_full_match_info."],
        ["Snapshot stale days", _fmt_int(dq.stale_days), "Days between the latest activity and the reference date."],
    ]
    return _table(
        ["Check", "Value", "What it means"],
        rows,
        table_id="data-quality",
        caption="Data quality and snapshot coverage for the previous-month window.",
    )


def _methodology(report: ReportData) -> str:
    return f"""
    <div class="prose">
      <h3>Definitions</h3>
      <ul>
        <li><strong>Voice session:</strong> a connect paired with the next disconnect for the same user and channel, then clipped to the window. Overlapping intervals for one user are merged before totals and overlaps.</li>
        <li><strong>Match window:</strong> <code>[match_timestamp - match_duration_ms, match_timestamp]</code>. If duration is missing, the match is treated as a point and flagged.</li>
        <li><strong>In server voice:</strong> the user's match window overlaps any merged voice interval for that user. <strong>Outside:</strong> no overlap.</li>
        <li><strong>Active user:</strong> reported separately for voice, matches, and either, so one number never hides the others.</li>
        <li><strong>Local time:</strong> UTC converted with <code>zoneinfo</code> and the user's <code>user_info.time_zone</code>; UTC is the fallback.</li>
        <li><strong>Co-match / likely teammate:</strong> another tracked user in the same <code>match_uuid</code>. Same result is a teammate heuristic; the database does not store a team id.</li>
        <li><strong>Outside partner:</strong> a co-match in a match classified as outside for the selected user.</li>
        <li><strong>Small sample:</strong> rates with fewer than 5 rows are shown but should not be ranked as reliable.</li>
      </ul>
      <h3>Sources and exclusions</h3>
      <ul>
        <li>Match metrics use <code>user_full_match_info</code> with <code>LOWER(session_type) = 'ranked'</code> and <code>is_rollback = 0</code>.</li>
        <li>Voice metrics use <code>user_activity</code>. Messages are optional context from <code>archived_message</code>, excluding bots and <code>moderator-audit</code>.</li>
        <li>Lifetime snapshots (<code>user_full_stats_info</code>, <code>operator_stats</code>) are context only and are not treated as monthly history.</li>
        <li>The report is read-only and runs from the database path shown below.</li>
      </ul>
      <h3>Known limitations</h3>
      <ul>
        <li>Only tracked users appear in match data. "Outside" means outside guild voice, not outside the community.</li>
        <li>One guild is tracked; cross-server or private voice is invisible.</li>
        <li>Match rows are per user per match; distinct matches are counted by <code>match_uuid</code>.</li>
        <li>Time-zone coverage is US-only in this snapshot; local-time patterns are not universal.</li>
        <li>Behavioral flags are signals, not verdicts. Use them to start a conversation, not to label people.</li>
      </ul>
      <p class="muted">Database: <code>{_esc(report.database_path)}</code> · Reference date: {_esc(report.reference_date.isoformat())} · Generated: {_esc(report.generated_at.strftime("%Y-%m-%d %H:%M UTC"))}</p>
    </div>
    """


def _sidebar() -> str:
    links = [
        ("cover", "Snapshot"),
        ("brief", "Executive brief"),
        ("pulse", "Community pulse"),
        ("patterns", "Play patterns"),
        ("split", "Server vs elsewhere"),
        ("people", "People directory"),
        ("profiles", "Player profiles"),
        ("social", "Social graph"),
        ("performance", "Performance context"),
        ("actions", "Action center"),
        ("methodology", "Data quality & method"),
        ("appendix", "Appendix"),
    ]
    items = "".join(f'<li><a href="#{anchor}">{_esc(label)}</a></li>' for anchor, label in links)
    return f"""
    <aside class="sidebar" id="sidebar">
      <div class="brand"><div class="brand-mark">GT</div><div><div class="brand-title">GameTime</div><div class="brand-sub">Analytics report</div></div></div>
      <nav class="nav" aria-label="Report sections">{items}</nav>
      <div class="sidebar-foot">
        <button class="print-button" type="button" onclick="window.print()">Print / save PDF</button>
        <div class="sidebar-note">Single file. No external requests.</div>
      </div>
    </aside>
    """


def _top_bar(report: ReportData) -> str:
    return f"""
    <header class="topbar">
      <button class="menu-button" type="button" aria-label="Toggle menu" onclick="document.body.classList.toggle('nav-open')">Menu</button>
      <div class="topbar-title">{_esc(report.report_month)} · {_esc(report.primary.window.title)}</div>
      <label class="search-label">Search <input id="global-search" type="search" placeholder="person, action, flag..." autocomplete="off"></label>
    </header>
    """


def _cover(report: ReportData) -> str:
    window = report.primary
    cards = [
        (_fmt_int(window.voice_users), "Voice users", "Distinct users with a voice session"),
        (_fmt_float(window.total_voice_hours, 1), "Voice hours", f"{window.session_count} sessions"),
        (_fmt_int(window.match_users), "Match users", f"{window.match_rows} ranked rows"),
        (_fmt_pct(window.out_percent), "Outside voice", f"{window.out_rows} of {window.match_rows} rows"),
        (_fmt_int(window.peak_concurrent), "Peak concurrent", _fmt_datetime(window.peak_concurrent_at)),
        (_fmt_int(window.messages), "Messages", f"{window.message_users} human authors"),
    ]
    return f"""
    <section id="cover" class="section cover">
      <div class="cover-grid">
        <div>
          <div class="eyebrow">Rainbow Six Siege community analytics</div>
          <h1>Monthly report<br><span>{_esc(report.primary.window.start.strftime("%B %Y"))}</span></h1>
          <p class="lead">A navigable read of voice activity, ranked play, playing patterns, and the people worth talking to.</p>
          <div class="cover-meta">
            <div><strong>Report month</strong><br>{_esc(report.report_month)}</div>
            <div><strong>Window</strong><br>{_esc(report.primary.window.label)}</div>
            <div><strong>Reference date</strong><br>{_esc(report.reference_date.isoformat())}</div>
            <div><strong>Snapshot</strong><br>{_esc(_fmt_datetime(report.primary.data_quality.snapshot_max_activity))}</div>
          </div>
        </div>
        <div class="cover-note">
          <div class="cover-note-title">Read this first</div>
          <p>Every number below is computed from the community database. The action list is a set of suggestions, not a verdict on any player.</p>
          <p class="muted">The detailed sections use the previous-month window. The appendix compares the longer windows.</p>
        </div>
      </div>
      {_stat_cards(cards)}
    </section>
    """


def _brief(report: ReportData) -> str:
    window = report.primary
    top_actions = report.actions[:5]
    action_html = "".join(
        f"<li>{_priority_badge(action.priority)} {_category_badge(action.category)} {_esc(action.headline)}</li>"
        for action in top_actions
    )
    return _section(
        "brief",
        "Executive brief",
        "The short version",
        f"""
        <div class="brief-grid">
          <div class="panel narrative">
            <div class="panel-head"><h3>Narrative</h3><span class="pill">{_esc(report.narrative_source)}</span></div>
            {_narrative_html(report.narrative)}
          </div>
          <div class="panel">
            <div class="panel-head"><h3>Start here</h3><span class="pill">{len(report.actions)} actions</span></div>
            <ul class="action-list">{action_html or '<li>No actions generated.</li>'}</ul>
            <div class="mini-grid">
              <div><div class="mini-value">{_fmt_int(window.new_users)}</div><div class="mini-label">new</div></div>
              <div><div class="mini-value">{_fmt_int(window.returning_users)}</div><div class="mini-label">returning</div></div>
              <div><div class="mini-value">{_fmt_int(window.churned_users)}</div><div class="mini-label">churned</div></div>
              <div><div class="mini-value">{_fmt_pct(window.in_percent)}</div><div class="mini-label">in-server</div></div>
            </div>
          </div>
        </div>
        """,
    )


def _pulse(report: ReportData) -> str:
    window = report.primary
    all_data = next((w for w in report.windows if w.window.key == "all_data"), window)
    weekly_series = [
        (
            "Voice hours",
            [(day.strftime("%m-%d"), seconds / 3600.0) for day, seconds in window.weekly_voice],
        )
    ]
    monthly_series = [
        (
            "Voice hours",
            [(month, seconds / 3600.0) for month, seconds in all_data.monthly_voice[-18:]],
        )
    ]
    daily_series = [
        (
            "Unique users",
            [(day.strftime("%m-%d"), float(count)) for day, count in window.unique_users_per_day],
        )
    ]
    cards = [
        (_fmt_int(window.voice_users), "Voice users", "Active at least one session"),
        (_fmt_float(window.total_voice_hours, 1), "Voice hours", f"{window.session_count} sessions"),
        (_fmt_float(window.median_session_minutes, 0) + "m", "Median session", "Clipped sessions"),
        (_fmt_int(window.peak_concurrent), "Peak concurrent", _fmt_datetime(window.peak_concurrent_at)),
        (_fmt_float(window.avg_concurrent, 1), "Average concurrent", "Time-weighted"),
        (_fmt_int(window.match_rows), "Ranked rows", f"{window.distinct_matches} distinct matches"),
    ]
    return _section(
        "pulse",
        "Community pulse",
        "Activity, trends, and consistency",
        f"""
        {_stat_cards(cards)}
        <div class="chart-grid">
          <div class="panel">{charts.line_chart(weekly_series, title="Voice hours by ISO week", y_label="hours", height=300)}</div>
          <div class="panel">{charts.line_chart(monthly_series, title="Voice hours by month (all data)", y_label="hours", height=300)}</div>
        </div>
        <div class="panel">{charts.line_chart(daily_series, title="Unique voice users per day", y_label="users", height=280)}</div>
        <div class="panel">
          <h3>Reading the pulse</h3>
          <p class="muted">Peak concurrency is a point-in-time count of distinct users in voice. Average concurrency is time-weighted over the whole window, so a short spike does not dominate it.</p>
        </div>
        """,
    )


def _patterns(report: ReportData) -> str:
    window = report.primary
    voice_heatmap = charts.heatmap(
        window.weekday_hour_voice,
        charts_chart_row_labels(),
        charts_chart_col_labels(),
        title="Voice hours by local weekday and hour",
        height=320,
        digits=2,
        unit="h",
    )
    match_heatmap = charts.heatmap(
        {(row, col): float(value) for (row, col), value in window.weekday_hour_matches.items()},
        charts_chart_row_labels(),
        charts_chart_col_labels(),
        title="Ranked rows by local weekday and hour",
        height=320,
        digits=0,
    )
    session_labels = list(window.session_length_counts.keys())
    session_values = [float(window.session_length_counts[label]) for label in session_labels]
    top_voice = [user for user in window.users if user.voice_hours > 0][:15]
    return _section(
        "patterns",
        "Play patterns",
        "When the community shows up",
        f"""
        <div class="chart-grid">
          <div class="panel">{voice_heatmap}</div>
          <div class="panel">{match_heatmap}</div>
        </div>
        <div class="chart-grid">
          <div class="panel">{charts.bar_chart(session_labels, session_values, title="Session length distribution", digits=0, color=charts.BLUE, height=300)}</div>
          <div class="panel">{charts.horizontal_bar_chart([u.display_name for u in top_voice], [u.voice_hours for u in top_voice], title="Top voice hours", digits=1, color=charts.GREEN)}</div>
        </div>
        <div class="panel">
          <h3>What the pattern suggests</h3>
          <p class="muted">The heatmaps use each user's configured time zone, not UTC. A populated late-night row can be a real local habit or a small group in a different zone; check the time-zone distribution in the methodology before scheduling around it.</p>
        </div>
        """,
    )


def _split(report: ReportData) -> str:
    window = report.primary
    cards = [
        (_fmt_pct(window.in_percent), "In-server share", f"{window.in_rows} rows · {_fmt_hours(window.in_seconds)}h"),
        (_fmt_pct(window.out_percent), "Outside share", f"{window.out_rows} rows · {_fmt_hours(window.out_seconds)}h"),
        (_fmt_float(window.total_voice_hours, 1), "Voice hours", "Merged, clipped sessions"),
        (_fmt_int(window.outside_while_active_count), "Outside while active", "Matches while 3+ others were in voice"),
    ]
    split_users = [user for user in window.users if user.match_rows > 0]
    split_users.sort(key=lambda user: -(user.in_rows + user.out_rows))
    split_users = split_users[:15]
    split_chart = charts.stacked_split_chart(
        [user.display_name for user in split_users],
        [user.in_hours for user in split_users],
        [user.out_hours for user in split_users],
        title="Match hours: in server vs outside",
    )
    scatter_points = [
        (user.voice_hours, user.out_percent, user.display_name, charts.RED if user.out_percent >= 60 else charts.GREEN)
        for user in window.users
        if user.match_rows > 0
    ]
    outside_rows = sorted(
        [user for user in window.users if user.out_rows > 0],
        key=lambda user: (-user.out_rows, -user.out_hours),
    )[:25]
    outside_table = _table(
        ["User", "Outside rows", "Outside %", "Outside hours", "While active", "Top outside partner"],
        [
            [
                _user_link(user.user_id, user.display_name),
                _fmt_int(user.out_rows),
                _fmt_pct(user.out_percent),
                _fmt_float(user.out_hours, 1),
                _fmt_int(user.outside_while_active),
                (
                    _esc(user.top_outside_partners[0][0])
                    if user.top_outside_partners
                    else '<span class="muted">none</span>'
                ),
            ]
            for user in outside_rows
        ],
        table_id="outside-table",
        caption="Users with ranked rows outside server voice. Sorted by outside volume.",
    )
    in_dc = sorted(window.in_data_centers.items(), key=lambda item: -item[1])
    out_dc = sorted(window.out_data_centers.items(), key=lambda item: -item[1])
    dc_table = _table(
        ["Data center", "In-server rows", "Outside rows"],
        [
            [_esc(name), _fmt_int(dict(in_dc).get(name, 0)), _fmt_int(dict(out_dc).get(name, 0))]
            for name in sorted(
                set(dict(in_dc)) | set(dict(out_dc)), key=lambda n: -(dict(in_dc).get(n, 0) + dict(out_dc).get(n, 0))
            )
        ],
        caption="Data center mix. A data center is not a team or a server; it is match infrastructure context.",
    )
    return _section(
        "split",
        "Server vs elsewhere",
        "Where ranked play actually happens",
        f"""
        {_stat_cards(cards)}
        <div class="panel">{split_chart}</div>
        <div class="chart-grid">
          <div class="panel">{charts.scatter(scatter_points, title="Voice hours vs outside share", x_label="voice hours", y_label="outside %", height=340)}</div>
          <div class="panel"><h3>What this means</h3>
            <p class="muted">A match is "outside" when the play window does not overlap the player's Discord voice session. It does not mean the player is absent from the community; it means they were not in guild voice while playing ranked.</p>
            <p class="muted">The strongest signal is <strong>outside while active</strong>: a ranked match played while at least three other tracked users were in voice. That is the shortlist for a neutral conversation about schedule or stack.</p></div>
        </div>
        <div class="panel"><h3>Outside-volume shortlist</h3>{outside_table}</div>
        <div class="panel"><h3>Data center mix</h3>{dc_table}</div>
        """,
    )


def _people(report: ReportData) -> str:
    window = report.primary
    rows = []
    attrs = []
    for user in window.users:
        if user.voice_seconds == 0 and user.match_rows == 0:
            continue
        flags = "".join(f'<span class="badge badge-warn">{_esc(flag.replace("_", " "))}</span> ' for flag in user.flags)
        search = f"{user.display_name} {user.ubisoft_name} {user.classification} {' '.join(user.flags)}"
        rows.append(
            [
                _user_link(user.user_id, user.display_name),
                _class_badge(user.classification),
                _fmt_float(user.voice_hours, 1),
                _fmt_int(user.match_rows),
                _fmt_int(user.in_rows),
                _fmt_int(user.out_rows),
                _fmt_pct(user.out_percent) if user.match_rows else "n/a",
                _esc(_fmt_date(user.last_seen)),
                flags or '<span class="muted">-</span>',
            ]
        )
        attrs.append(f'data-search="{_esc(search)}" data-user="{user.user_id}"')
    table = _table(
        ["User", "Class", "Voice h", "Ranked", "In", "Out", "Out %", "Last seen", "Flags"],
        rows,
        table_id="people-table",
        caption="People directory. Click a name for the profile. Use the search box to filter.",
        row_attributes=attrs,
    )
    return _section(
        "people",
        "People directory",
        "Every active person in one table",
        f"""
        <div class="panel">
          <div class="table-tools">
            <label>Filter <input id="people-filter" type="search" placeholder="name, class, flag..." autocomplete="off"></label>
            <span class="muted small">{len(rows)} active users in this window</span>
          </div>
          {table}
        </div>
        """,
    )


def _profiles(report: ReportData) -> str:
    window = report.primary
    active = [user for user in window.users if user.voice_seconds > 0 or user.match_rows > 0]
    active.sort(key=lambda user: (-user.voice_hours, -user.match_rows, user.display_name.lower()))
    selected = list(active)
    extra_ids = {uid for action in report.actions for uid in action.user_ids}
    selected_ids = {user.user_id for user in selected}
    for user in active:
        if user.user_id in extra_ids and user.user_id not in selected_ids:
            selected.append(user)
            selected_ids.add(user.user_id)
    for user_id in sorted(extra_ids - selected_ids):
        profile_user = window.user(user_id)
        if profile_user is not None:
            selected.append(profile_user)
            selected_ids.add(user_id)
    profiles = "".join(_person_profile(user, report) for user in selected)
    return _section(
        "profiles",
        "Player profiles",
        f"{len(selected)} linkable profiles, ordered by activity",
        f"""
        <div class="panel">
          <p class="muted">Each profile is collapsible and linkable. The weekly sparkline is the last eight ISO weeks, oldest to newest.</p>
          {profiles or '<p class="empty">No active profiles.</p>'}
        </div>
        """,
    )


def _social(report: ReportData) -> str:
    window = report.primary
    nodes = report.network_nodes
    edges = report.network_edges
    graph = charts.network_graph(nodes, edges, title="Community network (top nodes by voice, edges by shared time)")
    pairs = window.pairs[:20]
    pair_rows = [
        [
            _user_link(
                pair.user_a, report.users[pair.user_a].display_name if pair.user_a in report.users else str(pair.user_a)
            ),
            _user_link(
                pair.user_b, report.users[pair.user_b].display_name if pair.user_b in report.users else str(pair.user_b)
            ),
            _fmt_float(pair.co_voice_seconds / 3600.0, 1),
            _fmt_int(pair.co_matches),
            _fmt_int(pair.co_wins),
        ]
        for pair in pairs
    ]
    pair_table = _table(
        ["Person A", "Person B", "Shared voice h", "Co-matches", "Same-result co-matches"],
        pair_rows,
        caption="Top relationships by combined co-voice and co-match score.",
    )
    bridges = sorted(nodes, key=lambda node: -node.betweenness)[:8]
    bridge_rows = [
        [
            _user_link(node.user_id, node.label),
            _fmt_float(node.betweenness, 3),
            _fmt_int(node.degree),
            _fmt_float(node.voice_hours, 1),
        ]
        for node in bridges
        if node.betweenness > 0
    ]
    bridge_table = _table(
        ["Bridge", "Betweenness", "Degree", "Voice h"],
        bridge_rows,
        empty="No clear bridge in the filtered network.",
        caption="High-betweenness users connect otherwise separate groups.",
    )
    isolated = [user for user in window.users if user.voice_hours >= 2 and len(user.top_voice_partners) <= 1][:15]
    isolated_table = _table(
        ["Regular", "Voice h", "Voice partners", "Suggested move"],
        [
            [
                _user_link(user.user_id, user.display_name),
                _fmt_float(user.voice_hours, 1),
                _fmt_int(len(user.top_voice_partners)),
                _esc("Introduce them to a same-time regular."),
            ]
            for user in isolated
        ],
        empty="No isolated regulars by the current threshold.",
        caption="Voice regulars with at most one strong partner.",
    )
    return _section(
        "social",
        "Social graph",
        "Who plays with whom",
        f"""
        <div class="panel">{graph}</div>
        <div class="chart-grid">
          <div class="panel"><h3>Top pairs</h3>{pair_table}</div>
          <div class="panel"><h3>Bridges</h3>{bridge_table}</div>
        </div>
        <div class="panel"><h3>Isolated regulars</h3>{isolated_table}</div>
        """,
    )


def _performance(report: ReportData) -> str:
    window = report.primary
    users = [user for user in window.users if user.match_rows >= 5]
    users.sort(key=lambda user: -((user.in_rank_delta + user.out_rank_delta)))
    rows = [
        [
            _user_link(user.user_id, user.display_name),
            _fmt_int(user.match_rows),
            _fmt_rate(user.in_wins, user.in_rows),
            _fmt_rate(user.out_wins, user.out_rows),
            f"{user.in_rank_delta + user.out_rank_delta:+d}",
            f"{_fmt_float(user.match_hours, 1)}h",
        ]
        for user in users[:25]
    ]
    table = _table(
        ["User", "Ranked rows", "In win %", "Out win %", "Rank delta", "Match hours"],
        rows,
        caption="Performance context. Small samples are still shown; use the row count before drawing conclusions.",
    )
    aggregate_in = sum(user.in_wins for user in users)
    aggregate_out = sum(user.out_wins for user in users)
    in_rows = sum(user.in_rows for user in users)
    out_rows = sum(user.out_rows for user in users)
    return _section(
        "performance",
        "Performance context",
        "Win rates and rank movement, not a skill verdict",
        f"""
        {_stat_cards([
            (_fmt_rate(aggregate_in, in_rows), "In-server win rate", f"{in_rows} rows"),
            (_fmt_rate(aggregate_out, out_rows), "Outside win rate", f"{out_rows} rows"),
            (_fmt_int(len(users)), "Users with 5+ rows", "Smaller samples excluded from this table"),
            (_fmt_int(window.match_rows), "Total ranked rows", "All users in the window"),
        ])}
        <div class="panel">{table}</div>
        <div class="panel"><p class="muted">A win-rate difference between in-server and outside play is an observation, not evidence that voice causes wins. Opponents, stacks, maps, and time of day are not controlled here.</p></div>
        """,
    )


def _actions(report: ReportData) -> str:
    priorities = sorted({action.priority for action in report.actions})
    categories = sorted({action.category for action in report.actions})
    filters = [
        '<button class="filter-chip active" type="button" data-filter-type="priority" data-filter-value="all">All</button>'
    ]
    filters.extend(
        f'<button class="filter-chip" type="button" data-filter-type="priority" data-filter-value="{_esc(priority)}">{_esc(priority)}</button>'
        for priority in priorities
    )
    category_filters = "".join(
        f'<button class="filter-chip" type="button" data-filter-type="category" data-filter-value="{_esc(category)}">{_esc(CATEGORY_LABELS.get(category, (category, ""))[0])}</button>'
        for category in categories
    )
    cards = "".join(_action_card(action, report) for action in report.actions)
    return _section(
        "actions",
        "Action center",
        "Who to talk to and what to do",
        f"""
        <div class="panel">
          <p class="muted">Priorities are suggestions based on impact, confidence, and recency. Every card shows the evidence and a copyable message. Nothing is sent automatically.</p>
          <div class="filter-row">{''.join(filters)}</div>
          <div class="filter-row">{category_filters}</div>
          <div class="action-grid" id="action-grid">{cards or '<p class="empty">No actions generated.</p>'}</div>
        </div>
        """,
    )


def _appendix(report: ReportData) -> str:
    return _section(
        "appendix",
        "Appendix",
        "Window comparison and definitions",
        f"""
        <div class="panel"><h3>Window comparison</h3>{_window_comparison(report)}</div>
        <div class="panel"><h3>Metric notes</h3>
          <ul class="prose">
            <li><strong>Voice hours</strong> are merged per user, so overlapping sessions do not double-count.</li>
            <li><strong>Match hours</strong> are the sum of tracked match durations, not wall-clock time in a session.</li>
            <li><strong>Outside %</strong> is outside ranked rows divided by all ranked rows for the same users.</li>
            <li><strong>Co-match</strong> means two tracked users share a <code>match_uuid</code>; same-result is a teammate heuristic.</li>
            <li><strong>Messages</strong> exclude bots and the <code>moderator-audit</code> channel.</li>
          </ul>
        </div>
        <div class="panel"><h3>Change log</h3>
          <p class="muted">This report replaces the linear PDF for the same month. The PDF generator remains available and unchanged. The HTML report adds per-person navigation, action cards, local-time heatmaps, and the outside-while-active signal.</p>
        </div>
        """,
    )


def _css() -> str:
    return """
    :root {
      --navy: #0F1B2D; --navy-2: #1E3A5F; --orange: #F18F01; --ink: #1F2937;
      --muted: #6B7280; --bg: #F4F6F8; --card: #FFFFFF; --border: #E5E7EB;
      --good: #1BAF7A; --bad: #E34948; --warn: #EDA100; --info: #2A78D6; --violet: #6D4AAE;
      --radius: 14px; --shadow: 0 10px 30px rgba(15, 27, 45, 0.07);
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { margin: 0; background: var(--bg); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Arial, sans-serif; line-height: 1.55; }
    a { color: var(--info); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .layout { display: flex; min-height: 100vh; }
    .sidebar { width: 270px; flex: 0 0 270px; position: sticky; top: 0; height: 100vh; overflow: auto; background: var(--navy); color: white; padding: 24px 18px; }
    .brand { display: flex; gap: 12px; align-items: center; margin-bottom: 26px; }
    .brand-mark { width: 42px; height: 42px; border-radius: 12px; background: var(--orange); color: var(--navy); display: grid; place-items: center; font-weight: 800; letter-spacing: -0.04em; }
    .brand-title { font-weight: 800; letter-spacing: 0.02em; }
    .brand-sub { color: #9FB3C8; font-size: 12px; }
    .nav { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
    .nav a { display: block; color: #C9D6E4; padding: 8px 10px; border-radius: 8px; font-size: 14px; }
    .nav a:hover, .nav a.active { background: rgba(255,255,255,0.09); color: white; text-decoration: none; }
    .sidebar-foot { margin-top: 28px; border-top: 1px solid rgba(255,255,255,0.12); padding-top: 16px; }
    .print-button { width: 100%; border: 0; border-radius: 9px; padding: 10px 12px; background: var(--orange); color: var(--navy); font-weight: 700; cursor: pointer; }
    .sidebar-note { color: #9FB3C8; font-size: 11px; margin-top: 10px; }
    .main { flex: 1; min-width: 0; max-width: 1440px; margin: 0 auto; padding: 26px 38px 80px; }
    .topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 18px; }
    .topbar-title { font-weight: 700; color: var(--navy); }
    .search-label { margin-left: auto; display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); }
    input[type="search"] { border: 1px solid var(--border); border-radius: 9px; padding: 8px 10px; min-width: 240px; background: white; color: var(--ink); }
    .menu-button { display: none; border: 1px solid var(--border); background: white; border-radius: 9px; padding: 8px 12px; }
    .section { margin: 0 0 34px; scroll-margin-top: 20px; }
    .section-head { border-bottom: 2px solid var(--border); margin-bottom: 16px; padding-bottom: 10px; }
    .eyebrow { color: var(--orange); text-transform: uppercase; letter-spacing: 0.11em; font-size: 11px; font-weight: 800; }
    h1, h2, h3, h4 { color: var(--navy); line-height: 1.15; margin: 0 0 10px; }
    h1 { font-size: clamp(34px, 5vw, 58px); letter-spacing: -0.045em; }
    h1 span { color: var(--orange); }
    h2 { font-size: clamp(24px, 3vw, 34px); letter-spacing: -0.03em; }
    h3 { font-size: 18px; margin-top: 18px; }
    h4 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.06em; margin-top: 18px; }
    p { margin: 0 0 10px; }
    .lead { font-size: 18px; color: #374151; max-width: 760px; }
    .muted { color: var(--muted); }
    .small { font-size: 12px; }
    .cover-grid { display: grid; grid-template-columns: 1.5fr 0.9fr; gap: 28px; align-items: end; padding: 18px 0 12px; }
    .cover-meta { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 24px; color: var(--muted); font-size: 13px; }
    .cover-meta strong { color: var(--navy); }
    .cover-note { background: var(--navy); color: #DCE7F2; border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow); }
    .cover-note-title { color: var(--orange); font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; font-size: 11px; margin-bottom: 8px; }
    .cover-note p { color: #DCE7F2; }
    .stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: 16px 0; }
    .stat { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 16px; box-shadow: var(--shadow); }
    .stat-value { font-size: 28px; font-weight: 850; color: var(--navy); letter-spacing: -0.03em; }
    .stat-label { font-weight: 700; font-size: 13px; margin-top: 3px; }
    .stat-hint { color: var(--muted); font-size: 11px; margin-top: 4px; }
    .panel { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); padding: 18px; box-shadow: var(--shadow); margin: 14px 0; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
    .pill { background: #EEF2F7; color: var(--muted); border-radius: 999px; padding: 3px 9px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
    .brief-grid { display: grid; grid-template-columns: 1.4fr 0.9fr; gap: 14px; }
    .mini-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin-top: 14px; }
    .mini-value { font-size: 22px; font-weight: 800; color: var(--navy); }
    .mini-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
    .action-list { margin: 0; padding-left: 18px; }
    .action-list li { margin: 7px 0; }
    .chart-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
    .chart { width: 100%; height: auto; display: block; }
    .chart-title { font-size: 13px; font-weight: 800; fill: var(--navy); }
    .axis { font-size: 10px; fill: var(--muted); }
    .value { font-size: 10px; fill: var(--ink); font-weight: 700; }
    .legend { font-size: 11px; font-weight: 700; }
    .node-label { font-size: 8px; fill: var(--ink); font-weight: 600; }
    .badge { display: inline-block; border-radius: 999px; padding: 2px 8px; font-size: 10px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap; }
    .badge-good { background: #DDF6EC; color: #0F7A55; }
    .badge-bad { background: #FDE3E4; color: #A51D2D; }
    .badge-warn { background: #FFF0CF; color: #8A5A00; }
    .badge-info { background: #E3EEFB; color: #1B5EA8; }
    .badge-violet { background: #EBE4F8; color: #55308F; }
    .badge-muted { background: #EEF2F7; color: #5B6675; }
    .table-wrap { overflow-x: auto; border: 1px solid var(--border); border-radius: 12px; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    caption { text-align: left; color: var(--muted); font-size: 12px; padding: 8px 10px; }
    th { background: #F8FAFC; color: var(--navy); text-align: left; padding: 10px; border-bottom: 1px solid var(--border); position: sticky; top: 0; font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; }
    td { padding: 9px 10px; border-bottom: 1px solid #F0F2F5; vertical-align: top; }
    tr:last-child td { border-bottom: 0; }
    tbody tr:hover { background: #FAFBFD; }
    .table-tools { display: flex; align-items: center; gap: 12px; margin-bottom: 10px; flex-wrap: wrap; }
    .table-tools label { display: flex; gap: 8px; align-items: center; font-size: 12px; color: var(--muted); }
    .profile { background: var(--card); border: 1px solid var(--border); border-radius: 12px; margin: 10px 0; box-shadow: var(--shadow); }
    .profile summary { cursor: pointer; padding: 14px 16px; display: flex; gap: 10px; align-items: center; flex-wrap: wrap; list-style: none; }
    .profile summary::-webkit-details-marker { display: none; }
    .profile summary::before { content: "+"; width: 22px; height: 22px; border-radius: 50%; background: var(--navy); color: white; display: grid; place-items: center; font-weight: 800; flex: 0 0 22px; }
    .profile[open] summary::before { content: "−"; }
    .profile-name { font-weight: 800; color: var(--navy); }
    .profile-meta { color: var(--muted); font-size: 12px; }
    .profile-body { padding: 0 16px 18px; border-top: 1px solid var(--border); }
    .profile-head { display: flex; justify-content: space-between; gap: 18px; align-items: flex-start; padding-top: 14px; }
    .profile-trend { text-align: right; }
    .two-col { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .action-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(330px, 1fr)); gap: 14px; }
    .action-card { background: #FBFCFE; border: 1px solid var(--border); border-radius: 12px; padding: 15px; }
    .action-card h4 { margin: 9px 0 4px; text-transform: none; letter-spacing: 0; font-size: 17px; }
    .action-top { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
    .confidence { color: var(--muted); font-size: 11px; margin-left: auto; }
    .action-people { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
    .action-evidence ul, .action-caveat ul { margin: 4px 0 10px; padding-left: 18px; }
    .action-evidence li, .action-caveat li { margin: 3px 0; }
    .action-caveat { background: #FFF8E7; border-radius: 8px; padding: 8px 10px; font-size: 12px; }
    .copy-block { margin-top: 10px; }
    .copy-block pre { background: var(--navy); color: #E7EEF7; border-radius: 9px; padding: 12px; white-space: pre-wrap; font-size: 12px; margin: 0 0 8px; }
    .copy-button { border: 0; border-radius: 8px; background: var(--orange); color: var(--navy); padding: 8px 11px; font-weight: 800; cursor: pointer; }
    .filter-row { display: flex; flex-wrap: wrap; gap: 7px; margin: 10px 0; }
    .filter-chip { border: 1px solid var(--border); background: white; color: var(--ink); border-radius: 999px; padding: 6px 11px; font-size: 12px; cursor: pointer; }
    .filter-chip.active { background: var(--navy); color: white; border-color: var(--navy); }
    .chip { display: inline-block; background: #EEF2F7; border-radius: 999px; padding: 4px 9px; font-size: 11px; margin: 2px; color: var(--navy); }
    .empty { color: var(--muted); font-style: italic; }
    .prose ul { padding-left: 20px; }
    .prose li { margin: 4px 0; }
    code { background: #EEF2F7; border-radius: 4px; padding: 1px 5px; font-size: 0.92em; }
    .person-link { font-weight: 700; }
    .nav-open .sidebar { display: block; }
    @media (max-width: 1050px) { .chart-grid, .two-col, .brief-grid, .cover-grid { grid-template-columns: 1fr; } }
    @media (max-width: 820px) {
      .layout { display: block; }
      .sidebar { position: static; width: auto; height: auto; display: none; }
      .nav-open .sidebar { display: block; }
      .menu-button { display: inline-block; }
      .main { padding: 18px 16px 60px; }
      input[type="search"] { min-width: 150px; }
      .topbar { flex-wrap: wrap; }
    }
    @media print {
      body { background: white; }
      .sidebar, .topbar, .copy-button, .filter-row, .print-button, .menu-button { display: none !important; }
      .main { max-width: none; padding: 0; }
      .panel, .stat, .action-card, .profile { box-shadow: none; break-inside: avoid; }
      .section { break-inside: avoid; }
      details { open: true; }
    }
    """


def _js() -> str:
    return """
    (function () {
      const navLinks = Array.from(document.querySelectorAll('.nav a'));
      const sections = navLinks.map(link => document.querySelector(link.getAttribute('href'))).filter(Boolean);
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (!entry.isIntersecting) return;
          navLinks.forEach(link => link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id));
        });
      }, { rootMargin: '-20% 0px -70% 0px', threshold: 0.01 });
      sections.forEach(section => observer.observe(section));

      const globalSearch = document.getElementById('global-search');
      const peopleFilter = document.getElementById('people-filter');
      const applySearch = (value) => {
        const term = value.trim().toLowerCase();
        document.querySelectorAll('#people-table tbody tr').forEach(row => {
          row.style.display = !term || (row.dataset.search || '').toLowerCase().includes(term) ? '' : 'none';
        });
        document.querySelectorAll('.profile').forEach(profile => {
          profile.style.display = !term || (profile.textContent || '').toLowerCase().includes(term) ? '' : 'none';
        });
        document.querySelectorAll('.action-card').forEach(card => {
          card.style.display = !term || (card.dataset.search || '').toLowerCase().includes(term) ? '' : 'none';
        });
      };
      if (globalSearch) globalSearch.addEventListener('input', event => { applySearch(event.target.value); if (peopleFilter) peopleFilter.value = event.target.value; });
      if (peopleFilter) peopleFilter.addEventListener('input', event => { applySearch(event.target.value); if (globalSearch) globalSearch.value = event.target.value; });

      let priorityFilter = 'all';
      let categoryFilter = 'all';
      const applyActionFilters = () => {
        document.querySelectorAll('.action-card').forEach(card => {
          const priorityOk = priorityFilter === 'all' || card.dataset.priority === priorityFilter;
          const categoryOk = categoryFilter === 'all' || card.dataset.category === categoryFilter;
          card.style.display = priorityOk && categoryOk ? '' : 'none';
        });
      };
      document.querySelectorAll('.filter-chip').forEach(button => {
        button.addEventListener('click', () => {
          const type = button.dataset.filterType;
          if (type === 'priority') { priorityFilter = button.dataset.filterValue; }
          if (type === 'category') { categoryFilter = categoryFilter === button.dataset.filterValue ? 'all' : button.dataset.filterValue; }
          button.parentElement.querySelectorAll('.filter-chip').forEach(sibling => sibling.classList.remove('active'));
          button.classList.add('active');
          applyActionFilters();
        });
      });

      document.querySelectorAll('.copy-button').forEach(button => {
        button.addEventListener('click', async () => {
          const text = button.dataset.copy || '';
          try { await navigator.clipboard.writeText(text); button.textContent = 'Copied'; }
          catch (error) {
            const area = document.createElement('textarea'); area.value = text; document.body.appendChild(area); area.select();
            try { document.execCommand('copy'); button.textContent = 'Copied'; } catch (e) { button.textContent = 'Copy failed'; }
            area.remove();
          }
          setTimeout(() => { button.textContent = 'Copy message'; }, 1600);
        });
      });

      document.addEventListener('keydown', event => {
        if (event.key === '/' && document.activeElement.tagName !== 'INPUT') { event.preventDefault(); if (globalSearch) globalSearch.focus(); }
        if (event.key === 'Escape') { if (globalSearch) globalSearch.value = ''; if (peopleFilter) peopleFilter.value = ''; applySearch(''); }
      });

      window.addEventListener('beforeprint', () => {
        document.querySelectorAll('details').forEach(detail => {
          detail.dataset.wasOpen = detail.open ? '1' : '0';
          detail.open = true;
        });
      });
      window.addEventListener('afterprint', () => {
        document.querySelectorAll('details').forEach(detail => {
          detail.open = detail.dataset.wasOpen === '1';
        });
      });
    })();
    """


def render_report_html(report: ReportData) -> str:
    """Render the complete single-file HTML report."""
    body = "".join(
        [
            _cover(report),
            _brief(report),
            _pulse(report),
            _patterns(report),
            _split(report),
            _people(report),
            _profiles(report),
            _social(report),
            _performance(report),
            _actions(report),
            _section(
                "methodology",
                "Data quality & methodology",
                "How to read this report",
                _data_quality_section(report) + _methodology(report),
            ),
            _appendix(report),
        ]
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GameTime Analytics {_esc(report.report_month)}</title>
<style>{_css()}</style>
</head>
<body>
<div class="layout">
{_sidebar()}
<main class="main">
{_top_bar(report)}
{body}
</main>
</div>
<script>{_js()}</script>
</body>
</html>
"""
