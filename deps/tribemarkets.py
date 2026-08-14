"""TribeMarkets integration for match prediction markets.

The integration is optional. When ``TRIBEMARKETS_API_KEY`` is not configured,
the Discord bot keeps its existing GIF-only behavior. When configured, a
binary market is created for each detected ranked match, a share link is
posted below the GIF, and score/result updates close and resolve the market.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import quote

import httpx

from deps.log import print_error_log, print_warning_log


DEFAULT_API_URL = "https://tribemarkets.com/v1"
DEFAULT_TRIBE_SLUG = "circus-maximus"
DEFAULT_SHARE_LINK_HOURS = 168
DEFAULT_CLOSE_SCORE = 2
DEFAULT_CHALLENGE_MINUTES = 15
RESULT_RECAP_MAX_PARTICIPANTS = 8
MATCH_MARKET_CATEGORY = "Siege"
MATCH_MARKET_TAGS = ("Match", "Ranked")


class TribeMarketsIntegrationError(RuntimeError):
    """A safe, expected failure while calling TribeMarkets."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class TribeMarketsSettings:
    """Environment-backed settings for the optional integration."""

    api_url: str
    api_key: str
    tribe_slug: str
    tribe_id: str | None
    validation_provider_id: str | None
    validation_mode: str
    share_link_hours: int
    close_score: int
    challenge_minutes: int

    @classmethod
    def from_environment(cls) -> "TribeMarketsSettings":
        def positive_int(name: str, default: int, maximum: int | None = None) -> int:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = int(raw)
            except ValueError as exc:
                raise ValueError(f"{name} must be an integer") from exc
            if value < 1 or (maximum is not None and value > maximum):
                suffix = f" and <= {maximum}" if maximum is not None else ""
                raise ValueError(f"{name} must be >= 1{suffix}")
            return value

        validation_mode = os.getenv("TRIBEMARKETS_VALIDATION_MODE", "manual").strip().lower()
        if validation_mode not in {"manual", "signed_bot_with_challenge"}:
            raise ValueError("TRIBEMARKETS_VALIDATION_MODE must be manual or signed_bot_with_challenge")
        provider_id = os.getenv("TRIBEMARKETS_VALIDATION_PROVIDER_ID", "").strip() or None
        if validation_mode == "signed_bot_with_challenge" and not provider_id:
            raise ValueError("TRIBEMARKETS_VALIDATION_PROVIDER_ID is required for signed bot validation")
        return cls(
            api_url=os.getenv("TRIBEMARKETS_API_URL", DEFAULT_API_URL).strip().rstrip("/"),
            api_key=os.getenv("TRIBEMARKETS_API_KEY", "").strip(),
            tribe_slug=os.getenv("TRIBEMARKETS_TRIBE_SLUG", DEFAULT_TRIBE_SLUG).strip(),
            tribe_id=os.getenv("TRIBEMARKETS_TRIBE_ID", "").strip() or None,
            validation_provider_id=provider_id,
            validation_mode=validation_mode,
            share_link_hours=positive_int("TRIBEMARKETS_SHARE_LINK_HOURS", DEFAULT_SHARE_LINK_HOURS, 168),
            close_score=positive_int("TRIBEMARKETS_CLOSE_SCORE", DEFAULT_CLOSE_SCORE),
            challenge_minutes=positive_int(
                "TRIBEMARKETS_VALIDATION_CHALLENGE_MINUTES", DEFAULT_CHALLENGE_MINUTES, 7 * 24 * 60
            ),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key and (self.tribe_id or self.tribe_slug))


def score_reached_close_threshold(our_score: int, their_score: int, *, threshold: int = DEFAULT_CLOSE_SCORE) -> bool:
    """Return true when one side reaches the configured first-to-N score.

    This intentionally does not decide the winner. The existing stats.cc
    ``is_match_complete`` signal remains the authority for resolution because
    a low round score can occur between rounds in Rainbow Six Siege.
    """
    return max(our_score, their_score) >= threshold and our_score != their_score


def infer_map_name(details: str | None) -> str | None:
    """Extract a map from a stats.cc detail such as ``Ranked on Villa``."""
    if not details or "Ranked on " not in details:
        return None
    map_name = details.split("Ranked on ", 1)[1].strip()
    return map_name or None


def build_market_title(started_at: datetime, map_name: str | None) -> str:
    """Build a concise, date-bearing title for the Discord match market."""
    timestamp = started_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return f"{timestamp} · {map_name or 'Map pending'} — Will the squad win?"


