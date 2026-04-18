"""
Events cog for the bot
Events are actions that the bot listens and reacts to
"""

import os
import asyncio
from typing import Any, cast
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from discord.ext import commands
import discord
from deps.ai.ai_functions import BotAISingleton
from deps.cache import start_periodic_cache_cleanup
from deps.analytic_data_access import insert_user_activity
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.data_access_data_class import UserInfo
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT, database_manager
from deps.bot_common_actions import (
    move_members_between_voice_channel,
    send_daily_question_to_a_guild,
    send_automatic_lfg_message,
    send_notification_voice_channel,
    send_session_stats_to_queue,
)
from deps.data_access import (
    data_access_get_channel,
    data_access_get_custom_game_voice_channels,
    data_access_get_guild_active_private_channels,
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_main_text_channel_id,
    data_access_get_new_user_text_channel_id,
    data_access_remove_guild_active_private_channel,
    data_access_remove_voice_user_list,
    data_access_update_voice_user_list,
    data_access_get_voice_user_list,
    data_access_get_last_match_start_gif_time,
    data_access_set_last_match_start_gif_time,
)
from deps.log import print_log, print_warning_log, print_error_log
from deps.functions_here_hints import content_suggests_ten_man_lfg
from deps.mybot import MyBot
from deps.values import (
    COMMAND_CUSTOM_GAME_LFG,
    COMMAND_CUSTOM_GAME_SUBSCRIBE,
    COMMAND_LFG,
)
from deps.models import ActivityTransition
from deps.siege import (
    get_any_siege_activity,
    get_aggregation_all_activities,
    get_statscc_activity,
    get_user_rank_siege,
    parse_statscc_ranked_score_from_activity,
)
from deps.follow_functions import send_private_notification_following_user

load_dotenv()

ENV = os.getenv("ENV")


def _is_loggable_voice_channel(channel: discord.abc.GuildChannel | None) -> bool:
    """Voice surfaces we record in user_activity and run follow notifications for."""
    return isinstance(channel, (discord.VoiceChannel, discord.StageChannel))


