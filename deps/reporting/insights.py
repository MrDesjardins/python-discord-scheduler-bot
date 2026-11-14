"""Classifications, action rules, and narrative generation for the HTML report."""

from __future__ import annotations

import os
import re
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from deps.reporting.models import ActionItem, UserInfo, UserMetrics, WindowMetrics

SMALL_SAMPLE = 5
AT_RISK_PRIOR_HOURS = 2.0
ELSEWHERE_MIN_ROWS = 5
ELSEWHERE_MIN_PERCENT = 60.0
VOICE_ONLY_MIN_HOURS = 4.0
MATCH_ONLY_MIN_ROWS = 5
ACTION_LIMITS = {
    "reengage": 10,
    "integrate": 10,
    "elsewhere": 10,
    "voice_only": 8,
    "match_only": 8,
    "celebrate": 6,
    "data": 8,
    "schedule": 3,
    "coaching": 5,
}


def _hours(seconds: float) -> str:
    return f"{seconds / 3600.0:.1f}"


def _month_label(window: WindowMetrics) -> str:
    return window.window.start.strftime("%B %Y")


def _top_names(users: list[UserMetrics], limit: int = 3) -> str:
    return ", ".join(user.display_name for user in users[:limit])


def _existing_user(user: Optional[UserMetrics], users: dict[int, UserInfo]) -> str:
    if user is not None:
        return user.display_name
    return "Unknown"


