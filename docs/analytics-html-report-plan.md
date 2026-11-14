# GameTime Analytics HTML Report — Reusable Plan

Status: implemented for October 2026. The plan remains the reusable specification for future months.
Scope: replace the 300+ page PDF with one self-contained, navigable HTML report for **October 2026** (data through 2026-10-31), and make the same report reusable for every future month.

Generated artifact:

- `reports/monthly/2026-10/gametime_report_2026-10.html`
- Built from `user_activity.db` refreshed from the production host with `sqlite3 .backup` on 2026-11-14.
- Local pre-refresh DB kept as `user_activity.db.bak-20261114T204641Z`.

Related code:

- New report package: `deps/reporting/`
- New CLI: `scripts/generate_analytics_report.py`
- New tests: `tests/reporting_*_unit_test.py`
- Existing PDF generator: `scripts/generate_monthly_report.py` → `deps/monthly_report.py`
- Existing PDF theme: `deps/monthly_report_style.py`
- Existing analytics queries: `deps/analytic_*_data_access.py`
- Schema documentation: `deps/ai/data_catalog.py`

## 1. Goal

Produce one HTML file that answers three questions for the server admin:

1. **What happened?** Activity, matches, people, trends, and data quality for the report month.
2. **What is actually going on?** Playing patterns, who plays where, who is drifting, who is isolated, and how server voice relates to ranked play.
3. **What should I do?** A prioritized, evidence-backed action list: who to talk to, what to ask, what to schedule, what to celebrate, and what data to fix.

The report must be:

- **One file.** No external CSS, JS, fonts, images, or network requests.
- **Navigable.** A sidebar menu with sections and anchors, a searchable people directory, and per-player detail views.
- **Reproducible.** A pinned reference date produces the same report from the same database snapshot.
- **Reusable.** Sections, metrics, thresholds, and action rules are config-driven so next month needs no code changes.
- **Honest.** Every metric has a definition and a caveat; interpretations and actions are clearly separated from raw facts.

## 2. Current state and constraints

- The old June 2026 PDF is 1.25 MB and is effectively a linear document. Finding one player or one comparison means scrolling or searching a PDF.
- The report month is derived as "the previous complete calendar month" from a reference date. The target report is **October 2026**, using data through **2026-10-31**.
- The database is SQLite (`user_activity.db`), read-only for reporting.
- The local DB on this machine is stale (ends **2026-07-18**). The production host `pdesjardins@10.0.0.181` has data through **2026-11-14** and must be snapshotted for the October report.
- One guild only (`1224166062581612574`), 236 known users, 216 ever voice-active, 152 with tracked matches.
- All configured time zones are US zones (156 Eastern, 51 Central, 29 Pacific).
- Ranked matches are the only match playlist stored (`session_type = 'Ranked'`).
- Match rows only include tracked users. `match_uuid` groups tracked users in the same match, but there is no stored team id.
- `match_timestamp` is the match end time. Match start must be derived from `match_duration_ms`.
- No `jinja2` dependency is present. HTML will be rendered with Python string/template helpers or an existing lightweight approach.
- Existing dependencies already include `matplotlib`, `numpy`, `pandas`, `networkx`, `plotly`, `pytz`, `tzdata`.

## 3. Design principles

1. **Facts before opinions.** Compute deterministic metrics first. Insights and actions are derived layers with visible evidence.
2. **Every number is traceable.** Each metric has an id, a definition, a source query, a window, and a caveat.
3. **No hidden "now".** All windows are computed from `--reference-date`; no metric silently depends on the machine clock.
4. **Neutral language.** "Playing outside server voice" is an observation, not an accusation. Many reasons are legitimate.
5. **Small-sample honesty.** Rates below a configurable sample size are flagged, not ranked as if reliable.
6. **Read-only reporting.** Queries only read; no schema changes are required.
7. **Offline-first.** Inline SVG charts and vanilla JS only. No CDN, no telemetry.
8. **Admin-only artifact.** It contains display names and behavioral inferences. It stays under `reports/` and is never posted publicly.

## 4. Data sources and semantics

| Table | Grain | Time axis | Use | Main traps |
|---|---|---|---|---|
| `user_info` | one row per Discord user | none | Identity, display name, Ubisoft names, time zone, max MMR | `display_name` is an alias; canonical player name is `COALESCE(ubisoft_username_active, ubisoft_username_max)` |
| `user_activity` | one event per user/channel | `timestamp` (UTC) | Voice sessions, concurrency, local-time patterns | `connect`/`disconnect` must be paired; unmatched disconnects and open sessions exist |
| `user_full_match_info` | one row per tracked user per match | `match_timestamp` = match end (UTC) | Ranked activity, server-vs-outside, performance | Only tracked users; `match_uuid` is not a team id; `is_rollback = 1` must be excluded; duration needed for match start |
| `user_full_stats_info` | one row per user | none | Lifetime context only | Snapshot, not time-filterable; only 128 users |
| `operator_stats` | one row per user/operator/playlist | `last_updated` | Lifetime operator context | Not a monthly history |
| `user_player_value` | one row per user/algorithm | `computed_at` | Skill/value context | Computed values, not ground truth; explain the algorithm |
| `archived_message` | one row per message | `created_at` | Engagement context | Includes bot/system/mod channels; exclude `moderator-audit` and bots for people metrics |
| `tournament`, `bet_*` | tournament/bet rows | various | Optional engagement context | Small samples; only include if useful |

### 4.1 Core definitions

**Voice session**

