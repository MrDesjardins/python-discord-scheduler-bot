#!/usr/bin/env python3
"""Export visible Discord messages from a channel in a time window."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import discord
from dotenv import load_dotenv


def parse_datetime(value: str) -> datetime:
    normalized = value.strip()
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


def serialize_message(message: discord.Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "guild_id": message.guild.id if message.guild else None,
        "channel_id": message.channel.id,
        "channel_name": getattr(message.channel, "name", None),
        "author_id": message.author.id,
        "author_name": str(message.author),
        "created_at": message.created_at.isoformat(),
        "edited_at": message.edited_at.isoformat() if message.edited_at else None,
        "content": message.content,
        "clean_content": message.clean_content,
        "jump_url": message.jump_url,
        "reference_message_id": message.reference.message_id if message.reference else None,
    }


async def export_window(args: argparse.Namespace) -> None:
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True
    client = discord.Client(intents=intents)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    @client.event
    async def on_ready() -> None:
        try:
            channel = client.get_channel(args.channel_id)
            if channel is None:
                channel = await client.fetch_channel(args.channel_id)
            if not isinstance(channel, discord.abc.Messageable):
                raise RuntimeError(f"Channel {args.channel_id} is not messageable.")

            after = parse_datetime(args.after)
            before = parse_datetime(args.before)
            count = 0
            with output_path.open("w", encoding="utf-8") as output_file:
                async for message in channel.history(limit=None, after=after, before=before, oldest_first=True):
                    output_file.write(json.dumps(serialize_message(message), ensure_ascii=False) + "\n")
                    count += 1
            print(f"exported {count} messages to {output_path}")
        finally:
            await client.close()
            await asyncio.sleep(0.25)

    await client.start(get_token(args.token_env))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel-id", type=int, required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--token-env", choices=["BOT_TOKEN", "BOT_TOKEN_DEV"], default="BOT_TOKEN")
    asyncio.run(export_window(parser.parse_args()))


if __name__ == "__main__":
    main()