def build_actions(window: WindowMetrics, users: dict[int, UserInfo]) -> list[ActionItem]:
    """Create evidence-backed admin actions for one report window."""
    actions: list[ActionItem] = []
    month = _month_label(window)
    for user in window.users:
        if user.voice_seconds == 0 and user.match_rows == 0:
            continue
        prior_hours = user.prior_28d_voice_seconds / 3600.0
        if "at_risk" in user.flags and prior_hours >= AT_RISK_PRIOR_HOURS:
            priority = "P0" if prior_hours >= 5 else "P1"
            actions.append(
                ActionItem(
                    action_id=f"reengage:{user.user_id}",
                    priority=priority,
                    category="reengage",
                    user_ids=(user.user_id,),
                    headline=f"Check in with {user.display_name}",
                    evidence=(
                        f"{prior_hours:.1f}h voice in the prior 28 days",
                        "0h voice in the last 14 days",
                        f"Last seen {user.last_seen.date().isoformat() if user.last_seen else 'unknown'}",
                    ),
                    why_it_matters="A recent regular disappeared from voice; early outreach is usually easier than re-onboarding later.",
                    suggested_action="Send a low-pressure check-in, ask whether their schedule changed, and invite them to the next session that matches their old play times.",
                    message=(
                        f"Hey {user.display_name}, we missed you in {month}. "
                        f"You had about {prior_hours:.0f}h in voice the month before, so it stood out when you went quiet. "
                        "Is there a night that works better for you? We're planning something soon and I'd like you there."
                    ),
                    confidence="high" if prior_hours >= 5 else "medium",
                    caveats=("Vacation, exams, work, or a time-zone change can explain this.",),
                    impact=int(prior_hours * 10),
                )
            )
        if user.first_seen and window.window.start <= user.first_seen < window.window.end_exclusive:
            actions.append(
                ActionItem(
                    action_id=f"integrate:{user.user_id}",
                    priority="P1",
                    category="integrate",
                    user_ids=(user.user_id,),
                    headline=f"Welcome and integrate {user.display_name}",
                    evidence=(
                        f"First seen {user.first_seen.date().isoformat()}",
                        f"{user.voice_hours:.1f}h voice, {user.match_rows} ranked rows",
                        f"{len(user.top_voice_partners)} voice partners",
                    ),
                    why_it_matters="A new member's first weeks decide whether they become a regular.",
                    suggested_action="Send a welcome message, introduce them to one regular who plays at the same time, and invite them to a low-stakes session.",
                    message=(
                        f"Welcome {user.display_name}! I saw you around in {month}. "
                        "If you want, I can introduce you to someone who usually plays around your time. "
                        "No pressure at all."
                    ),
                    confidence="high",
                    caveats=(),
                    impact=int(user.voice_hours * 5) + 10,
                )
            )
        outside_rows = user.out_rows
        if (
            outside_rows >= ELSEWHERE_MIN_ROWS and user.out_percent >= ELSEWHERE_MIN_PERCENT and user.voice_hours >= 1
        ) or user.outside_while_active >= 3:
            priority = "P1" if user.outside_while_active >= 3 or user.out_hours >= 20 else "P2"
            evidence = [
                f"{outside_rows} ranked rows outside server voice ({user.out_percent:.0f}%)",
                f"{user.out_hours:.1f}h outside vs {user.in_hours:.1f}h in server voice",
            ]
            if user.outside_while_active:
                evidence.append(f"{user.outside_while_active} outside matches while 3+ others were in voice")
            if user.top_outside_partners:
                names = ", ".join(name for name, _ in user.top_outside_partners[:3])
                evidence.append(f" Frequent outside co-matches: {names}")
            actions.append(
                ActionItem(
                    action_id=f"elsewhere:{user.user_id}",
                    priority=priority,
                    category="elsewhere",
                    user_ids=(user.user_id,),
                    headline=f"Ask {user.display_name} about playing elsewhere",
                    evidence=tuple(evidence),
                    why_it_matters="They are active and playing ranked, but not in the community voice channels. A schedule or stack mismatch is fixable.",
                    suggested_action="Ask neutrally about their schedule or stack, then offer one specific in-server night that matches their usual play time.",
                    message=(
                        f"Hey {user.display_name}, I noticed you play a lot of ranked outside the server. "
                        "No pressure at all - is it a schedule or stack thing? "
                        "We're trying to make in-server nights work better, and your input would help."
                    ),
                    confidence="high" if user.outside_while_active >= 3 else "medium",
                    caveats=("They may have another group, prefer solo queue, or play at different hours.",),
                    impact=outside_rows + user.outside_while_active * 5,
                )
            )
        if user.match_rows == 0 and user.voice_hours >= VOICE_ONLY_MIN_HOURS:
            actions.append(
                ActionItem(
                    action_id=f"voice_only:{user.user_id}",
                    priority="P2",
                    category="voice_only",
                    user_ids=(user.user_id,),
                    headline=f"Invite {user.display_name} into a game",
                    evidence=(
                        f"{user.voice_hours:.1f}h voice",
                        "0 tracked ranked rows this window",
                        "Top voice partners: " + (", ".join(name for name, _ in user.top_voice_partners[:3]) or "none"),
                    ),
                    why_it_matters="They already spend time with the community; a low-pressure invite can turn voice presence into shared play.",
                    suggested_action="Invite them to a casual stack or ask whether they want their matches tracked.",
                    message=(
                        f"You're a regular in voice, {user.display_name} - want to join the next ranked stack? "
                        "Casual is completely fine too."
                    ),
                    confidence="medium",
                    caveats=("They may not play Siege, may play on another account, or may prefer voice-only.",),
                    impact=int(user.voice_hours * 5),
                )
            )
        if user.match_rows >= MATCH_ONLY_MIN_ROWS and user.voice_hours < 1:
            actions.append(
                ActionItem(
                    action_id=f"match_only:{user.user_id}",
                    priority="P2",
                    category="match_only",
                    user_ids=(user.user_id,),
                    headline=f"Invite {user.display_name} into voice",
                    evidence=(
                        f"{user.match_rows} ranked rows",
                        f"{user.match_hours:.1f}h match time",
                        f"{user.voice_hours:.1f}h voice",
                    ),
                    why_it_matters="They are grinding ranked without the social layer; voice is the easiest bridge into the community.",
                    suggested_action="Invite them to join voice for one session and ask what would make voice worth it.",
                    message=(
                        f"You're grinding ranked, {user.display_name} - hop in voice sometime so we can squad up. "
                        "Even just listening is fine."
                    ),
                    confidence="medium",
                    caveats=("Some players deliberately keep voice off; respect that.",),
                    impact=user.match_rows,
                )
            )
    # Celebrate positive signals.
    top_voice = [user for user in window.users if user.voice_hours > 0][:3]
    if top_voice:
        actions.append(
            ActionItem(
                action_id="celebrate:top_voice",
                priority="P2",
                category="celebrate",
                user_ids=tuple(user.user_id for user in top_voice),
                headline="Recognize the voice regulars",
                evidence=tuple(f"{user.display_name}: {user.voice_hours:.1f}h voice" for user in top_voice),
                why_it_matters="Public recognition reinforces the behavior that keeps the community alive.",
                suggested_action="Give a shoutout in the community channel and thank them for showing up.",
                message=f"Shoutout to {_top_names(top_voice)} for carrying voice this month. Thank you for showing up.",
                confidence="high",
                caveats=(),
            )
        )
    rank_gainers = [
        user
        for user in window.users
        if user.match_rows >= SMALL_SAMPLE and (user.in_rank_delta + user.out_rank_delta) > 0
    ]
    rank_gainers.sort(key=lambda user: -(user.in_rank_delta + user.out_rank_delta))
    if rank_gainers:
        user = rank_gainers[0]
        gain = user.in_rank_delta + user.out_rank_delta
        actions.append(
            ActionItem(
                action_id=f"celebrate:rank:{user.user_id}",
                priority="P2",
                category="celebrate",
                user_ids=(user.user_id,),
                headline=f"Recognize {user.display_name}'s rank climb",
                evidence=(f"+{gain} rank points over {user.match_rows} ranked rows",),
                why_it_matters="Visible progress is worth celebrating and encourages others to play together.",
                suggested_action="Congratulate them publicly and ask what changed in their game.",
                message=f"Big climb from {user.display_name}: +{gain} rank points this month. Nice work!",
                confidence="medium",
                caveats=("Rank points fluctuate; this is a snapshot, not a skill verdict.",),
            )
        )
    # Data quality actions.
    dq = window.data_quality
    if dq.stale_days > 7:
        actions.append(
            ActionItem(
                action_id="data:stale",
                priority="P1",
                category="data",
                user_ids=(),
                headline="Refresh the analytics snapshot",
                evidence=(f"Latest activity is {dq.stale_days} days before the report date",),
                why_it_matters="Stale data makes recent activity and churn signals unreliable.",
                suggested_action="Transfer a fresh snapshot from the production host before acting on recency-based items.",
                message="The analytics database is stale. Refresh the snapshot before using the action list.",
                confidence="high",
                caveats=(),
            )
        )
    for key, label, detail in (
        ("unmatched_disconnects", "unmatched disconnect events", "Check tracker reconnects and voice event pairing."),
        (
            "open_sessions_at_end",
            "voice sessions still open at the window end",
            "Check the tracker for missing disconnect events.",
        ),
        ("long_sessions", "voice sessions longer than 12 hours", "Check for a missing disconnect event."),
        (
            "missing_duration_rows",
            "ranked rows without match duration",
            "Match overlap uses a point-in-time fallback for these rows.",
        ),
    ):
        value = getattr(dq, key)
        if value:
            actions.append(
                ActionItem(
                    action_id=f"data:{key}",
                    priority="P2",
                    category="data",
                    user_ids=(),
                    headline=f"Review {value} {label}",
                    evidence=(f"{value} in {month}",),
                    why_it_matters="Data gaps can distort voice hours, session lengths, or in-server classification.",
                    suggested_action=detail,
                    message=f"We have {value} {label} in {month}. Worth checking the tracker when you have a minute.",
                    confidence="high",
                    caveats=(),
                )
            )
    # Schedule action from the busiest local slots.
    slots = sorted(window.weekday_hour_voice.items(), key=lambda item: -item[1])[:3]
    if slots:
        slot_text = ", ".join(
            f"{_weekday_name(day)} {hour:02d}:00 ({seconds / 3600.0:.1f}h)" for (day, hour), seconds in slots
        )
        top_users = [user for user in window.users if user.voice_hours > 0][:8]
        actions.append(
            ActionItem(
                action_id="schedule:peak",
                priority="P1",
                category="schedule",
                user_ids=tuple(user.user_id for user in top_users),
                headline="Schedule around the real peak",
                evidence=(f"Top local slots: {slot_text}",),
                why_it_matters="Events placed at existing peak times get more attendance with less promotion.",
                suggested_action="Pick the top slot, invite the top voice regulars, and announce it once in the community channel.",
                message=f"Peak availability is {slot_text.split(',')[0]}. Want to run the next community night then?",
                confidence="high",
                caveats=("Slots are in each user's local time zone; check the group you invite.",),
            )
        )
    # Deduplicate, cap each category, and order by impact.
    seen: set[str] = set()
    category_counts: dict[str, int] = defaultdict(int)
    unique: list[ActionItem] = []
    for action in sorted(actions, key=lambda item: (-item.score, item.category, item.headline)):
        if action.action_id in seen:
            continue
        limit = ACTION_LIMITS.get(action.category, 10)
        if category_counts[action.category] >= limit:
            continue
        seen.add(action.action_id)
        category_counts[action.category] += 1
        unique.append(action)
    unique.sort(key=lambda item: (-item.score, item.category, item.headline))
    return unique