- Pair `connect` with the next `disconnect` for the same `(user_id, channel_id)`.
- Clip each session to the report window.
- Merge overlapping intervals per user before computing "in voice" or total user time.
- Count unmatched disconnects, open sessions at window end, and sessions over 12 hours in data quality.
- Rationale: the existing `data_access_fetch_win_rate_server` query pairs connects with `MIN(disconnect)` across all channels; that can mispair a user who switches channels or reconnects. The new report uses the more robust per-channel pairing and merge from `deps/monthly_report.py:336-368`, and documents the difference.

**Match window**

- A match occupies `[match_timestamp - match_duration_ms, match_timestamp]`.
- If duration is missing or zero, fall back to a point at `match_timestamp` and flag it.
- Use the match window, not the end timestamp, for overlap with voice. This is stricter and more accurate for long matches.

**In server voice vs outside**

- **In-server match**: the user's match window overlaps any merged voice interval for that user.
- **Outside match**: the user's match window overlaps no voice interval.
- Both counts are per user-match row. "Distinct matches" use `match_uuid`.

**Active user**

- Report separately: `voice_active_users`, `match_active_users`, `any_active_users`.
- Do not collapse them into one "active" number without a label.

**Local time**

- Convert UTC to `user_info.time_zone` with `zoneinfo.ZoneInfo` (DST-aware).
- Fall back to UTC when the zone is missing or invalid.
- Show both UTC and local labels in the methodology; aggregate patterns in local time.

**Partner / co-match**

- A "co-match" is another tracked user in the same `match_uuid`.
- A "likely teammate" additionally shares the same `has_win`.
- This is a heuristic, not a stored team relationship. Label it "co-match (likely teammate)" and state the limitation.
- "Outside partner" is a co-match in a match classified as outside for the selected user.

**Ranked scope**

- Default match analysis uses `LOWER(session_type) = 'ranked' AND is_rollback = 0`.
- Any standard/casual analysis must be explicitly labeled; no casual rows exist in the current snapshot.

### 4.2 Snapshot acquisition

The report must run against a consistent snapshot, not a live SQLite file with an active WAL.

Recommended process:

```bash
ssh pdesjardins@10.0.0.181 \
  'cd /home/pdesjardins/code/python-discord-scheduler-bot && \
   sqlite3 user_activity.db ".backup /tmp/gametime_snapshot_2026-11-01.db"'
scp pdesjardins@10.0.0.181:/tmp/gametime_snapshot_2026-11-01.db \
  ./user_activity_2026-11-01.db
```

Rules:

- Use `sqlite3 .backup` or `VACUUM INTO`; do not copy `user_activity.db`, `-wal`, and `-shm` while the bot is writing. The existing `analytics/transfer_db.sh` copies all three and can capture an inconsistent state.
- Keep the snapshot outside the report output and never commit it. Add the filename pattern to `.gitignore` if it is not already covered.
- Add `--database PATH` to the report CLI so the snapshot is explicit; default remains `user_activity.db` for normal local use.
- Verify before rendering: `MAX(timestamp) >= 2026-11-01` and `MAX(match_timestamp) >= 2026-11-01`. The report itself uses `end_exclusive = 2026-11-01`, so later data cannot leak into October.
- Record the snapshot max timestamp and row counts in the report's data-quality section.

## 5. Report windows

The report will compute these windows from one reference date:

| Key | Label | Start | End |
|---|---|---|---|
| `previous_month` | Previous Month | first day of previous calendar month | first day of current month |
| `previous_three_months` | Previous 3 Complete Months | first day 3 months before current | first day of current month |
| `year_to_date` | Year to Date | January 1 of previous month's year | first day of current month |
| `all_data` | All Tracked Data | first activity or first match | first day of current month |
| `last_28_days` | Last 28 Days (action window) | reference date − 28 days | reference date |

Rules:

- `--reference-date 2026-11-01` produces the October 2026 report.
- `--report-month 2026-10` can pin the report month directly and derive the reference date.
- ISO weeks start Monday, matching the existing weekly split query.
- The action window is explicitly separate from the report month so "who needs attention now" is not confused with "what happened in October".

## 6. Metric catalog

Each metric is implemented as a named function with a stable id, a definition, and a unit. The HTML shows the definition in a methodology appendix and on hover.

### 6.1 Community pulse

| Id | Metric | Definition / formula | Notes |
|---|---|---|---|
| `pulse.voice_users` | Voice-active users | distinct users with at least one clipped voice session | |
| `pulse.match_users` | Match-active users | distinct users with at least one ranked row | |
| `pulse.any_users` | Any active users | union of the two | label explicitly |
| `pulse.new_users` | New users | first-ever activity in window | "ever" means first row in `user_activity` |
| `pulse.returning_users` | Returning users | active in window after a gap of >= 28 days | |
| `pulse.churned_users` | Churned users | active in prior 28 days and absent in last 28 days | action window only |
| `pulse.voice_hours` | Voice hours | merged voice interval seconds / 3600 | |
| `pulse.sessions` | Voice sessions | count of paired, clipped sessions | |
| `pulse.median_session_minutes` | Median session | median clipped session minutes | |
| `pulse.match_rows` | Ranked match rows | count of user-match rows | |
| `pulse.distinct_matches` | Distinct matches | `COUNT(DISTINCT match_uuid)` | |
| `pulse.match_hours` | Match hours | sum of `match_duration_ms` / 3.6e6 | |
| `pulse.peak_concurrent` | Peak concurrent voice | max distinct users in voice at once | sweep line |
| `pulse.avg_concurrent` | Average concurrent voice | time-weighted mean concurrency | |
| `pulse.unique_users_per_day` | Unique users per day | distinct users with any voice that day | |
| `pulse.messages` | Human messages | non-bot, non-`moderator-audit` messages | optional |