class MyEventsCog(commands.Cog):
    """
    Main events cog for the bot
    """

    lock = asyncio.Lock()

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.last_task: dict[str, asyncio.Task] = {}
        self.last_task_lock = asyncio.Lock()  # Protect concurrent access to last_task dictionary
        self.match_start_gif_locks: dict[str, asyncio.Lock] = {}
        self.match_start_gif_locks_creation_lock = asyncio.Lock()
        self.cleanup_task: asyncio.Task | None = None  # Store reference to prevent garbage collection
        # Track repeated private-channel deletion access failures to prune stale entries.
        self.private_channel_delete_failures: dict[tuple[int, int], int] = {}

    def _record_private_channel_delete_failure(self, guild_id: int, channel_id: int) -> int:
        key = (guild_id, channel_id)
        current = self.private_channel_delete_failures.get(key, 0) + 1
        self.private_channel_delete_failures[key] = current
        return current

    def _clear_private_channel_delete_failure(self, guild_id: int, channel_id: int) -> None:
        self.private_channel_delete_failures.pop((guild_id, channel_id), None)

    @staticmethod
    def _log_channel_move_sync(
        member_id: int,
        member_display_name: str,
        old_channel_id: int,
        new_channel_id: int,
        guild_id: int,
        move_time: datetime,
    ) -> None:
        """Helper to log channel move in database (runs in thread pool)"""
        with database_manager.data_access_transaction() as cursor:
            # Upsert user_info
            cursor.execute(
                """
                INSERT INTO user_info(id, display_name)
                VALUES(:user_id, :user_display_name)
                ON CONFLICT(id) DO UPDATE SET display_name = :user_display_name
                WHERE id = :user_id;
                """,
                {"user_id": member_id, "user_display_name": member_display_name},
            )

            # Insert DISCONNECT from old channel
            cursor.execute(
                """
                INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
                VALUES (:user_id, :channel_id, :guild_id, :event, :time)
                """,
                {
                    "user_id": member_id,
                    "channel_id": old_channel_id,
                    "guild_id": guild_id,
                    "event": EVENT_DISCONNECT,
                    "time": move_time.isoformat(),
                },
            )

            # Insert CONNECT to new channel
            cursor.execute(
                """
                INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
                VALUES (:user_id, :channel_id, :guild_id, :event, :time)
                """,
                {
                    "user_id": member_id,
                    "channel_id": new_channel_id,
                    "guild_id": guild_id,
                    "event": EVENT_CONNECT,
                    "time": move_time.isoformat(),
                },
            )

    @staticmethod
    def _normalize_message_mentions(message: discord.Message) -> str:
        """
        Replace raw Discord mention tokens with stable display names for AI prompts.
        """
        content = message.content
        for mentioned_user in message.mentions:
            replacement = f"@{mentioned_user.display_name}"
            content = content.replace(f"<@{mentioned_user.id}>", replacement)
            content = content.replace(f"<@!{mentioned_user.id}>", replacement)
            content = content.replace(mentioned_user.mention, replacement)
        return content

    @staticmethod
    async def _resolve_user_mentions(message: discord.Message, bot_user_id: int) -> list[UserInfo]:
        """
        Resolve mentioned Discord users into UserInfo-like identities for AI prompts.
        """
        resolved_mentions: list[UserInfo] = []
        seen_user_ids: set[int] = set()

        for mentioned_user in message.mentions:
            if mentioned_user.id == bot_user_id or mentioned_user.id in seen_user_ids:
                continue

            seen_user_ids.add(mentioned_user.id)
            user_info = await fetch_user_info_by_user_id(mentioned_user.id)
            if user_info is None:
                user_info = UserInfo(
                    id=mentioned_user.id,
                    display_name=mentioned_user.display_name,
                    ubisoft_username_max=None,
                    ubisoft_username_active=None,
                    r6_tracker_active_id=None,
                    time_zone="US/Eastern",
                    max_mmr=0,
                )
            else:
                user_info = UserInfo(
                    id=user_info.id,
                    display_name=mentioned_user.display_name,
                    ubisoft_username_max=user_info.ubisoft_username_max,
                    ubisoft_username_active=user_info.ubisoft_username_active,
                    r6_tracker_active_id=user_info.r6_tracker_active_id,
                    time_zone=user_info.time_zone,
                    max_mmr=user_info.max_mmr,
                )
            resolved_mentions.append(user_info)

        return resolved_mentions

    @commands.Cog.listener()
    async def on_ready(self):
        """Main function to run when the bot is ready"""
        bot = self.bot
        print_log(f"{bot.user} has connected to Discord!")
        print_log(f"Bot latency: {bot.latency} seconds")
        tasks = []
        # Load ai data
        await BotAISingleton().bot.load_initial_value()
        print_log("✅ AI Counted loaded")
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

        # Start cleanup task that runs in background
        # Store reference to prevent garbage collection
        self.cleanup_task = start_periodic_cache_cleanup()
        print_log("✅ Started periodic cache cleanup task")

        # Running all tasks concurrently and waiting for them to finish
        if tasks:
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
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        """
        Check if the user is the only one in the voice channel
        """
        if member.bot:
            return  # Ignore bot

        guild = member.guild
        guild_id = guild.id

        # Fetch all active private channels once; used for deletion below
        active_private_channels = await data_access_get_guild_active_private_channels(guild_id)
        all_private_ids: set[int] = set(active_private_channels.keys())

        # Always delete a private channel when it becomes empty, regardless of guild config
        left_channel = before.channel if (before.channel is not None and after.channel != before.channel) else None
        if left_channel is not None and left_channel.id in all_private_ids:
            try:
                # Discord can momentarily keep the leaving member in before.channel.members.
                # Treat a channel with only the leaving member as effectively empty.
                members = list(left_channel.members)
                is_effectively_empty = len(members) == 0 or (
                    len(members) == 1 and any(m.id == member.id for m in members)
                )
                if is_effectively_empty:
                    bot_member = guild.me
                    if bot_member is None:
                        print_warning_log(
                            f"on_voice_state_update: Cannot delete private channel {left_channel.id} in guild {guild_id} because bot member is unavailable."
                        )
                    else:
                        bot_permissions = left_channel.permissions_for(bot_member)
                        if not bot_permissions.view_channel or not bot_permissions.manage_channels:
                            missing: list[str] = []
                            if not bot_permissions.view_channel:
                                missing.append("View Channel")
                            if not bot_permissions.manage_channels:
                                missing.append("Manage Channels")
                            print_warning_log(
                                "on_voice_state_update: Cannot delete private channel "
                                f"{left_channel.id} in guild {guild_id}; missing {', '.join(missing)}."
                            )
                        else:
                            await left_channel.delete(reason="Private channel is empty")
                            await data_access_remove_guild_active_private_channel(guild_id, left_channel.id)
                            self._clear_private_channel_delete_failure(guild_id, left_channel.id)
                        if not bot_permissions.view_channel or not bot_permissions.manage_channels:
                            failure_count = self._record_private_channel_delete_failure(guild_id, left_channel.id)
                            if failure_count >= 3:
                                await data_access_remove_guild_active_private_channel(guild_id, left_channel.id)
                                self._clear_private_channel_delete_failure(guild_id, left_channel.id)
                                print_warning_log(
                                    "on_voice_state_update: Removed stale private channel entry after repeated "
                                    f"missing-access deletion failures for channel {left_channel.id} in guild {guild_id}."
                                )
            except discord.NotFound:
                await data_access_remove_guild_active_private_channel(guild_id, left_channel.id)
                self._clear_private_channel_delete_failure(guild_id, left_channel.id)
            except discord.Forbidden as e:
                failure_count = self._record_private_channel_delete_failure(guild_id, left_channel.id)
                print_warning_log(
                    "on_voice_state_update: Missing access deleting private channel "
                    f"{left_channel.id} in guild {guild_id} (attempt {failure_count}/3): {e}"
                )
                if failure_count >= 3:
                    await data_access_remove_guild_active_private_channel(guild_id, left_channel.id)
                    self._clear_private_channel_delete_failure(guild_id, left_channel.id)
                    print_warning_log(
                        "on_voice_state_update: Removed stale private channel entry after repeated "
                        f"forbidden deletion failures for channel {left_channel.id} in guild {guild_id}."
                    )
            except Exception as e:
                print_error_log(f"on_voice_state_update: Error deleting private channel: {e}")

        lfg_voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)
        lfg_voice_channel_ids_set: set[int] = set(lfg_voice_channel_ids) if lfg_voice_channel_ids is not None else set()

        # Log user activity (all voice/stage channels). LFG stays admin-configured only (below).
        try:
            if before.channel is None and after.channel is not None:
                # User joined a voice channel
                if _is_loggable_voice_channel(after.channel):
                    channel_id = after.channel.id
                    insert_user_activity(
                        member.id,
                        member.display_name,
                        channel_id,
                        guild_id,
                        EVENT_CONNECT,
                        datetime.now(timezone.utc),
                    )

                    # Add the user to the voice channel list with the current siege activity detail
                    user_activity = get_any_siege_activity(member)
                    await data_access_update_voice_user_list(
                        guild_id,
                        after.channel.id,
                        member.id,
                        user_activity.details if user_activity else None,
                    )

                    # When a user joins a voice channel, notify users who follow this member (any loggable VC)
                    try:
                        await send_private_notification_following_user(self.bot, member.id, guild_id, channel_id)
                    except Exception as e:
                        print_error_log(f"on_voice_state_update: Error sending follow notification: {e}")

            elif before.channel is not None and after.channel is None:
                # User left a voice channel
                if _is_loggable_voice_channel(before.channel):
                    channel_id = before.channel.id
                    await asyncio.to_thread(
                        insert_user_activity,
                        member.id,
                        member.display_name,
                        channel_id,
                        guild_id,
                        EVENT_DISCONNECT,
                        datetime.now(timezone.utc),
                    )
                try:
                    await send_session_stats_to_queue(member, guild_id)
                except Exception as e:
                    print_error_log(f"on_voice_state_update: Error sending user stats: {e}")

                # Remove the user from the voice channel list (after.channel is None)
                await data_access_remove_voice_user_list(guild_id, before.channel.id, member.id)

            elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
                # User switched between voice channels
                before_loggable = _is_loggable_voice_channel(before.channel)
                after_loggable = _is_loggable_voice_channel(after.channel)
                try:
                    move_time = datetime.now(timezone.utc)
                    if before_loggable and after_loggable:
                        await asyncio.to_thread(
                            self._log_channel_move_sync,
                            member.id,
                            member.display_name,
                            before.channel.id,
                            after.channel.id,
                            guild_id,
                            move_time,
                        )
                    elif before_loggable:
                        await asyncio.to_thread(
                            insert_user_activity,
                            member.id,
                            member.display_name,
                            before.channel.id,
                            guild_id,
                            EVENT_DISCONNECT,
                            move_time,
                        )
                    elif after_loggable:
                        await asyncio.to_thread(
                            insert_user_activity,
                            member.id,
                            member.display_name,
                            after.channel.id,
                            guild_id,
                            EVENT_CONNECT,
                            move_time,
                        )
                except Exception as e:
                    print_error_log(f"on_voice_state_update: Error logging channel move: {e}")

                # Update voice user list cache (always, regardless of tracking)
                await data_access_remove_voice_user_list(guild_id, before.channel.id, member.id)
                user_activity = get_any_siege_activity(member)
                await data_access_update_voice_user_list(
                    guild_id,
                    after.channel.id,
                    member.id,
                    user_activity.details if user_activity else None,
                )
        except Exception as e:
            print_error_log(f"on_voice_state_update: Error logging user activity: {e}")

        # LFG notification (only for admin-configured voice channels; schedule channel required for that only)
        if after.channel is not None and after.channel.id in lfg_voice_channel_ids_set:
            if len(after.channel.members) == 1:
                schedule_text_channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
                if schedule_text_channel_id is None:
                    print_warning_log(
                        f"Schedule text channel not set for guild {guild.name}; cannot send LFG notification."
                    )
                else:
                    await send_notification_voice_channel(
                        guild_id,
                        member,
                        after.channel,
                        schedule_text_channel_id,
                    )

    @commands.Cog.listener()
    async def on_close(self):
        """
        Handle bot shutdown by closing all open voice sessions.
        Ensures every CONNECT event has a matching DISCONNECT.
        """
        print_log("Bot shutting down - closing all open voice sessions")

        for guild in self.bot.guilds:
            guild_id = guild.id
            voice_like_channels: list[discord.VoiceChannel | discord.StageChannel] = [
                *guild.voice_channels,
                *guild.stage_channels,
            ]
            for channel in voice_like_channels:
                try:
                    for member in channel.members:
                        if not member.bot:
                            await asyncio.to_thread(
                                insert_user_activity,
                                member.id,
                                member.display_name,
                                channel.id,
                                guild_id,
                                EVENT_DISCONNECT,
                                datetime.now(timezone.utc),
                            )
                            print_log(f"Shutdown cleanup: Disconnected {member.display_name} from {channel.name}")
                except Exception as e:
                    print_error_log(f"on_close: Error processing channel {channel.id} in guild {guild_id}: {e}")

        print_log("Shutdown cleanup completed")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """
        Send message to new user
        """
        print_log("on_member_join called")
        if member.bot:
            return  # Ignore bot
        guild_id = member.guild.id
        if guild_id is None:
            print_warning_log("on_member_join: Guild ID not found. Skipping.")
            return
        text_channel_new_user_id = await data_access_get_new_user_text_channel_id(guild_id)
        if text_channel_new_user_id is None:
            print_warning_log(f"on_member_join: New user text channel not set for guild {member.guild.name}. Skipping.")
            return
        channel = await data_access_get_channel(text_channel_new_user_id)
        if channel is None:
            print_warning_log(
                f"on_member_join: New user text channel not found for guild {member.guild.name}. Skipping."
            )
            return

        text_channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
        if text_channel_id is None:
            print_warning_log(f"on_member_join: Schedule text channel not set for guild {member.guild.name}. Skipping.")
            return
        # Send message into the text channel with mention to the user to welcome them
        await channel.send(
            f"""Welcome {member.mention} to the server! Use the command `/setupprofile` (in any text channel) to set up your profile which will give you a role and access to many voice channels. You can check who plan to play in the schedule channel <#{text_channel_id}>. When ready to play, join a voice channel and then use the command `/lfg` to find other players."""
        )
        print_log(f"on_member_join: New user message sent to {member.display_name} in guild {member.guild.name}.")

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        """Keep track of user activity"""
        if before.bot:
            return  # Ignore bot
        guild_id = before.guild.id
        guild_name = before.guild.name
        text_channel_main_siege_id = await data_access_get_main_text_channel_id(guild_id)
        if text_channel_main_siege_id is None:
            print_warning_log(
                f"on_presence_update: Main Siege text channel id not set for guild {guild_name}. Skipping."
            )
            return
        channel = await data_access_get_channel(text_channel_main_siege_id)
        if not channel:
            print_warning_log(f"on_presence_update: New user text channel not found for guild {guild_name}. Skipping.")
            return

        # Check if the member is in a voice channel
        if not after.voice or not after.voice.channel:
            return  # Ignore users not in a voice channel

        # Check for activity changes
        before_activity = get_any_siege_activity(before)
        after_activity = get_any_siege_activity(after)
        before_details = before_activity.details if before_activity else None
        after_details = after_activity.details if after_activity else None

        if before_details != after_details:
            message = f"on_presence_update: User {after.display_name} changed activity from {before_details} to {after_details}"
            print_log(message)
        # Add the user to the voice channel list with the current siege activity detail
        await data_access_update_voice_user_list(
            guild_id,
            after.voice.channel.id,
            after.id,
            ActivityTransition(before_details, after_details),
        )

        # Automatic send in the Siege text message a "looking for game" message
        await self.send_automatic_lfg_message_debounced(guild_id, after.voice.channel.id)

        # Check for match start and send animated GIF
        await self.send_match_start_gif_debounced(guild_id, after.voice.channel.id)

        # stats.cc ranked score changes: debounce then update pending match-start GIF (in-round or match end)
        after_stats_cc = get_statscc_activity(after)
        before_stats_cc = get_statscc_activity(before)
        parsed_ranked_after = (
            parse_statscc_ranked_score_from_activity(after_stats_cc) if after_stats_cc is not None else None
        )
        parsed_ranked_before = (
            parse_statscc_ranked_score_from_activity(before_stats_cc) if before_stats_cc is not None else None
        )
        schedule_gif_result_update = False
        if parsed_ranked_after is not None and after_stats_cc is not None:
            before_state = before_stats_cc.state if before_stats_cc else None
            after_state = after_stats_cc.state
            before_details_cc = before_stats_cc.details if before_stats_cc else None
            after_details_cc = after_stats_cc.details
            if before_state != after_state or before_details_cc != after_details_cc:
                schedule_gif_result_update = True
        elif parsed_ranked_before is not None and parsed_ranked_after is None:
            # Lost parseable ranked score (menu, queue, activity cleared) — schedule one more read so we can
            # still pick up the final score from debounced member fetch or from another player in the VC.
            schedule_gif_result_update = True
        if schedule_gif_result_update:
            await self.update_match_start_gif_result_debounced(guild_id, after.voice.channel.id)

        # Check that the detail variables exist BEFORE checking their contents
        # if before_details and after_details and after.voice and after.voice.channel:
        #     if "CUSTOM GAME match" in before_details and "MENU" in after_details:
        #         await self.auto_move_custom_game_debounced(guild_id, after.voice.channel.id)

    async def send_automatic_lfg_message_debounced(self, guild_id: int, channel_id: int) -> None:
        """
        Handle the request for a automatic message but if there is already a request, cancel it and wait again.
        The goal is to debounce and only act on the last operation
        """
        key = f"lfg-{guild_id}-{channel_id}"
        async with self.last_task_lock:
            if key in self.last_task:
                task = self.last_task.get(key)
                if task is not None:
                    task.cancel()  # Cancel any pending execution
            self.last_task[key] = asyncio.create_task(
                self.send_automatic_lfg_message_debounced_cancellable_task(guild_id, channel_id)
            )

    async def send_automatic_lfg_message_debounced_cancellable_task(self, guild_id: int, channel_id: int) -> None:
        """
        A task that can be cancelled and will wait for X seconds before sending the automatic message
        """
        try:
            await asyncio.sleep(5)  # Wait
            await send_automatic_lfg_message(
                self.bot, guild_id, channel_id
            )  # Send the actual command to see if we can send a message (depending of everyone state)
        except asyncio.CancelledError:
            pass  # Task was cancelled, cleanup will happen in finally
        finally:
            async with self.last_task_lock:
                self.last_task.pop(f"lfg-{guild_id}-{channel_id}", None)  # Remove the last task for the guild/channel

    async def send_match_start_gif_debounced(self, guild_id: int, channel_id: int) -> None:
        """
        Handle the request for match start GIF generation with debouncing.
        The goal is to debounce and only act on the last operation.
        """
        key = f"matchstartgif-{guild_id}-{channel_id}"
        async with self.last_task_lock:
            if key in self.last_task:
                task = self.last_task.get(key)
                if task is not None:
                    task.cancel()  # Cancel any pending execution
            self.last_task[key] = asyncio.create_task(
                self.send_match_start_gif_debounced_cancellable_task(guild_id, channel_id)
            )

    async def send_match_start_gif_debounced_cancellable_task(self, guild_id: int, channel_id: int) -> None:
        """
        A task that can be cancelled and will wait for X seconds before checking if a ranked match started.
        """
        lock_key = f"{guild_id}:{channel_id}"

        # Ensure we have a lock for this channel BEFORE the sleep
        # Use a creation lock to prevent race condition where multiple tasks create separate locks
        async with self.match_start_gif_locks_creation_lock:
            if lock_key not in self.match_start_gif_locks:
                self.match_start_gif_locks[lock_key] = asyncio.Lock()

        try:
            await asyncio.sleep(5)  # Wait for all presence updates to settle

            # Use a lock to prevent multiple GIFs from being sent simultaneously for the same channel
            async with self.match_start_gif_locks[lock_key]:
                # Check if 1+ users just started a ranked match (not just queuing, but actually in match)
                # We detect this by looking for users who transitioned TO ranked-specific states like
                # "Picking Operators: Ranked on..." which indicates match actually started
                user_activities = await data_access_get_voice_user_list(guild_id, channel_id)
                aggregation = get_aggregation_all_activities(user_activities)
                number_users = len(user_activities)
                if aggregation.looking_ranked_match >= 1 and number_users >= 2:
                    print_log(f"Detected ranked match start in guild {guild_id}, channel {channel_id}. Sending GIF.")
                    # Rate limit: once per hour per channel
                    last_time = await data_access_get_last_match_start_gif_time(guild_id, channel_id)
                    if last_time is None or (datetime.now(timezone.utc) - last_time) > timedelta(minutes=15):
                        from deps.bot_common_actions import send_match_start_gif

                        await send_match_start_gif(self.bot, guild_id, channel_id)
                        await data_access_set_last_match_start_gif_time(
                            guild_id, channel_id, datetime.now(timezone.utc)
                        )
                    else:
                        print_log(
                            f"Match start GIF recently sent for guild {guild_id}, channel {channel_id}. Skipping."
                        )
        except asyncio.CancelledError:
            # Task was cancelled during sleep, this is expected
            pass
        except Exception as e:
            print_error_log(f"send_match_start_gif_debounced_cancellable_task: {e}")
        finally:
            async with self.last_task_lock:
                self.last_task.pop(f"matchstartgif-{guild_id}-{channel_id}", None)

    async def update_match_start_gif_result_debounced(self, guild_id: int, channel_id: int) -> None:
        """Debounce stats.cc ranked score updates so multiple members do not race GIF regeneration."""
        key = f"matchgifresult-{guild_id}-{channel_id}"
        async with self.last_task_lock:
            if key in self.last_task:
                task = self.last_task.get(key)
                if task is not None:
                    task.cancel()
            self.last_task[key] = asyncio.create_task(
                self.update_match_start_gif_result_debounced_cancellable_task(guild_id, channel_id)
            )

    async def update_match_start_gif_result_debounced_cancellable_task(self, guild_id: int, channel_id: int) -> None:
        try:
            await asyncio.sleep(4)
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                return
            from deps.bot_common_actions import try_update_match_start_gif_with_result

            await try_update_match_start_gif_with_result(self.bot, guild, channel_id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print_error_log(f"update_match_start_gif_result_debounced_cancellable_task: {e}")
        finally:
            async with self.last_task_lock:
                self.last_task.pop(f"matchgifresult-{guild_id}-{channel_id}", None)

    async def auto_move_custom_game_debounced(self, guild_id: int, channel_id: int) -> None:
        """
        Handle the request for auto move custom game but if there is already a request, cancel it and wait again.
        The goal is to debounce and only act on the last operation
        """
        key = f"customgame-{guild_id}-{channel_id}"
        async with self.last_task_lock:
            if key in self.last_task:
                task = self.last_task.get(key)
                if task is not None:
                    task.cancel()  # Cancel any pending execution
            self.last_task[key] = asyncio.create_task(
                self.auto_move_custom_game_debounced_cancellable_task(guild_id, channel_id)
            )

    async def auto_move_custom_game_debounced_cancellable_task(self, guild_id: int, channel_id: int) -> None:
        """
        A task that can be cancelled and will wait for X seconds before sending the automatic message
        """
        try:
            lobby_channel_id, team1_channel_id, team2_channel_id = await data_access_get_custom_game_voice_channels(
                guild_id
            )
            if lobby_channel_id is None or team1_channel_id is None or team2_channel_id is None:
                print_warning_log(
                    f"auto_move_custom_game_debounced_cancellable_task: Custom game channel ids not configured for guild {guild_id}. Skipping."
                )
                return
            lobby_channel = await data_access_get_channel(lobby_channel_id)
            team1_channel = await data_access_get_channel(team1_channel_id)
            team2_channel = await data_access_get_channel(team2_channel_id)
            if lobby_channel is None or team1_channel is None or team2_channel is None:
                print_warning_log(
                    f"auto_move_custom_game_debounced_cancellable_task: One of the custom game channels not found for guild {guild_id}. Skipping."
                )
                return
            if channel_id not in [team1_channel.id, team2_channel.id]:
                print_warning_log(
                    f"auto_move_custom_game_debounced_cancellable_task: Channel {channel_id} is not a custom game team channel for guild {guild_id}. Skipping."
                )
                return
            await asyncio.sleep(
                2
            )  # Wait since many people might have the same update (10 people playing the custom game)
            # Voice channels; stubs type data_access_get_channel as TextChannel-only.
            await move_members_between_voice_channel(cast(Any, team1_channel), cast(Any, lobby_channel))
            await move_members_between_voice_channel(cast(Any, team2_channel), cast(Any, lobby_channel))
        except asyncio.CancelledError:
            pass  # Task was cancelled, cleanup will happen in finally
        except Exception as e:
            print_error_log(f"auto_move_custom_game_debounced_cancellable_task: Error moving custom game users: {e}")
        finally:
            async with self.last_task_lock:
                self.last_task.pop(
                    f"customgame-{guild_id}-{channel_id}", None
                )  # Remove the last task for the guild/channel

    @commands.Cog.listener()
    async def on_message(self, message) -> None:
        """
        Make the bot aware if someone mentions it in a message
        """
        # Ignore messages from the bot itself
        if message.author == self.bot.user:
            return

        # @here education: mention_everyone is set for both @here and @everyone; only nudge on literal @here
        if (
            message.guild is not None
            and not message.author.bot
            and isinstance(message.channel, (discord.TextChannel, discord.Thread))
            and message.mention_everyone
            and "@here" in message.content
        ):
            if content_suggests_ten_man_lfg(message.content):
                reply = (
                    f"{message.author.mention} For 10-man / custom game LFG, `@here` is not the usual pattern — "
                    f"use `/{COMMAND_CUSTOM_GAME_LFG}` to ping subscribers and `/{COMMAND_CUSTOM_GAME_SUBSCRIBE}` "
                    "to join the notification list."
                )
            else:
                reply = (
                    f"{message.author.mention} For general LFG, try `/{COMMAND_LFG}` instead of `@here` "
                    "(you need to be in a voice channel for that command to work)."
                )
            try:
                await message.channel.send(reply)
            except discord.Forbidden as e:
                print_warning_log(f"on_message @here hint: missing permission to send in channel: {e}")
            except discord.HTTPException as e:
                print_error_log(f"on_message @here hint: HTTP error sending reply: {e}")

        # Check if the bot was mentioned
        if self.bot.user in message.mentions:
            if BotAISingleton().bot.is_running():
                await message.channel.send(
                    message.author.mention + " I am already working on a inquiry. Give me more time and try later."
                )
            else:
                message_ref = await message.channel.send(
                    message.author.mention
                    + " Hi! I am here to help you. Please wait a moment (might take a minute) while I process your request... I will edit this message with the response if I can figure it out."
                )
                # Fetch the last 8 messages in the same channel
                before_replied_msg = []
                if message.reference is not None:
                    replied_message = await message.channel.fetch_message(message.reference.message_id)
                    # If the message is a reply, we can fetch the last x messages before the replied message
                    before_replied_msg = [
                        msg async for msg in message.channel.history(limit=8, before=replied_message.created_at)
                    ]
                current_replied_msg = [message]
                last_messages_channel = [msg async for msg in message.channel.history(limit=8)]
                messages: list[discord.Message] = before_replied_msg + current_replied_msg + last_messages_channel
                # Remove duplicates and sort by creation time
                messages = list({m.id: m for m in messages}.values())
                messages.sort(key=lambda m: m.created_at)
                context = "\n".join(
                    f"{m.author.display_name} said: {self._normalize_message_mentions(m)}" for m in messages
                )
                try:
                    user_rank = get_user_rank_siege(message.author)
                    bot_user = self.bot.user
                    if bot_user is None:
                        return
                    resolved_mentions = await self._resolve_user_mentions(message, bot_user.id)
                    response = await asyncio.to_thread(
                        lambda: asyncio.run(
                            BotAISingleton().bot.generate_answer_when_mentioning_bot(
                                message.guild.id if message.guild is not None else None,
                                context,
                                self._normalize_message_mentions(message),
                                resolved_mentions,
                                message.author.display_name,
                                message.author.id,
                                user_rank,
                            )
                        )
                    )
                    if response is not None:
                        await message_ref.edit(content="✅ " + message.author.mention + " " + response)
                    else:
                        await message_ref.edit(
                            content="⛔ " + message.author.mention + " I am sorry, I could not process your request."
                        )
                except Exception as e:
                    print_error_log(f"on_message: Error processing message: {e}")
                    await message_ref.edit(
                        content=message.author.mention
                        + " I am sorry, I encountered an error while processing your request."
                    )
        # Make sure other commands still work
        await self.bot.process_commands(message)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(MyEventsCog(bot))
