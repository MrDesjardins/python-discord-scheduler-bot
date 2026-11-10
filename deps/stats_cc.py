"""Experimental stats.cc match-history adapter; no browser or tracker.gg cookies required."""

import threading
import time
from datetime import datetime
from uuid import UUID

import requests

from deps.data_access_data_class import UserInfo
from deps.models import UserFullMatchStats

API_ROOT = "https://api.stats.cc/siege/v2"


class StatsCCUnavailable(Exception):
    """The provider cannot return a complete, trustworthy history for this account."""


def _display(config: dict, group: str, slug: str) -> str:
    return config[group][slug]["display"]


def parse_match(match: dict, detail: dict, config: dict, user: UserInfo) -> UserFullMatchStats:
    """Translate a finished ranked match, rejecting incomplete or mismatched records."""
    profile_id = user.r6_tracker_active_id
    if match["id"] != detail["id"] or match["playlist"] != "ranked" or match["end_reason"] != "finished":
        raise StatsCCUnavailable("Match is incomplete, canceled, or mismatched")
    player = match["player_summary"]
    if player["profile_id"] != profile_id:
        raise StatsCCUnavailable("Match belongs to another profile")
    if player["outcome"] not in ("win", "loss", "surrender", "forfeit", "abandon"):
        raise StatsCCUnavailable("Unsupported match outcome")
    rounds = [p for r in detail["rounds"] for p in r["player_summaries"] if p["profile_id"] == profile_id]
    if not rounds or len(rounds) < player["rounds"]:
        raise StatsCCUnavailable("Missing per-round player detail")
    operators = dict.fromkeys(_display(config, "operators", p["operator"]) for p in rounds if p.get("operator"))
    ended = datetime.fromisoformat(match["ended_at"].replace("Z", "+00:00"))
    started = datetime.fromisoformat(match["started_at"].replace("Z", "+00:00"))
    if ended.tzinfo is None or started.tzinfo is None or ended < started:
        raise StatsCCUnavailable("Invalid match timestamps")
    rank = match.get("ranked_session") or {}
    points = rank.get("rank_points", 0) or 0
    delta = rank.get("rank_points_delta", 0) or 0
    kills, deaths, assists = player["kills"], player["deaths"], player["assists"]
    count = player["rounds"]
    family = config["datacenters"][match["datacenter"]]["family"]
    center = _display(config, "datacenter_families", family)
    center = {
        "Europe West": "EU West",
        "Europe Central": "EU Central",
        "Europe North": "EU North",
        "US Central": "Central US",
        "Asia Northeast": "AP North East",
        "Asia Southeast": "South East Asia",
        "South America": "Brazil South",
    }.get(center, center)
    map_name = _display(config, "maps", match["map"])
    # Production parity on 2026-11-09: TRN timestamps are match END times. Using
    # started_at moves games into the wrong daily/session summary window.
    # Keep canonical map/rank names so existing grouping and rank roles still work.
    values = dict(
        id=None,
        match_uuid=match["id"],
        user_id=user.id,
        match_timestamp=ended,
        match_duration_ms=round((ended - started).total_seconds() * 1000),
        data_center=center,
        session_type="Ranked",
        map_name="Clubhouse" if map_name == "Club House" else map_name,
        # A short finished game can be a surrender by the OTHER team. Until the
        # provider supplies an explicit match-wide flag, do not guess from scores.
        is_surrender=any(p.get("outcome") == "surrender" for p in detail["player_summaries"]),
        is_forfeit=any(p.get("outcome") == "forfeit" for p in detail["player_summaries"]),
        is_rollback=False,
        r6_tracker_user_uuid=profile_id,
        ubisoft_username=player["username"],
        operators=",".join(operators),
        round_played_count=count,
        round_won_count=player["round_wins"],
        round_lost_count=player["round_losses"],
        round_disconnected_count=player["round_abandons"],
        kill_count=kills,
        death_count=deaths,
        assist_count=assists,
        head_shot_count=player["headshots"],
        tk_count=player["team_kills"],
        ace_count=player["kills_5k"],
        first_kill_count=player["opening_kills"],
        first_death_count=player["opening_deaths"],
        kill_1_count=sum(p["kills"] == 1 for p in rounds),
        rank_points=points,
        rank_name=_display(config, "ranks", rank["rank"]).upper() if points else "Unknown",
        points_gained=delta,
        rank_previous=points - delta,
        kd_ratio=round(kills / max(deaths, 1), 2),
        head_shot_percentage=round(100 * player["headshots"] / kills, 2) if kills else 0,
        kills_per_round=round(kills / count, 2) if count else 0,
        deaths_per_round=round(deaths / count, 2) if count else 0,
        assists_per_round=round(assists / count, 2) if count else 0,
        has_win=player["outcome"] == "win",
    )
    for size in range(1, 6):
        values[f"clutches_win_count_1v{size}"] = player[f"clutch_1v{size}_wins"]
        values[f"clutches_lost_count_1v{size}"] = player[f"clutch_1v{size}_losses"]
    values["clutches_win_count"] = sum(player[f"clutch_1v{s}_wins"] for s in range(1, 6))
    values["clutches_loss_count"] = sum(player[f"clutch_1v{s}_losses"] for s in range(1, 6))
    for size in range(2, 6):
        values[f"kill_{size}_count"] = player[f"kills_{size}k"]
    return UserFullMatchStats(**values)


class StatsCCClient:
    """Bounded HTTP reads with shared pacing; no automatic retries after a block."""

    _lock = threading.Lock()
    _last_request = float("-inf")

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "python-discord-scheduler-bot", "Accept": "application/json"})
        self.config = None
        self.details = {}
        self.failed = False

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.session.close()

    def _get(self, path: str):
        if self.failed:
            raise StatsCCUnavailable("stats.cc HTTP requests stopped for this batch")
        with self._lock:
            wait = 3 - (time.monotonic() - StatsCCClient._last_request)
            if wait > 0:
                time.sleep(wait)
            StatsCCClient._last_request = time.monotonic()
            try:
                response = self.session.get(f"{API_ROOT}/{path}", timeout=20)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                # A challenge/429 must stop this batch, rather than issuing the
                # same failing HTTP request once for every queued player.
                self.failed = True
                raise StatsCCUnavailable(f"stats.cc request failed: {path}") from exc

    def download_matches(self, user: UserInfo) -> list[UserFullMatchStats]:
        """Fetch recent overlay matches. Empty/unsupported accounts must use another source."""
        try:
            profile_id = str(UUID(user.r6_tracker_active_id or ""))
            history = self._get(f"profiles/{profile_id}/matches?playlist=ranked")
            # Empty is not proof of inactivity: non-overlay users may have no match
            # telemetry at stats.cc even while their Ubisoft profile is up to date.
            if not isinstance(history, list) or not history:
                raise StatsCCUnavailable("No stats.cc match telemetry")
            if self.config is None:
                self.config = self._get("config")
            result = []
            for match in history[:20]:
                if not isinstance(match, dict):
                    raise StatsCCUnavailable("Malformed match history")
                if match.get("end_reason") != "finished":
                    continue
                match_id = str(UUID(match["id"]))
                # Teammates share match IDs; fetch each finished match once per batch.
                if match_id not in self.details:
                    self.details[match_id] = self._get(f"matches/{match_id}")
                detail = self.details[match_id]
                result.append(parse_match(match, detail, self.config, user))
            if not result:
                raise StatsCCUnavailable("No completed ranked matches")
            return result
        except (KeyError, TypeError, ValueError) as exc:
            raise StatsCCUnavailable("Unsupported stats.cc response or missing profile ID") from exc