### 6.2 Play patterns

| Id | Metric | Definition / formula | Notes |
|---|---|---|---|
| `pattern.weekday_hour_heatmap` | Weekday × hour activity | voice hours and match rows by local weekday/hour | two heatmaps: voice and matches |
| `pattern.weekend_share` | Weekend share | weekend voice hours / total voice hours | Sat/Sun local |
| `pattern.late_night_share` | Late-night share | voice hours 00:00–05:00 local / total | per user and aggregate |
| `pattern.session_length_hist` | Session length distribution | histogram of clipped session minutes | buckets: <15, 15–30, 30–60, 1–2h, 2–4h, 4h+ |
| `pattern.start_hour_hist` | Session start hour | local hour of session start | |
| `pattern.end_hour_hist` | Session end hour | local hour of session end | |
| `pattern.regularity` | Regularity score | normalized entropy of a user's weekly hours, or 1 − CV | define one and keep it stable |
| `pattern.streak_current` | Current streak | consecutive local days with >= 1 minute voice or >= 1 match | end at report window end |
| `pattern.streak_longest` | Longest streak | same, over all data | |
| `pattern.weekly_trend` | Weekly voice/match trend | ISO-week totals | sparkline |
| `pattern.monthly_trend` | Monthly voice/match trend | calendar-month totals | |
| `pattern.cohort_retention` | Cohort retention | first-seen month cohort × months since first seen | |
| `pattern.new_user_return` | New-user return rate | share of new users active again within 7/14/28 days | |

### 6.3 Server vs elsewhere (headline section)

| Id | Metric | Definition / formula | Notes |
|---|---|---|---|
| `split.voice_hours` | Voice hours | per user | |
| `split.match_rows` | Ranked rows | per user | |
| `split.in_rows` | In-server rows | matches whose window overlaps voice | |
| `split.out_rows` | Outside rows | matches whose window overlaps no voice | |
| `split.in_percent` | In-server share | `in_rows / match_rows` | |
| `split.out_percent` | Outside share | `out_rows / match_rows` | |
| `split.in_match_hours` | In-server match hours | sum of durations for in matches | |
| `split.out_match_hours` | Outside match hours | sum of durations for outside matches | |
| `split.outside_while_server_active` | Elsewhere while server is active | outside matches where >= N other users are in voice during the match window | N configurable, default 3 |
| `split.voice_only_hours` | Voice-only hours | voice hours with no match window | social/lurking |
| `split.match_only_hours` | Match-only hours | match hours with no voice overlap | |
| `split.ratio` | Match/voice ratio | match hours / voice hours | guard zero |
| `split.data_center_mix` | Data center mix | in vs outside match counts by `data_center` | context for "where" |
| `split.warmup_matches` | Before-first-connect matches | matches in the 60 min before the user's first voice connect that day | optional pattern |
| `split.after-disconnect_matches` | After-last-disconnect matches | matches in the 60 min after last disconnect | optional pattern |
| `split.in_win_rate` | In-server win rate | wins / in rows | flag n < 5 |
| `split.out_win_rate` | Outside win rate | wins / out rows | flag n < 5 |
| `split.in_rank_delta` | In-server rank points | sum `points_gained` for in rows | flag n < 5 |
| `split.out_rank_delta` | Outside rank points | sum `points_gained` for out rows | flag n < 5 |

### 6.4 People classifications

Assign each user one primary classification for the report month, plus flags:

| Classification | Rule (default) | Admin meaning |
|---|---|---|
| `core_in_server` | in_rows >= 5 and in_percent >= 60% | Plays ranked with the community |
| `mixed` | in_rows >= 3 and out_rows >= 3 | Splits time |
| `elsewhere_heavy` | out_rows >= 5 and out_percent >= 60% | Plays ranked mostly outside server voice |
| `voice_only` | voice_hours >= 4 and match_rows = 0 | Social/voice regular, no tracked ranked |
| `match_only` | match_rows >= 5 and voice_hours < 1 | Grinds ranked without voice |
| `new` | first activity in window | Needs welcome/integration |
| `inactive` | no voice and no match in window | Not active this month |

Thresholds live in `deps/reporting/config.py` and are shown in the methodology.

### 6.5 Social network

| Id | Metric | Definition | Notes |
|---|---|---|---|
| `social.co_voice_pairs` | Co-voice pairs | overlap seconds between two users' merged voice intervals | sweep/interval overlap |
| `social.co_match_pairs` | Co-match pairs | shared `match_uuid` count | likely teammate flag when same `has_win` |
| `social.combined_pairs` | Combined relationship | normalized co-voice + co-match | define weights in config |
| `social.top_pairs` | Top pairs | ranked by combined score | show hours/matches |
| `social.top_trios` | Top trios | cliques of 3 by combined score | optional |
| `social.degree` | Degree | number of partners above a minimum overlap | |
| `social.betweenness` | Betweenness | network centrality | identify bridges |
| `social.communities` | Communities | Louvain or greedy modularity | label members |
| `social.isolated` | Isolated regulars | voice >= 2h but <= 1 partner | action candidates |
| `social.new_connections` | New connections | pairs first seen together in window | |
| `social.lost_connections` | Lost connections | pairs active before, absent in window | |

### 6.6 Performance context (optional, label as context)

| Id | Metric | Definition | Notes |
|---|---|---|---|
| `perf.win_rate` | Win rate | wins / rows | flag n < 5 |
| `perf.kd` | K/D | kills / deaths | guard zero |
| `perf.rank_delta` | Rank points delta | sum `points_gained` | |
| `perf.rank_tier` | Rank tier | latest `rank_name` / `max_mmr` | |
| `perf.top_operators` | Operator pool | operator counts from `operators` | comma-split, case-insensitive |
| `perf.map_win_rate` | Map win rate | wins / rows by `map_name` | flag n < 5 |
| `perf.surrender_rate` | Surrender/forfeit rate | flags / rows | |
| `perf.disconnect_rounds` | Disconnect rounds | sum `round_disconnected_count` | |

