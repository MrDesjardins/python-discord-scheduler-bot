#!/usr/bin/env python3
"""Export one Discord user's visible message history from one guild.

Deleted messages cannot be recovered through Discord's API. This script exports
messages that still exist and are visible to the bot account.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import traceback
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord
from dotenv import load_dotenv, dotenv_values


DEFAULT_GUILD_ID = 1224166062581612574
DEFAULT_USER_ID = 1177820750636400711


@dataclass
class ExportStats:
    guild_id: int
    user_id: int
    started_at: str
    finished_at: str | None = None
    channels_scanned: int = 0
    channels_skipped: int = 0
    messages_seen: int = 0
    messages_exported: int = 0
    errors: list[dict[str, str]] | None = None


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def get_token(token_env: str | None = None) -> str:
    load_dotenv()
    env = os.getenv("ENV")
    if env == "prod":
        for key, value in dotenv_values().items():
            if value is not None:
                os.environ[key] = value

    token_key = token_env or ("BOT_TOKEN_DEV" if os.getenv("ENV") == "dev" else "BOT_TOKEN")
    token = os.getenv(token_key)
    if token is None:
        raise RuntimeError(f"Missing {token_key}. Check .env or ENV.")
    return token


def serialize_message(message: discord.Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "guild_id": message.guild.id if message.guild else None,
        "channel_id": message.channel.id,
        "channel_name": getattr(message.channel, "name", None),
        "channel_type": type(message.channel).__name__,
        "author_id": message.author.id,
        "author_name": str(message.author),
        "created_at": message.created_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "content": message.content,
        "clean_content": message.clean_content,
        "jump_url": message.jump_url,
        "attachments": [
            {
                "id": attachment.id,
                "filename": attachment.filename,
                "url": attachment.url,
                "content_type": attachment.content_type,
                "size": attachment.size,
            }
            for attachment in message.attachments
        ],
        "embeds": [embed.to_dict() for embed in message.embeds],
        "mentions": [user.id for user in message.mentions],
        "role_mentions": [role.id for role in message.role_mentions],
        "reactions": [
            {
                "emoji": str(reaction.emoji),
                "count": reaction.count,
            }
            for reaction in message.reactions
        ],
        "reference_message_id": message.reference.message_id if message.reference else None,
    }


async def iter_channels(guild: discord.Guild) -> list[discord.abc.Messageable]:
    channels: list[discord.abc.Messageable] = []

    channels.extend(guild.text_channels)
    channels.extend(guild.threads)

    for text_channel in guild.text_channels:
        channels.extend(text_channel.threads)
        try:
            async for thread in text_channel.archived_threads(limit=None):
                channels.append(thread)
        except (discord.Forbidden, discord.HTTPException):
            continue

    for forum_channel in guild.forums:
        channels.extend(forum_channel.threads)
        try:
            async for thread in forum_channel.archived_threads(limit=None):
                channels.append(thread)
        except (discord.Forbidden, discord.HTTPException):
            continue

    unique: dict[int, discord.abc.Messageable] = {}
    for channel in channels:
        unique[getattr(channel, "id")] = channel
    return list(unique.values())


async def export_messages(args: argparse.Namespace) -> None:
    token = get_token(args.token_env)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path = output_path.with_suffix(output_path.suffix + ".summary.json")

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True

    stats = ExportStats(
        guild_id=args.guild_id,
        user_id=args.user_id,
        started_at=datetime.now(timezone.utc).isoformat(),
        errors=[],
    )

    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        try:
            guild = client.get_guild(args.guild_id)
            if guild is None:
                raise RuntimeError(
                    f"Guild {args.guild_id} is not in the bot cache. "
                    "Confirm the bot is in the guild and has the Server Members/Guilds gateway access it needs."
                )
            print(f"connected as {client.user}; exporting from {guild.name} ({guild.id})")
            channels = await iter_channels(guild)
            if args.channel_id:
                wanted_channel_ids = set(args.channel_id)
                channels = [channel for channel in channels if getattr(channel, "id") in wanted_channel_ids]
            if args.skip_channel:
                skipped_channel_ids = set(args.skip_channel)
                channels = [channel for channel in channels if getattr(channel, "id") not in skipped_channel_ids]
            print(f"found {len(channels)} text/thread channels to scan")

            after = parse_datetime(args.after)
            before = parse_datetime(args.before)

            with output_path.open("w", encoding="utf-8") as output_file:
                for channel in channels:
                    channel_id = str(getattr(channel, "id", "unknown"))
                    channel_name = str(getattr(channel, "name", "unknown"))
                    stats.channels_scanned += 1
                    try:
                        count_for_channel = 0
                        async for message in channel.history(
                            limit=args.limit_per_channel,
                            after=after,
                            before=before,
                            oldest_first=args.oldest_first,
                        ):
                            stats.messages_seen += 1
                            if args.progress_every and stats.messages_seen % args.progress_every == 0:
                                print(
                                    f"progress: seen {stats.messages_seen} messages; "
                                    f"exported {stats.messages_exported}; "
                                    f"currently scanning #{channel_name} ({channel_id})"
                                )
                            if message.author.id != args.user_id:
                                continue
                            output_file.write(json.dumps(serialize_message(message), ensure_ascii=False) + "\n")
                            output_file.flush()
                            stats.messages_exported += 1
                            count_for_channel += 1
                        if not args.quiet:
                            print(
                                f"scanned #{channel_name} ({channel_id}); "
                                f"exported {count_for_channel} matching messages"
                            )
                    except discord.Forbidden as exc:
                        stats.channels_skipped += 1
                        stats.errors.append(
                            {
                                "channel_id": channel_id,
                                "channel_name": channel_name,
                                "error": f"forbidden: {exc}",
                            }
                        )
                    except discord.HTTPException as exc:
                        stats.channels_skipped += 1
                        stats.errors.append(
                            {
                                "channel_id": channel_id,
                                "channel_name": channel_name,
                                "error": f"http: {exc}",
                            }
                        )

            stats.finished_at = datetime.now(timezone.utc).isoformat()
            summary_path.write_text(json.dumps(asdict(stats), indent=2), encoding="utf-8")
            print(f"wrote messages: {output_path}")
            print(f"wrote summary: {summary_path}")
        except Exception as exc:  # pylint: disable=broad-exception-caught
            stats.finished_at = datetime.now(timezone.utc).isoformat()
            stats.errors = stats.errors or []
            stats.errors.append({"channel_id": "global", "channel_name": "global", "error": repr(exc)})
            summary_path.write_text(json.dumps(asdict(stats), indent=2), encoding="utf-8")
            print(f"export failed: {exc}")
            traceback.print_exc()
        finally:
            await client.close()
            await asyncio.sleep(0.25)

    await client.start(token)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guild-id", type=int, default=DEFAULT_GUILD_ID)
    parser.add_argument("--user-id", type=int, default=DEFAULT_USER_ID)
    parser.add_argument("--output", default=f"exports/user-{DEFAULT_USER_ID}-messages.jsonl")
    parser.add_argument(
        "--token-env",
        choices=["BOT_TOKEN", "BOT_TOKEN_DEV"],
        help="Override token selection without changing ENV. Defaults to BOT_TOKEN_DEV when ENV=dev, else BOT_TOKEN.",
    )
    parser.add_argument("--after", help="Optional ISO timestamp, for example 2026-01-01T00:00:00Z.")
    parser.add_argument("--before", help="Optional ISO timestamp, for example 2026-06-27T00:00:00Z.")
    parser.add_argument(
        "--limit-per-channel",
        type=int,
        default=None,
        help="Optional scan cap per channel. Default scans full visible history.",
    )
    parser.add_argument("--quiet", action="store_true", help="Suppress per-channel scan output.")
    parser.add_argument("--oldest-first", action="store_true", help="Scan each channel from oldest to newest.")
    parser.add_argument(
        "--channel-id",
        type=int,
        action="append",
        help="Only scan this channel/thread id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--skip-channel",
        type=int,
        action="append",
        help="Skip this channel/thread id. Can be passed multiple times.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10000,
        help="Print progress every N scanned messages. Use 0 to disable.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    asyncio.run(export_messages(args))


if __name__ == "__main__":
    main()