def build_market_description(
    *,
    member_names: Iterable[str],
    started_at: datetime,
    map_name: str | None,
) -> str:
    """Build the user-facing binary prediction description."""
    names = ", ".join(name.strip() for name in member_names if name.strip()) or "Unknown squad"
    timestamp = started_at.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Squad: {names}\n"
        f"Map: {map_name or 'Pending from match telemetry'}\n"
        f"Started: {timestamp}\n\n"
        "Vote Yes if this squad will win the match; vote No if it will lose. "
        "The bot closes voting when one side reaches the configured score threshold "
        "and records the final win/loss result from stats.cc."
    )


@dataclass
class MatchMarket:
    """The minimum market state needed by the GIF lifecycle."""

    community_id: str
    market_id: str
    yes_outcome_id: str
    no_outcome_id: str
    share_url: str
    external_event_id: str
    vote_closed: bool = False
    result_submitted: bool = False
    vote_message_id: int | None = None
    settlement_complete: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "community_id": self.community_id,
            "market_id": self.market_id,
            "yes_outcome_id": self.yes_outcome_id,
            "no_outcome_id": self.no_outcome_id,
            "share_url": self.share_url,
            "external_event_id": self.external_event_id,
            "vote_closed": self.vote_closed,
            "result_submitted": self.result_submitted,
            "settlement_complete": self.settlement_complete,
            "vote_message_id": self.vote_message_id,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MatchMarket":
        return cls(
            community_id=str(value["community_id"]),
            market_id=str(value["market_id"]),
            yes_outcome_id=str(value["yes_outcome_id"]),
            no_outcome_id=str(value["no_outcome_id"]),
            share_url=str(value["share_url"]),
            external_event_id=str(value["external_event_id"]),
            vote_closed=bool(value.get("vote_closed", False)),
            result_submitted=bool(value.get("result_submitted", False)),
            settlement_complete=bool(value.get("settlement_complete", False)),
            vote_message_id=int(value["vote_message_id"]) if value.get("vote_message_id") is not None else None,
        )


def _signed_money(value: Any) -> str:
    """Render an API money string with an explicit sign without using floats."""
    text = str(value)
    if text.startswith("-") or text.startswith("+"):
        return text
    return f"+{text}"


def _participant_line(participant: dict[str, Any]) -> str:
    name = str(participant.get("display_name") or "Unknown")
    outcome = str(participant.get("outcome_code") or "?")
    profit = _signed_money(participant.get("profit", "0"))
    payout = str(participant.get("payout", "0"))
    return f"• {name} — {outcome}: {profit} profit ({payout} payout)"


def format_result_summary(summary: dict[str, Any], market_url: str) -> str:
    """Build a bounded, public Discord recap from the API result summary.

    The API intentionally returns only the top ten winners and losers. For a
    small match we show every returned position; for a larger match we show
    only the headline earners so the message remains useful and under
    Discord's message-size limit.
    """
    raw_market = summary.get("market")
    market = raw_market if isinstance(raw_market, dict) else {}
    status = str(market.get("status") or "")
    lines = ["🏁 **TribeMarkets result**"]
    if status in {"voided", "cancelled"}:
        reason = str(summary.get("terminal_reason") or status)
        lines.append(f"↩️ Market **{reason}** — all stakes were refunded.")
        lines.append(f"🔗 View market: {market_url}")
        return "\n".join(lines)[:2000]

    winning = market.get("winning_outcome")
    if isinstance(winning, dict):
        winning_label = str(winning.get("label") or winning.get("code") or "Unknown")
        lines.append(f"Winning prediction: **{winning_label}**")
    else:
        lines.append("The result was recorded, but the winning prediction is not available yet.")
    evidence = market.get("evidence")
    if isinstance(evidence, dict) and evidence.get("final_score"):
        lines.append(f"Final score: **{evidence['final_score']}**")

    pool = summary.get("pool") if isinstance(summary.get("pool"), dict) else None
    participants = summary.get("participants") if isinstance(summary.get("participants"), dict) else None
    if pool is not None:
        currency = str(pool.get("currency_code") or "credits")
        lines.append(f"Pool: {pool.get('total_staked', '0')} {currency}")
    if participants is not None:
        lines.append(
            "Correct predictions: "
            f"{participants.get('correct_count', 0)}/{participants.get('eligible_count', 0)} "
            f"· Incorrect: {participants.get('incorrect_count', 0)}"
        )

    winners = summary.get("top_winners")
    losers = summary.get("top_losers")
    winners = winners if isinstance(winners, list) else []
    losers = losers if isinstance(losers, list) else []
    if winners:
        highest = winners[0]
        if isinstance(highest, dict):
            lines.append(
                f"🏆 Highest earner: **{highest.get('display_name', 'Unknown')}** "
                f"({_signed_money(highest.get('profit', '0'))} profit)"
            )
    if losers:
        biggest_loss = losers[0]
        if isinstance(biggest_loss, dict):
            lines.append(
                f"📉 Biggest loss: **{biggest_loss.get('display_name', 'Unknown')}** "
                f"({_signed_money(biggest_loss.get('profit', '0'))})"
            )

    eligible_count = int(participants.get("eligible_count", 0)) if participants is not None else 0
    if eligible_count and eligible_count <= RESULT_RECAP_MAX_PARTICIPANTS:
        all_participants = [item for item in [*winners, *losers] if isinstance(item, dict)]
        if all_participants:
            lines.append("\n**Prediction breakdown**")
            lines.extend(_participant_line(item) for item in all_participants)
    elif eligible_count > RESULT_RECAP_MAX_PARTICIPANTS:
        lines.append(f"Detailed breakdown omitted for privacy ({eligible_count} bets).")

    link_line = f"🔗 View market: {market_url}"
    body = "\n".join(lines)
    available_body_length = 2000 - len(link_line) - 1
    if len(body) > available_body_length:
        body = body[: max(0, available_body_length - 1)] + "…"
    return f"{body}\n{link_line}"