### 6.7 Data quality

| Id | Metric | Definition | Action |
|---|---|---|---|
| `dq.unmatched_disconnects` | Unmatched disconnects | disconnect with no open connect in window | tracker issue |
| `dq.open_sessions` | Open sessions at window end | connects without disconnect | tracker issue |
| `dq.long_sessions` | Sessions > 12h | count | tracker issue |
| `dq.rollback_rows` | Rollback rows excluded | `is_rollback = 1` count | note only |
| `dq.missing_duration` | Missing match duration | null/zero duration | overlap uses point fallback |
| `dq.missing_timezone` | Missing time zone | blank/invalid `time_zone` | local-time analysis falls back to UTC |
| `dq.missing_ubisoft` | Missing Ubisoft name | both names null | identity gap |
| `dq.voice_only_users` | Voice-only users | no match rows ever | not an error |
| `dq.match_only_users` | Match-only users | no voice rows ever | not an error |
| `dq.stale_snapshot` | Snapshot staleness | latest data timestamp vs reference date | warn if > 7 days |
| `dq.duplicate_names` | Duplicate display names | count of duplicated display names | UI disambiguation |

## 7. Insight and action framework

### 7.1 Action object

Every action is a structured object so it can be rendered, filtered, exported, and tested:

```python
@dataclass(frozen=True)
class ActionItem:
    action_id: str
    priority: str          # P0, P1, P2
    category: str          # reengage, integrate, elsewhere, voice_only, match_only, celebrate, data, schedule, coaching
    user_ids: tuple[int, ...]
    headline: str
    evidence: tuple[str, ...]   # metric ids + human-readable values
    why_it_matters: str
    suggested_action: str
    message_template: str
    confidence: str        # high, medium, low
    caveats: tuple[str, ...]
```

Priority is computed from:

- **Impact**: how much activity/relationship is at stake (e.g., prior voice hours, matches).
- **Confidence**: sample size and signal strength.
- **Recency**: how recent the signal is.
- **Actionability**: whether an admin can reasonably do something.

Keep the formula simple and documented. Cap the visible list to the top N per category, with a "show all" toggle.

### 7.2 Action categories and default rules

**Re-engage at-risk regulars (`reengage`)**

- Prior 28 days voice >= 2h and current 14 days voice = 0.
- Or 4-week voice trend <= −50% and prior 4-week average >= 1h/week.
- Or last seen 14–28 days ago and historical weekly average >= 1h.
- Evidence: last seen, prior/current voice hours, prior rank in top users, matches trend.
- Suggested action: low-pressure check-in, ask about schedule, invite to the next event.
- Caveats: vacation, exams, time zone, life changes; do not assume disengagement.

**Integrate new members (`integrate`)**

- First activity in window and <= 14 days since first activity.
- Evidence: first seen, voice hours, distinct voice partners, matches with community members, whether they returned after 7 days.
- Suggested action: welcome message, introduce to a similar-time regular, invite to a low-stakes session.

**Bring elsewhere players into server (`elsewhere`)**

- `out_rows >= 5` and `out_percent >= 60%` and voice hours >= 1.
- Boost priority when `outside_while_server_active >= 3`.
- Evidence: in/out rows, outside hours, outside partners, data centers, times, whether in-server win rate differs.
- Suggested action: neutral question about schedule/stack; offer a specific in-server night that matches their play times.
- Caveats: they may have another group, prefer solo queue, or play at different hours. This is not a rule violation.

**Activate voice-only members (`voice_only`)**

- `voice_hours >= 4` and `match_rows = 0`.
- Evidence: voice hours, top co-voice partners, active hours, whether they have Ubisoft/match data.
- Suggested action: invite to a casual stack, ask if they want their matches tracked, pair with a patient regular.

**Activate match-only members (`match_only`)**

- `match_rows >= 5` and `voice_hours < 1`.
- Evidence: match rows, match hours, usual play times, data center.
- Suggested action: invite to voice for the next session, explain the social side, ask what would make voice worthwhile.

**Celebrate and reinforce (`celebrate`)**

- Streak >= 14 days.
- Top 3 voice hours.
- Biggest rank gain (with sample guard).
- Most improved win rate (with sample guard).
- Top connector (betweenness) or top pair.
- Suggested action: shoutout, thank-you, or invite to help welcome new members.

**Fix data (`data`)**

- Any `dq.*` threshold breach.
- Suggested action: check tracker reconnects, fix open sessions, fill missing time zones or Ubisoft names, refresh stale snapshot.

**Schedule events (`schedule`)**

- Identify the top 3 local weekday/hour slots by voice hours and match rows.
- Identify underserved but historically active slots.
- Identify groups of 4–5 users with compatible times and complementary roles/ranks.
- Suggested action: propose a specific event time and invite list.

**Performance coaching (`coaching`)**

- Rank decline over >= 10 matches, map/operator weakness with n >= 10, disconnect rounds.
- Suggested action: offer a review, share map/operator stats, pair with a stronger player.
- Caveats: performance is context, not a judgment; avoid public comparison.

### 7.3 Message templates

Templates are editable in `deps/reporting/templates.py` and rendered with safe placeholders. The report shows a copy button, not an auto-send.

Examples:

- Re-engage: "Hey {name}, we missed you in {month}. You were one of our top {n} voice regulars in {prior_month}. Is there a night that works better for you? We're planning {event} on {day}."
- New: "Welcome {name}! I saw you in {channel}. If you want, {buddy} usually plays around {time} — happy to introduce you."
- Elsewhere: "Hey {name}, I noticed you play a lot of ranked outside the server. No pressure at all — is it a schedule or stack thing? We're trying to make in-server nights work better, and your input would help."
- Voice-only: "You're a regular in voice — want to join the next ranked stack? No pressure, casual is fine too."
- Match-only: "You're grinding ranked — hop in voice sometime so we can squad up. Even just listening is fine."
- Celebrate: "Shoutout to {name} for a {n}-day streak and {hours} voice hours this month."
- Data: "We have {n} unmatched disconnects in {month}. If your tracker reconnects often, that may be why some sessions look short."
- Schedule: "Peak availability is {day} around {time}. Want to run {event} then?"

Rules:

- Use display names exactly as stored, escaped for HTML.
- Include `<@user_id>` only in the copyable text, not in the visible headline.
- Never imply the admin has already decided to confront someone.
- No mental-health, identity, or other sensitive speculation.

### 7.4 Executive brief

The first screen after the cover shows:

- 5 headline numbers with month-over-month deltas.
- 5 findings, each with a metric id and a one-line "so what".
- 5 actions, each with a priority and a link to the full action.
- One data-quality warning if the snapshot is stale or coverage is poor.

## 8. HTML information architecture

One file: `reports/monthly/2026-10/gametime_report_2026-10.html` (or the configured output).

### 8.1 Layout

- **Left sidebar** (sticky, collapsible on mobile): grouped navigation.
- **Top bar**: report month, reference date, window selector, search, print button.
- **Main content**: sections with anchor ids.
- **Right-side detail panel** (optional): opens when a person or action is selected.
- **Footer**: methodology, data range, generated timestamp, "single-file, no external requests".

### 8.2 Sections

1. **Cover / Snapshot** — month, generated time, data range, 6 headline cards, data-quality badge.
2. **Executive Brief** — top findings and top actions.
3. **Community Pulse** — active users, voice hours, matches, messages, concurrency, trends.
4. **Play Patterns** — weekday/hour heatmaps, session lengths, streaks, cohorts, local-time insights.
5. **Server vs Elsewhere** — the headline analysis: split cards, per-user scatter, outside-while-active list, data center mix, win-rate comparison.
6. **People Directory** — sortable/searchable table with classification, voice, matches, in/out, last seen, flags; click a row for a profile.
7. **Player Profiles** — per-user detail: summary, voice/match timeline, weekday/hour heatmap, partners, in/out split, trend, actions.
8. **Social Graph** — top pairs, communities, bridges, isolated regulars, new/lost connections.
9. **Performance Context** — optional aggregate and per-user context, clearly labeled.
10. **Action Center** — all actions, grouped by category, filterable by priority and person; copyable message templates.
11. **Data Quality & Methodology** — definitions, caveats, exclusions, known limitations.
12. **Appendix** — full tables, metric definitions, query notes, change log.

### 8.3 Navigation behavior

- Sidebar links use anchors and scroll smoothly; active section is highlighted with `IntersectionObserver` or a scroll handler.
- A search box filters the people table and action list live.
- Window selector toggles sections for `previous_month`, `previous_three_months`, `year_to_date`, `all_data`, and `last_28_days`. Use one set of sections and show/hide by `data-window` so the file stays small.
- Person profile opens in a panel; a URL hash (`#person-<id>`) makes it linkable.
- "Back to top" and "previous/next section" controls.
- Keyboard: `/` focuses search, `Esc` closes panels, arrow keys move between sections.
- Print stylesheet: hide sidebar/top bar, show all sections, avoid breaking cards and tables.

### 8.4 Charts

- **Inline SVG generated in Python.** No JS chart library, no CDN.
- Chart types: bar, line, stacked bar, scatter, heatmap, distribution, timeline, network, small multiples.
- Every chart has:
  - a title and subtitle with the metric window,
  - axis labels and units,
  - a `<title>` tooltip for each mark where practical,
  - a fallback `<details><table>` with the underlying values,
  - a caption stating the definition and caveat.
- Color:
  - Reuse the navy/orange palette and validated categorical colors from `deps/monthly_report_style.py`.
  - In-server = green, outside = red, neutral = navy.
  - Sequential blue ramp for heatmaps.
  - Never rely on color alone; use labels/patterns.
- Network graph:
  - Cap to the top N users by combined activity for legibility (default 60); full pair table remains available.
  - Node size = voice hours; edge width = combined relationship strength.
  - Color = classification or community; legend explains.
  - Provide a "top pairs" table as the accessible fallback.

### 8.5 Tables

- Sticky header, sortable columns, search filter.
- Numeric columns right-aligned; percentages with one decimal; hours with one decimal.
- Flags as text badges, not color-only.
- Small-sample badge (`n=3`) on rates.
- Row click opens the person panel; a separate "copy mention" button.

### 8.6 Single-file mechanics

- Inline `<style>` and `<script>`; no `src`/`href` to external origins.
- Inline SVG; no `<img>` to files.
- Embed a JSON data block for JS filtering if needed, but keep the primary content as server-rendered HTML so it works without JS.
- Escape all user-controlled text with `html.escape`.
- Validate that the output contains no `http://` or `https://` resource references (except harmless text links in methodology, if any; preferably none).
- Target file size: under 10 MB, ideally 3–6 MB for a month with 60 users and 4 windows.

## 9. Architecture

New package: `deps/reporting/`

