#!/usr/bin/env python3
"""Backfill visible Discord guild messages into the local moderation archive DB."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import discord
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


DEFAULT_GUILD_ID = 1224166062581612574


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


def get_token(token_env: str) -> str:
    load_dotenv()
    token = os.getenv(token_env)
    if token is None:
        raise RuntimeError(f"Missing {token_env}. Check .env.")
    return token


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


async def backfill(args: argparse.Namespace) -> None:
    from deps.message_archive_data_access import (
        archive_message_payloads,
        open_archive_connection,
        serialize_discord_message,
    )

    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready() -> None:
        try:
            guild = client.get_guild(args.guild_id)
            if guild is None:
                raise RuntimeError(f"Guild {args.guild_id} is not in the bot cache.")

            channels = await iter_channels(guild)
            if args.channel_id:
                wanted_channel_ids = set(args.channel_id)
                channels = [channel for channel in channels if getattr(channel, "id") in wanted_channel_ids]
            if args.skip_channel:
                skipped_channel_ids = set(args.skip_channel)
                channels = [channel for channel in channels if getattr(channel, "id") not in skipped_channel_ids]

            print(f"connected as {client.user}; backfilling {guild.name} ({guild.id})")
            print(f"found {len(channels)} text/thread channels to scan")

            after = parse_datetime(args.after)
            before = parse_datetime(args.before)
            total_seen = 0
            total_archived = 0
            errors: list[str] = []

            with open_archive_connection(args.database) as archive_conn:
                for channel in channels:
                    channel_id = getattr(channel, "id")
                    channel_name = getattr(channel, "name", "unknown")
                    channel_count = 0
                    batch: list[dict] = []
                    try:
                        async for message in channel.history(
                            limit=args.limit_per_channel,
                            after=after,
                            before=before,
                            oldest_first=args.oldest_first,
                        ):
                            batch.append(serialize_discord_message(message, source="backfill"))
                            channel_count += 1
                            total_seen += 1
                            if len(batch) >= args.batch_size:
                                total_archived += archive_message_payloads(
                                    batch,
                                    event_type="backfill",
                                    conn=archive_conn,
                                )
                                batch = []
                            if args.progress_every and total_seen % args.progress_every == 0:
                                print(
                                    f"progress: seen {total_seen}; archived {total_archived}; "
                                    f"currently scanning #{channel_name} ({channel_id})"
                                )
                        if batch:
                            total_archived += archive_message_payloads(
                                batch,
                                event_type="backfill",
                                conn=archive_conn,
                            )
                        print(f"scanned #{channel_name} ({channel_id}); archived {channel_count} messages")
                    except discord.Forbidden as exc:
                        errors.append(f"#{channel_name} ({channel_id}): forbidden: {exc}")
                    except discord.HTTPException as exc:
                        errors.append(f"#{channel_name} ({channel_id}): http: {exc}")

            print(f"done: seen {total_seen}; archived {total_archived}; errors {len(errors)}")
            for error in errors:
                print(f"error: {error}")
        finally:
            await client.close()
            await asyncio.sleep(0.25)

    await client.start(get_token(args.token_env))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guild-id", type=int, default=DEFAULT_GUILD_ID)
    parser.add_argument("--token-env", choices=["BOT_TOKEN", "BOT_TOKEN_DEV"], default="BOT_TOKEN")
    parser.add_argument("--after", help="Optional ISO timestamp, for example 2025-01-01T00:00:00Z.")
    parser.add_argument("--before", help="Optional ISO timestamp, for example 2026-01-01T00:00:00Z.")
    parser.add_argument("--limit-per-channel", type=int, default=None)
    parser.add_argument("--oldest-first", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--progress-every", type=int, default=5000)
    parser.add_argument("--channel-id", type=int, action="append")
    parser.add_argument("--skip-channel", type=int, action="append")
    parser.add_argument(
        "--database",
        default=None,
        help="Optional DB path. Defaults to the project database configured by deps.system_database.",
    )
    args = parser.parse_args()

    if args.database:
        Path(args.database).parent.mkdir(parents=True, exist_ok=True)
        os.environ["MESSAGE_ARCHIVE_DATABASE"] = args.database

    asyncio.run(backfill(args))


if __name__ == "__main__":
    main()