def _weekday_name(day: int) -> str:
    return ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[day]


def deterministic_narrative(window: WindowMetrics) -> str:
    """A fact-only summary used when AI is disabled or fails validation."""
    top_voice = [user for user in window.users if user.voice_hours > 0][:3]
    top_outside = sorted(
        [user for user in window.users if user.out_rows >= ELSEWHERE_MIN_ROWS],
        key=lambda user: -user.out_rows,
    )[:5]
    if window.weekday_hour_voice:
        peak_day, peak_hour = max(window.weekday_hour_voice.items(), key=lambda item: item[1])[0]
        peak_slot = f"{_weekday_name(peak_day)} {peak_hour:02d}:00."
    else:
        peak_slot = "not available."
    lines = [
        f"## What happened in {_month_label(window)}",
        f"- {window.voice_users} voice-active users generated {window.total_voice_hours:.1f} voice hours across "
        f"{window.session_count} sessions; {window.match_users} users logged {window.match_rows} ranked rows "
        f"in {window.distinct_matches} distinct matches.",
        f"- {window.in_rows} ranked rows ({window.in_percent:.1f}%) overlapped server voice, while "
        f"{window.out_rows} ({window.out_percent:.1f}%) happened outside it.",
        f"- Peak concurrency was {window.peak_concurrent} users; the busiest local slot was {peak_slot}",
        f"- New users: {window.new_users}; returning users: {window.returning_users}; churned users: {window.churned_users}.",
        "## What stands out",
        "- Top voice regulars: " + (", ".join(user.display_name for user in top_voice) or "none") + ".",
        "- Highest outside-server ranked volume: "
        + (", ".join(f"{user.display_name} ({user.out_rows})" for user in top_outside) or "none")
        + ".",
        "## What to do next",
        "- Start with the P0/P1 items in the Action Center: re-engagement, new-member integration, and the outside-play conversation.",
        "- Use the schedule item to place the next community night at the observed peak.",
    ]
    return "\n".join(lines)