```text
deps/reporting/
  __init__.py
  config.py          # thresholds, defaults, section registry
  models.py          # dataclasses for windows, sessions, metrics, people, actions
  windows.py         # report windows, ISO weeks, local-time helpers
  queries.py         # read-only SQL, parameterized
  sessions.py        # pairing, clipping, merging, overlap, concurrency
  metrics.py         # aggregate and per-user metrics
  patterns.py        # heatmaps, streaks, cohorts, session distributions
  split.py           # server-vs-outside classification and metrics
  social.py          # co-voice/co-match pairs, network metrics
  performance.py     # optional performance context
  insights.py        # classifications, findings, data-quality checks
  actions.py         # action rules, prioritization, templates
  templates.py       # message templates
  charts.py          # inline SVG primitives
  html.py            # page rendering, CSS, JS, navigation
scripts/
  generate_analytics_report.py
tests/
  reporting_sessions_unit_test.py
  reporting_metrics_unit_test.py
  reporting_split_unit_test.py
  reporting_actions_unit_test.py
  reporting_html_unit_test.py
  reporting_integration_test.py
```

Design notes:

- Keep `deps/monthly_report.py` and the PDF path working. Do not refactor it in the first pass.
- Reuse `deps/monthly_report_style.py` colors and `deps/analytic_functions.py` overlap helpers where they fit, but do not inherit the PDF's SQL quirks.
- `queries.py` returns plain rows or small dataclasses; no HTML concerns.
- `metrics.py` and `split.py` are pure functions over fetched data so they are easy to unit test.
- `html.py` receives a fully computed `ReportData` object; it does no SQL.
- `config.py` is the only place thresholds and section toggles live.

CLI:

```bash
uv run python scripts/generate_analytics_report.py \
  --reference-date 2026-11-01 \
  --database user_activity.db \
  --output-dir reports/monthly
```

Options:

- `--reference-date YYYY-MM-DD`
- `--report-month YYYY-MM` (alternative pin)
- `--database PATH` (default `user_activity.db`; use the November snapshot for October)
- `--output-dir PATH` (default `reports/monthly`)
- `--window KEY` (repeatable; default all)
- `--no-ai`
- `--format html|pdf|both` (default `html`)
- `--open` (open the file with the OS handler)
- `--config PATH` (threshold overrides)
- `--strict` (fail on data-quality thresholds instead of warning)

Add a `make report-html` target with the reference date as a variable, or document the direct command in README. Do not change the existing `make` targets.

### 9.1 Config example

```python
# deps/reporting/config.py
DEFAULT_TOP_USERS = 25
NETWORK_NODE_LIMIT = 60
SMALL_SAMPLE_THRESHOLD = 5
LATE_NIGHT_HOURS = (0, 5)          # local time, end-exclusive
SESSION_LONG_HOURS = 12
ELSEWHERE_MIN_OUT_ROWS = 5
ELSEWHERE_MIN_OUT_PERCENT = 60.0
ELSEWHERE_ACTIVE_SERVER_THRESHOLD = 3
AT_RISK_PRIOR_VOICE_HOURS = 2.0
AT_RISK_CURRENT_DAYS = 14
AT_RISK_LOOKBACK_DAYS = 28
NEW_USER_DAYS = 14
STREAK_MIN_DAYS = 14
MIN_EDGE_CO_VOICE_MINUTES = 30
MIN_EDGE_CO_MATCHES = 2
ACTION_LIMITS = {
    "reengage": 10,
    "integrate": 10,
    "elsewhere": 10,
    "voice_only": 8,
    "match_only": 8,
    "celebrate": 8,
    "data": 5,
    "schedule": 3,
    "coaching": 5,
}
SECTIONS = [
    "cover", "brief", "pulse", "patterns", "split",
    "people", "social", "performance", "actions", "methodology", "appendix",
]
```

The CLI `--config` accepts a JSON file with the same keys and overrides these values for one run.

## 10. Algorithm details and SQL sketches

### 10.1 Voice sessions

```sql
SELECT user_id, channel_id, event, timestamp
FROM user_activity
WHERE julianday(timestamp) < julianday(:end)
ORDER BY user_id, channel_id, julianday(timestamp), id;
```

Pair in Python per `(user_id, channel_id)`, clip, then merge per user. This avoids the cross-channel mispairing risk in the older query. Count unmatched disconnects and open sessions as data quality.

### 10.2 Concurrent voice

- Build events: `(start, +1, user_id)` and `(end, -1, user_id)`.
- Sort by timestamp; maintain a set of active users.
- Peak = max set size; average = time-weighted integral.
- For "outside while server active", precompute a concurrency timeline and query it at each match window; count other users (exclude the player).

### 10.3 Match windows and split

```sql
SELECT user_id, match_uuid, match_timestamp, match_duration_ms, has_win,
       data_center, points_gained, rank_name, map_name, operators,
       round_disconnected_count, is_surrender, is_forfeit
FROM user_full_match_info
WHERE julianday(match_timestamp) >= julianday(:start)
  AND julianday(match_timestamp) < julianday(:end)
  AND LOWER(session_type) = 'ranked'
  AND is_rollback = 0;
```

Then per row:

```text
match_start = match_timestamp - duration (if duration > 0 else match_timestamp)
in_server = any(session.start <= match_timestamp and session.end >= match_start
                for session in merged_sessions[user_id])
```

Use a small configurable tolerance (default 0 minutes) for clock skew; do not hide it.

### 10.4 Co-voice pairs

- For each user, merged intervals sorted by start.
- Sweep users by interval start; for each pair with overlap, add overlap seconds.
- Complexity can be O(n²) in the worst case; with <= 236 users and <= 1 month it is fine. For all-data, cap to active users in the window and use a sweep line.
- Store pairs in a dict keyed by `(min_id, max_id)`.

