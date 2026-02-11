"""
Function to interact with the AI bot and Discord bot
"""

import discord

from deps.ai.ai_functions import BotAISingleton
from deps.data_access import data_access_get_ai_text_channel_id, data_access_get_channel, data_access_get_main_text_channel_id
from deps.log import print_error_log, print_warning_log


def split_message_at_paragraphs(message: str, max_length: int = 2000) -> list[str]:
    """
    Split a message into chunks at paragraph boundaries to avoid breaking mid-paragraph.
    Discord has a 2000 character limit per message.

    Args:
        message: The message to split
        max_length: Maximum length per chunk (default 2000 for Discord)

    Returns:
        List of message chunks, each <= max_length characters
    """
    if len(message) <= max_length:
        return [message]

    chunks = []
    current_chunk = ""

    # Split by double newlines (paragraphs)
    paragraphs = message.split("\n\n")

    for paragraph in paragraphs:
        # If adding this paragraph would exceed the limit
        if len(current_chunk) + len(paragraph) + 2 > max_length:  # +2 for "\n\n"
            # If current chunk has content, save it
            if current_chunk:
                chunks.append(current_chunk.rstrip())
                current_chunk = ""

            # If the paragraph itself is too long, split by single newlines
            if len(paragraph) > max_length:
                lines = paragraph.split("\n")
                for line in lines:
                    if len(current_chunk) + len(line) + 1 > max_length:  # +1 for "\n"
                        if current_chunk:
                            chunks.append(current_chunk.rstrip())
                            current_chunk = ""

                        # If even a single line is too long, hard split it
                        if len(line) > max_length:
                            for i in range(0, len(line), max_length):
                                chunks.append(line[i : i + max_length])
                        else:
                            current_chunk = line + "\n"
                    else:
                        current_chunk += line + "\n"
            else:
                current_chunk = paragraph + "\n\n"
        else:
            current_chunk += paragraph + "\n\n"

    # Add any remaining content
    if current_chunk:
        chunks.append(current_chunk.rstrip())

    return chunks


async def send_daily_ai_summary_guild(guild: discord.Guild):
    """
    Send a daily message in the guild main text channel with the summary of the last 24 hours
    """
    guild_id = guild.id

    channel_id = await data_access_get_ai_text_channel_id(guild_id)
    if channel_id is None:
        print_error_log(
            f"\t⚠️ send_daily_ai_summary_guild: Channel id (AI text) not found for guild {guild.name}. Skipping."
        )
        return
    channel = await data_access_get_channel(channel_id)
    if channel is None:
        print_error_log(f"\t⚠️ send_daily_ai_summary_guild: Channel not found for guild {guild.name}. Skipping.")
        return
    try:
        msg = await BotAISingleton().generate_message_summary_matches_async(24)
    except Exception as e:
        print_error_log(f"send_daily_ai_summary_guild>generate_message_summary_matches_async: {e}")
        msg = ""

    if msg == "":
        print_warning_log(f"\t⚠️ send_daily_ai_summary_guild: No summary found for guild {guild.name}. Skipping.")
        return
    # Split the message into chunks at paragraph boundaries to avoid breaking mid-paragraph
    chunks = split_message_at_paragraphs(msg)
    # Send each chunk as a separate message
    for chunk in chunks:
        await channel.send(content=chunk)