def _ask_openai(prompt: str) -> Optional[str]:
    """Call OpenAI directly so the report stays read-only and never imports bot DB code."""
    try:
        from dotenv import load_dotenv
        from openai import OpenAI
    except ImportError:
        return None
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        client = OpenAI(api_key=api_key)
        model = os.getenv("REPORT_AI_MODEL", "gpt-5.6-terra")
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception:
        return None


def build_narrative(
    window: WindowMetrics,
    facts: dict[str, str],
    fallback: str,
) -> tuple[str, str]:
    """Ask the configured AI for a grounded narrative and validate its fact tags."""
    fact_lines = "\n".join(f"- [{key}] = {value}" for key, value in facts.items())
    prompt = (
        "You are writing a short analytics narrative for a Discord Rainbow Six Siege community admin. "
        "Use ONLY the facts below. Do not invent people, numbers, or causes. "
        "Every numeric claim and every person you name must cite its fact id in square brackets, for example: "
        "581.0 voice hours [pulse.voice_hours] or Kuzorota [people.top_voice_1]. "
        "Write 3 short sections: What happened, What stands out, What to do next. "
        "Mention 2-3 concrete people from the people facts. "
        "For pulse.voice_users say 'voice-active users'. "
        "Say 'in server voice' and 'outside server voice'; never say 'in-category' or 'out-category'. "
        "Keep it under 250 words. Be neutral about players who play outside server voice.\n\n"
        f"Facts for {_month_label(window)}:\n{fact_lines}"
    )
    result = _ask_openai(prompt)
    if not result or not result.strip():
        return fallback, "deterministic-fallback"
    text = result.strip()
    tags = re.findall(r"\[([a-zA-Z0-9_.]+)\]", text)
    if not tags or any(tag not in facts for tag in tags):
        return fallback, "deterministic-fallback"
    allowed_numbers: set[str] = set()
    for value in facts.values():
        allowed_numbers.update(re.findall(r"\d+(?:\.\d+)?", value.replace(",", "")))
    allowed_numbers.update({str(number) for number in range(0, 24)})
    allowed_numbers.update({str(number) for number in range(2020, 2031)})
    allowed_numbers.add("250")
    normalized = text.replace(",", "")
    for token in re.findall(r"\b\d+(?:\.\d+)?\b", normalized):
        if token not in allowed_numbers:
            return fallback, "deterministic-fallback"
    cleaned = re.sub(r"\s*\[[a-zA-Z0-9_.]+\]", "", text).strip()
    return cleaned, "ai-grounded"