### 10.5 Co-match pairs

```sql
SELECT match_uuid, user_id, has_win
FROM user_full_match_info
WHERE julianday(match_timestamp) >= julianday(:start)
  AND julianday(match_timestamp) < julianday(:end)
  AND LOWER(session_type) = 'ranked'
  AND is_rollback = 0;
```

Group by `match_uuid`; for each pair of users in the group, increment co-match count. Mark `likely_teammate` when `has_win` matches. Do not claim it is a team.

### 10.6 Streaks

- Build the set of local dates with activity.
- Current streak: walk backward from the report window end (or last active date) while consecutive.
- Longest streak: scan the sorted set.
- Define activity as voice >= 1 minute or match row >= 1; keep the definition in config.

### 10.7 Cohorts and retention

- First-seen month = month of the user's first `user_activity` row (or first match, with a separate label).
- Cohort retention for month `m + k` = share of cohort active in that month.
- Suppress cells with cohort size < 3.

### 10.8 Local time

- `zoneinfo.ZoneInfo(user.time_zone)`; fall back to UTC with a data-quality count.
- Convert each session start/end to local for hour buckets; split sessions that cross an hour boundary.
- For heatmaps, assign each hour segment to its local weekday/hour.
- Show the time zone distribution in methodology.

### 10.9 Network metrics

- Use `networkx` for degree, betweenness, and community detection.
- Build an undirected weighted graph from co-voice/co-match pairs.
- Filter edges below a configurable minimum (e.g., 30 minutes co-voice or 2 co-matches) to avoid noise.
- Label communities by their top 3 members, not by an opaque id.

## 11. Implementation phases

### Phase 0 — Approve plan and scope

- Confirm report month (default: **October 2026**, reference date **2026-11-01**).
- Confirm the snapshot source and that data through 2026-10-31 is available.
- Confirm output path and whether to keep the PDF.
- Confirm action tone and thresholds.
- Confirm whether the AI narrative is included (already requested: yes, grounded and validated).

### Phase 1 — Data layer and deterministic metrics

- Add `deps/reporting/` models, windows, queries, sessions, metrics.
- Implement community pulse, play patterns, server-vs-outside, data quality.
- Add unit tests with hand-computed fixtures.
- Add an integration test against the test database.
- Acceptance: October 2026 metrics reconcile with an independent remote query (active users, voice hours, ranked rows, distinct matches) or differences are explained; a JSON dump is stable. The old June PDF remains a secondary validation fixture for the metric engine.

### Phase 2 — Insights and actions

- Add classifications, findings, and action rules.
- Add templates and priority calculation.
- Add tests for thresholds, deduplication, and priority.
- Acceptance: the action list is sensible, evidence-backed, and not duplicate-heavy; the admin can copy a message.

### Phase 3 — HTML rendering

- Add SVG chart primitives and the HTML shell.
- Add sidebar navigation, window switching, search, person panel, tables, print styles.
- Add HTML tests: escaping, unique anchors, valid embedded JSON, no external resource references, all nav targets exist.
- Acceptance: one file, opens offline, all sections reachable in <= 2 clicks, no console errors.

### Phase 4 — Polish and reuse

- Add CLI, config overrides, docs, and a Makefile target.
- Add the grounded AI narrative (requested) with strict validation and a deterministic fallback.
- Generate the October 2026 report and review it with the admin.
- Acceptance: the admin finds a person or an action in under 30 seconds; the report is useful enough to run monthly.

### Phase 5 — Monthly operation

- Document the monthly command and data refresh steps.
- Optional: systemd timer or cron after data transfer.
- Keep previous months under `reports/monthly/<YYYY-MM>/`.
- Add a small index page or README in `reports/`? Optional; the user asked for one HTML per month.

## 12. Validation and acceptance criteria

- **Reconciliation:** October 2026 `voice_active_users = 35`, `voice_hours ≈ 581.0`, `ranked_rows = 1158`, `distinct_matches = 648`, `match_users = 32`, `outside_share ≈ 49.7%` using the definitions above. Differences from any independent query must be explained in the methodology (match-window vs point overlap, session pairing).
- **Reproducibility:** two runs with the same reference date and DB produce the same HTML content (timestamps aside).
- **Single file:** no external network requests; no missing images/fonts; works from `file://`.
- **Navigation:** every section and every person is reachable; back/forward hash links work.
- **Action quality:** each action has an id, priority, evidence, suggested action, template, confidence, and caveats.
- **Data quality:** unmatched disconnects, open sessions, stale snapshot, missing time zone, and missing duration are surfaced.
- **Accessibility:** semantic headings, table headers, focus styles, keyboard search, color-independent labels.
- **Performance:** generation under 30 seconds for the full data set; HTML loads under 2 seconds locally; file size under 10 MB.
- **Quality gates:** `make unit-test`, `make lint-black`, `make lint-mypy`, and relevant pylint checks pass.

## 13. Reuse checklist

- **New month:** run the CLI with a new `--reference-date`; no code changes.
- **New window:** add a `ReportWindow` in `windows.py` and a config entry; the renderer shows it automatically.
- **New metric:** add a query/function in `metrics.py`, a definition in the metric registry, a section entry, and a unit test.
- **New action rule:** add a rule in `actions.py`, a template in `templates.py`, a threshold in `config.py`, and a test.
- **Threshold change:** edit `config.py` or pass `--config`; no renderer changes.
- **New chart:** add a function in `charts.py`; charts are plain SVG strings and do not depend on a JS library.
- **New data source:** add a table spec in `deps/ai/data_catalog.py` and a query module; keep the report read-only.
- **PDF still needed:** keep `scripts/generate_monthly_report.py` unchanged; the new path is additive.

