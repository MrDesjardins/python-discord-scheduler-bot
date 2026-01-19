"""
Function to interact with the AI bot and Discord bot
"""

import discord

from deps.ai.ai_functions import BotAISingleton
from deps.data_access import data_access_get_ai_text_channel_id, data_access_get_channel, data_access_get_main_text_channel_id
from deps.log import print_error_log, print_warning_log


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
    # Split the message into chunks of 2000 characters
    chunks = [msg[i : i + 2000] for i in range(0, len(msg), 2000)]
    # Send each chunk as a separate message
    for chunk in chunks:
        await channel.send(content=chunk)
