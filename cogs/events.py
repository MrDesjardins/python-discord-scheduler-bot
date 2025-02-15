import os
from dotenv import load_dotenv
from datetime import datetime, timezone
import asyncio
from discord.ext import commands
import discord
from deps.cache import start_periodic_cache_cleanup
from deps.analytic_data_access import insert_user_activity
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT
from deps.bot_common_actions import (
    send_daily_question_to_a_guild,
    send_automatic_lfg_message,
    send_notification_voice_channel,
    send_session_stats_to_queue,
)
from deps.data_access import (
    data_access_get_channel,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_main_text_channel_id,
    data_access_get_new_user_text_channel_id,
    data_access_remove_voice_user_list,
    data_access_update_voice_user_list,
)
from deps.log import print_log, print_warning_log, print_error_log
from deps.mybot import MyBot
from deps.models import ActivityTransition
from deps.siege import get_siege_activity
from deps.functions_stats import send_daily_stats_to_a_guild

load_dotenv()

ENV = os.getenv("ENV")


class MyEventsCog(commands.Cog):
    lock = asyncio.Lock()

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.last_task = {}

    @commands.Cog.listener()
    async def on_ready(self):
        """Main function to run when the bot is ready"""
        bot = self.bot
        print_log(f"{bot.user} has connected to Discord!")
        print_log(f"Bot latency: {bot.latency} seconds")
        tasks = []
        for guild in bot.guilds:
            print_log(f"Checking in guild: {guild.name} ({guild.id}) - Created the {guild.created_at}")
            print_log(f"\tGuild {guild.name} has {guild.member_count} members, setting the commands")
            guild_obj = discord.Object(id=guild.id)

            # commands_reg = await bot.tree.fetch_commands(guild=guild_obj)
            # for command in commands_reg:
            #     print_log(f"\tDeleting command {command.name}")
            #     await bot.tree.remove_command(command=command.name, guild=guild_obj)

            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            print_log(f"\tSynced {len(synced)} commands for guild {guild.name}.")

            commands_reg = await bot.tree.fetch_commands(guild=guild_obj)
            names = [command.name for command in commands_reg]
            sorted_names = sorted(names)
            for command in sorted_names:
                print_log(f"\t✅ /{command}")

            bot.guild_emoji[guild.id] = {}
            for emoji in guild.emojis:
                bot.guild_emoji[guild.id][emoji.name] = emoji.id
                print_log(f"Guild emoji: {emoji.name} -> {emoji.id}")
            # In development, we show always the daily stats
            if ENV == "dev":
                tasks.append(send_daily_stats_to_a_guild(guild))
            tasks.append(send_daily_question_to_a_guild(bot, guild))

        # Cleanup task that runs every few seconds
        tasks.append(start_periodic_cache_cleanup())

        # Running all tasks concurrently and waiting for them to finish
        await asyncio.gather(*tasks)
        print_log("✅ on_ready() completed, bot is fully initialized.")

    def check_bot_permissions(self, channel: discord.TextChannel) -> dict:
        """Check the bot permissions in a specific channel"""
        bot_permissions = channel.permissions_for(channel.guild.me)

        permissions = {
            "read_messages": bot_permissions.read_messages,
            "send_messages": bot_permissions.send_messages,
            "manage_messages": bot_permissions.manage_messages,
            "add_reactions": bot_permissions.add_reactions,
            "read_message_history": bot_permissions.read_message_history,
            "mention_everyone": bot_permissions.mention_everyone,
        }

        return permissions

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        """
        Check if the user is the only one in the voice channel
        """
        if member.bot:
            return  # Ignore bot

        for guild in self.bot.guilds:
            guild_id = guild.id
            voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)

            if voice_channel_ids is None:
                print_warning_log(f"Voice channel not set for guild {guild.name}. Skipping.")
                continue
            schedule_text_channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
            if schedule_text_channel_id is None:
                print_warning_log(f"Text channel not set for guild {guild.name}. Skipping.")
                continue

            # Log user activity
            try:
                if before.channel is None and after.channel is not None:
                    # User joined a voice channel but wasn't in any voice channel before
                    channel_id = after.channel.id
                    event = EVENT_CONNECT
                    insert_user_activity(
                        member.id,
                        member.display_name,
                        channel_id,
                        guild_id,
                        event,
                        datetime.now(timezone.utc),
                    )

                    # Add the user to the voice channel list with the current siege activity detail
                    user_activity = get_siege_activity(member)
                    await data_access_update_voice_user_list(
                        guild_id, after.channel.id, member.id, user_activity.details if user_activity else None
                    )

                elif before.channel is not None and after.channel is None:
                    # User left a voice channel
                    channel_id = before.channel.id
                    event = EVENT_DISCONNECT
                    insert_user_activity(
                        member.id,
                        member.display_name,
                        channel_id,
                        guild_id,
                        event,
                        datetime.now(timezone.utc),
                    )
                    try:
                        await send_session_stats_to_queue(member, guild_id)
                    except Exception as e:
                        print_error_log(f"on_voice_state_update: Error sending user stats: {e}")

                    # Remove the user from the voice channel list (after.channel is None)
                    await data_access_remove_voice_user_list(guild_id, before.channel.id, member.id)
                elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
                    # User switched between voice channel
                    insert_user_activity(
                        member.id,
                        member.display_name,
                        before.channel.id,
                        guild_id,
                        EVENT_DISCONNECT,
                        datetime.now(timezone.utc),
                    )
                    insert_user_activity(
                        member.id,
                        member.display_name,
                        after.channel.id,
                        guild_id,
                        EVENT_CONNECT,
                        datetime.now(timezone.utc),
                    )
                    # Remove the user from the voice channel list (before.channel is different then the after, remove from before.channel)
                    await data_access_remove_voice_user_list(guild_id, before.channel.id, member.id)
                    # Add the user to the voice channel list with the current siege activity detail
                    user_activity = get_siege_activity(member)
                    await data_access_update_voice_user_list(
                        guild_id, after.channel.id, member.id, user_activity.details if user_activity else None
                    )
            except Exception as e:
                print_error_log(f"on_voice_state_update: Error logging user activity: {e}")

            # Check if the user joined a voice channel to send a voice message
            if after.channel is not None and after.channel.id in voice_channel_ids:
                # Check if the user is the only one in the voice channel
                if len(after.channel.members) == 1:
                    await send_notification_voice_channel(guild_id, member, after.channel, schedule_text_channel_id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Send message to new user
        """
        print_log("on_member_join called")
        if member.bot:
            return  # Ignore bot
        guild_id = member.guild.id
        text_channel_new_user_id: int = await data_access_get_new_user_text_channel_id(guild_id)
        if text_channel_new_user_id is None:
            print_warning_log(f"on_member_join: New user text channel not set for guild {member.guild.name}. Skipping.")
            return
        channel: discord.TextChannel = await data_access_get_channel(text_channel_new_user_id)
        if channel is None:
            print_warning_log(
                f"on_member_join: New user text channel not found for guild {member.guild.name}. Skipping."
            )
            return

        text_channel_id: int = await data_access_get_guild_schedule_text_channel_id(guild_id)
        if text_channel_id is None:
            print_warning_log(f"on_member_join: Schedule text channel not set for guild {member.guild.name}. Skipping.")
            return
        # Send message into the text channel with mention to the user to welcome them
        await channel.send(
            f"Welcome {member.mention} to the server! Use the command `/setupprofile` (in any text channel) to set up your profile which will give you a role and access to many voice channels. You can check who plan to play in the schedule channel <#{text_channel_id}>. When ready to play, join a voice channel and then use the command `/lfg` to find other players."
        )
        print_log(f"on_member_join: New user message sent to {member.display_name} in guild {member.guild.name}.")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Keep track of user activity"""
        if before.bot:
            return  # Ignore bot
        guild_id = before.guild.id
        guild_name = before.guild.name
        text_channel_main_siege_id: int = await data_access_get_main_text_channel_id(guild_id)
        if text_channel_main_siege_id is None:
            print_warning_log(f"on_member_update: Main Siege text channel id not set for guild {guild_name}. Skipping.")
            return
        channel: discord.TextChannel = await data_access_get_channel(text_channel_main_siege_id)
        if not channel:
            print_warning_log(f"on_member_update: New user text channel not found for guild {guild_name}. Skipping.")
            return

        # Check if the member is in a voice channel
        if not after.voice or not after.voice.channel:
            return  # Ignore users not in a voice channel

        # Check for activity changes
        before_activity = get_siege_activity(before)
        after_activity = get_siege_activity(after)
        before_details = before_activity.details if before_activity else None
        after_details = after_activity.details if after_activity else None

        if before_details != after_details:
            message = f"User {after.display_name} changed activity from {before_details} to {after_details}"
            print_log(message)
        # Add the user to the voice channel list with the current siege activity detail
        await data_access_update_voice_user_list(
            guild_id, after.voice.channel.id, after.id, ActivityTransition(before_details, after_details)
        )
        # await send_automatic_lfg_message(self.bot, after.guild, after.voice.channel)
        await self.send_automatic_lfg_message_debounced(guild_id, after.voice.channel.id)

    async def send_automatic_lfg_message_debounced(self, guild_id: int, channel_id: int) -> None:
        """
        Handle the request for a automatic message but if there is already a request, cancel it and wait again.
        The goal is to debounce and only act on the last operation
        """
        key = f"{guild_id}-{channel_id}"
        if key in self.last_task:
            task = self.last_task.get(key)
            task.cancel()  # Cancel any pending execution
        self.last_task[key] = asyncio.create_task(
            self.send_automatic_lfg_message_debounced_cancellable_task(guild_id, channel_id)
        )

    async def send_automatic_lfg_message_debounced_cancellable_task(self, guild_id: int, channel_id: int) -> None:
        """
        A task that can be cancelled and will wait for X seconds before sending the automatic message
        """
        await asyncio.sleep(5)  # Wait
        await send_automatic_lfg_message(
            self.bot, guild_id, channel_id
        )  # Send the actual command to see if we can send a message (depending of everyone state)
        self.last_task.pop(f"{guild_id}-{channel_id}", None)  # Remove the last task for the guild/channel


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(MyEventsCog(bot))