## 14. Risks and open questions

- **Snapshot staleness:** the local DB ends 2026-07-18. October requires a fresh snapshot from the production host (currently through 2026-11-14). The report must show a staleness badge and the snapshot max timestamp. Use `sqlite3 .backup`, not a live file copy.
- **Only three time zones:** local-time patterns are reliable for US users but not generalizable.
- **Tracked-user bias:** match data only includes users the bot tracks. "Outside" means outside guild voice, not outside the community.
- **Teammate inference:** co-match + same result is a heuristic; label it.
- **Small samples:** many users have few matches. Rates below 5 are flagged, and rankings should not overstate them.
- **Tone:** "elsewhere" can feel accusatory. Use neutral wording and offer the admin editable templates.
- **AI narrative:** included, but must be grounded. Pass only computed metric ids/values; validate every number against the data; fall back to deterministic text. `--no-ai` remains available. No AI in the action rules.
- **File size:** many SVG charts can grow the file. Cap the network graph, use small multiples, and lazy-render heavy sections with `<details>` if needed.
- **Existing query quirks:** do not copy the old `MIN(disconnect)` session pairing. Document why the new pairing differs.
- **Privacy:** the report contains behavioral inferences. Keep it admin-only under `reports/` (gitignored).

## 15. Initial October 2026 findings to validate the plan

These are from the production snapshot (queried remotely, data through 2026-11-14) with the proposed definitions. They are not the final report, but they show the plan is grounded:

- 35 voice-active users, 365 clipped sessions, 581.0 voice hours.
- 32 users with ranked rows, 1,158 ranked rows, 648 distinct matches, 530.5 match hours.
- 583 in-server rows (50.3%) vs 575 outside rows (49.7%); 273.3 in-server match hours vs 257.2 outside match hours.
- Peak concurrent voice: 11 users on 2026-10-31 02:15 UTC.
- 18 unique voice users on the busiest day (2026-10-18); 107 ranked rows in one day (2026-10-18).
- 1 new user in October; 377 human messages (excluding bots and `moderator-audit`).
- Median session 64 minutes; p90 4.1 hours; longest 9.2 hours.
- 14 open sessions at the October window end; 0 unmatched disconnects inside October.
- Month-over-month: September 2026 had 42 voice users, 527.1 voice hours, 1,147 ranked rows, 46.7% outside; October has fewer voice users and more outside share.
- Year-over-year: October 2025 had 38 voice users, 739.4 voice hours, 1,281 ranked rows, 41.2% outside; October 2026 is smaller and more outside-heavy.
- All-time: 64 voice-only users; 0 users with matches but no voice.
- Production snapshot max: 2026-11-14. The report ends at 2026-11-01 exclusive.

## 16. Decision log

- 2026-11-14: Chosen HTML over PDF because navigation and per-person lookup are the main pain points.
- 2026-11-14: Chosen inline SVG over a JS chart library to keep the file self-contained and small.
- 2026-11-14: Chosen robust per-channel session pairing over the older cross-channel `MIN(disconnect)` query.
- 2026-11-14: Chosen match-window overlap (start derived from duration) over end-timestamp-only overlap.
- 2026-11-14: Chosen neutral "outside server voice" wording; actions are suggestions, not verdicts.
- 2026-11-14: Core report is deterministic; AI narrative is optional and grounded.
- 2026-11-14: Target changed from June 2026 to October 2026 (data through 2026-10-31), per admin request.
- 2026-11-14: Snapshot must come from the production host via `sqlite3 .backup`, because the local DB ends 2026-07-18.
- 2026-11-14: AI narrative confirmed as included, grounded and validated.
- 2026-11-14: Profiles render for every active user, not only a fixed top N, so every people-directory link resolves.
- 2026-11-14: Network graph keeps up to 60 nodes and 90 edges for legibility.
- 2026-11-14: AI narrative calls OpenAI directly from the reporting package, so generating a report never imports bot database code or runs migrations.

## 17. Implementation notes (October 2026)

- Command: `.venv/bin/python scripts/generate_analytics_report.py --reference-date 2026-11-01 --database user_activity.db`
- Reusable target: `make report-html REFERENCE_DATE=2026-11-01 DATABASE=user_activity.db`
- Output: one file, no external requests, no duplicate anchors, no missing anchor targets.
- Validated October metrics: 35 voice users, 581.0 voice hours, 365 sessions, 32 match users, 1,158 ranked rows, 648 distinct matches, 583 in-server rows (50.3%), 575 outside rows (49.7%), 118 outside matches while 3+ others were in voice, 377 human messages.
- The report contains 12 sections, 20 capped actions, 37 linkable profiles, and a grounded AI narrative with a deterministic fallback.
- Data-quality note: the snapshot includes rows through 2026-11-14, but every window ends at 2026-11-01 exclusive; later rows do not leak into October.

## 18. Implementation checklist (completed)

- [x] Report month and reference date: **October 2026 / 2026-11-01**.
- [x] Snapshot source: production host `pdesjardins@10.0.0.181`, refreshed with `sqlite3 .backup`.
- [x] Output path: `reports/monthly/2026-10/gametime_report_2026-10.html`.
- [x] Existing PDF generator untouched.
- [x] Action center with copyable message and mention buttons.
- [x] Default action thresholds applied, with per-category caps.
- [x] AI narrative included with grounded validation and deterministic fallback.
- [x] All active users have linkable profiles; network node limit 60, edge limit 90.
- [x] Unit tests for sessions, metrics, actions, and HTML; mypy and black checks pass.