class TribeMarketsClient:
    """Small async client using a Tribe-bound TribeMarkets API key."""

    def __init__(self, settings: TribeMarketsSettings | None = None) -> None:
        self.settings = settings or TribeMarketsSettings.from_environment()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.enabled:
            raise TribeMarketsIntegrationError("TribeMarkets integration is not configured")
        request_headers = {"X-API-Key": self.settings.api_key}
        if headers:
            request_headers.update(headers)
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.api_url,
                headers=request_headers,
                timeout=httpx.Timeout(15.0),
            ) as client:
                response = await client.request(method, path, json=json_body)
        except httpx.HTTPError as exc:
            raise TribeMarketsIntegrationError(f"TribeMarkets request failed: {exc}") from exc
        if response.status_code >= 400:
            raise TribeMarketsIntegrationError(
                f"TribeMarkets request returned HTTP {response.status_code}",
                status_code=response.status_code,
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TribeMarketsIntegrationError("TribeMarkets returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise TribeMarketsIntegrationError("TribeMarkets returned an unexpected response")
        return payload

    async def create_match_market(
        self,
        *,
        guild_id: int,
        voice_channel_id: int,
        member_names: list[str],
        started_at: datetime,
        map_name: str | None,
    ) -> MatchMarket | None:
        """Create an open binary market and its short-lived share link."""
        if not self.settings.enabled:
            return None
        community_id = self.settings.tribe_id
        if community_id is None:
            community = await self._request("GET", f"/communities/by-slug/{quote(self.settings.tribe_slug, safe='')}")
            community_id = str(community["id"])
        external_event_id = f"discord-ranked:{guild_id}:{voice_channel_id}:{int(started_at.timestamp())}"
        closes_at = started_at + timedelta(hours=4)
        resolves_at = started_at + timedelta(hours=5)
        policy: dict[str, Any] = {"type": "manual"}
        if self.settings.validation_mode == "signed_bot_with_challenge":
            policy = {
                "type": "signed_bot_with_challenge",
                "provider_id": self.settings.validation_provider_id,
                "external_event_id": external_event_id,
                "challenge_window_minutes": self.settings.challenge_minutes,
                "require_final_attestation": True,
            }
        payload: dict[str, Any] = {
            "title": build_market_title(started_at, map_name),
            "description": build_market_description(
                member_names=member_names,
                started_at=started_at,
                map_name=map_name,
            ),
            "resolution_criteria": (
                "Use the final win/loss result reported by the bot's stats.cc match telemetry. "
                "A match result is not inferred from an intermediate round score."
            ),
            "market_type": "binary",
            "opens_at": started_at.astimezone(timezone.utc).isoformat(),
            "closes_at": closes_at.astimezone(timezone.utc).isoformat(),
            "resolves_at": resolves_at.astimezone(timezone.utc).isoformat(),
            "resolution_source": "stats.cc",
            "external_source": "python-discord-scheduler-bot",
            "external_event_id": external_event_id,
            "external_market_type": "rainbow-six-ranked-match",
            "category": MATCH_MARKET_CATEGORY,
            "tags": list(MATCH_MARKET_TAGS),
            "validation_policy": policy,
            "metadata": {
                "discord_guild_id": str(guild_id),
                "discord_voice_channel_id": str(voice_channel_id),
                "member_names": member_names,
                "map_name": map_name,
            },
        }
        market = await self._request(
            "POST",
            f"/communities/{community_id}/markets",
            json_body=payload,
            headers={
                "Idempotency-Key": hashlib.sha256(external_event_id.encode()).hexdigest(),
            },
        )
        outcomes = market.get("outcomes")
        if not isinstance(outcomes, list):
            raise TribeMarketsIntegrationError("Created market did not return outcomes")
        yes = next(
            (item for item in outcomes if isinstance(item, dict) and str(item.get("code", "")).upper() == "YES"),
            None,
        )
        no = next(
            (item for item in outcomes if isinstance(item, dict) and str(item.get("code", "")).upper() == "NO"),
            None,
        )
        if not isinstance(yes, dict) or not isinstance(no, dict):
            raise TribeMarketsIntegrationError("Created binary market did not return YES/NO outcomes")
        market_id = str(market["id"])
        share_url = f"https://tribemarkets.com/app/tribes/{quote(self.settings.tribe_slug)}/markets/{market_id}"
        try:
            share = await self._request(
                "POST",
                f"/communities/{community_id}/markets/{market_id}/share-links",
                json_body={"expires_in_hours": self.settings.share_link_hours},
            )
            share_url = str(share.get("url", share_url))
        except TribeMarketsIntegrationError as exc:
            print_warning_log(f"TribeMarkets share link unavailable: {exc}")
        return MatchMarket(
            community_id=str(community_id),
            market_id=market_id,
            yes_outcome_id=str(yes["id"]),
            no_outcome_id=str(no["id"]),
            share_url=share_url,
            external_event_id=external_event_id,
        )

    async def close_market(self, market: MatchMarket) -> bool:
        """Close betting; a conflict is treated as an already-closed market."""
        try:
            await self._request("POST", f"/communities/{market.community_id}/markets/{market.market_id}/close")
            return True
        except TribeMarketsIntegrationError as exc:
            if exc.status_code == 409:
                return True
            print_error_log(f"TribeMarkets could not close market {market.market_id}: {exc}")
            return False

    async def get_result_summary(self, market: MatchMarket) -> dict[str, Any] | None:
        """Read the settled recap used to update the Discord voting message.

        A 409 means a signed validation submission is still awaiting its
        challenge/finalization window, so it is intentionally not treated as
        an integration failure.
        """
        try:
            return await self._request(
                "GET",
                f"/communities/{market.community_id}/markets/{market.market_id}/result-summary",
            )
        except TribeMarketsIntegrationError as exc:
            if exc.status_code in {404, 409}:
                return None
            print_error_log(f"TribeMarkets result summary unavailable for {market.market_id}: {exc}")
            return None

    async def submit_result(
        self,
        market: MatchMarket,
        *,
        won: bool,
        score: str,
        map_name: str | None,
        member_names: list[str],
        occurred_at: datetime,
    ) -> bool:
        """Resolve directly or submit a signed result, depending on configuration."""
        outcome_id = market.yes_outcome_id if won else market.no_outcome_id
        evidence = {
            "source": "stats.cc",
            "final_score": score,
            "map_name": map_name,
            "member_names": member_names,
            "external_event_id": market.external_event_id,
        }
        if self.settings.validation_mode == "signed_bot_with_challenge":
            provider_id = self.settings.validation_provider_id
            if provider_id is None:
                return False
            timestamp = str(int(time.time()))
            nonce = secrets.token_urlsafe(18)
            submission = {
                "provider_id": provider_id,
                "external_event_id": market.external_event_id,
                "winning_outcome_code": "YES" if won else "NO",
                "status": "final",
                "evidence": evidence,
                "occurred_at": occurred_at.astimezone(timezone.utc).isoformat(),
                "nonce": nonce,
            }
            canonical = {
                "market_id": market.market_id,
                **submission,
            }
            encoded = json.dumps(
                canonical,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
            signature = hmac.new(
                self.settings.api_key.encode(),
                f"{timestamp}.".encode() + encoded,
                hashlib.sha256,
            ).hexdigest()
            try:
                await self._request(
                    "POST",
                    f"/communities/{market.community_id}/markets/{market.market_id}/validation/submissions",
                    json_body=submission,
                    headers={
                        "X-Validation-Timestamp": timestamp,
                        "X-Validation-Signature": f"v1={signature}",
                        "Idempotency-Key": f"{market.external_event_id}:result",
                    },
                )
                return True
            except TribeMarketsIntegrationError as exc:
                if exc.status_code == 409:
                    return True
                print_error_log(f"TribeMarkets could not submit result {market.market_id}: {exc}")
                return False
        try:
            await self._request(
                "POST",
                f"/communities/{market.community_id}/markets/{market.market_id}/resolve",
                json_body={
                    "winning_outcome_id": outcome_id,
                    "resolution_source": "stats.cc",
                    "evidence": evidence,
                },
            )
            return True
        except TribeMarketsIntegrationError as exc:
            if exc.status_code == 409:
                return True
            print_error_log(f"TribeMarkets could not resolve market {market.market_id}: {exc}")
            return False
