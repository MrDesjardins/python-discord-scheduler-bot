"""
Events cog for the bot
Events are actions that the bot listens and reacts to
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from discord.ext import commands
import discord
from deps.ai.ai_functions import BotAISingleton
from deps.cache import start_periodic_cache_cleanup
from deps.analytic_data_access import insert_user_activity
from deps.system_database import EVENT_CONNECT, EVENT_DISCONNECT
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
    data_access_get_guild_schedule_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_main_text_channel_id,
    data_access_get_new_user_text_channel_id,
    data_access_remove_voice_user_list,
    data_access_update_voice_user_list,
    data_access_get_voice_user_list,
    data_access_get_last_match_start_gif_time,
    data_access_set_last_match_start_gif_time,
)
from deps.log import print_log, print_warning_log, print_error_log
from deps.mybot import MyBot
from deps.models import ActivityTransition
from deps.siege import get_siege_activity, get_user_rank_siege, get_aggregation_siege_activity
from deps.follow_functions import send_private_notification_following_user

load_dotenv()

ENV = os.getenv("ENV")


class MyEventsCog(commands.Cog):
    """
    Main events cog for the bot
    """

    lock = asyncio.Lock()

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.last_task: dict[str, asyncio.Task] = {}

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

        # FIX: Process only member's guild, not all guilds
        guild = member.guild
        guild_id = guild.id
        voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)

        if voice_channel_ids is None:
            print_warning_log(f"Voice channel not set for guild {guild.name}. Skipping.")
            return
        schedule_text_channel_id = await data_access_get_guild_schedule_text_channel_id(guild_id)
        if schedule_text_channel_id is None:
            print_warning_log(f"Schedule text channel not set for guild {guild.name}. Skipping.")
            return

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
                    guild_id,
                    after.channel.id,
                    member.id,
                    user_activity.details if user_activity else None,
                )

                # When a user joins a voice channel, we see if someone is following that new user to send a private message
                try:
                    await send_private_notification_following_user(self.bot, member.id, guild_id, channel_id)
                except Exception as e:
                    print_error_log(f"on_voice_state_update: Error sending follow notification: {e}")

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
                # User switched between voice channels
                # FIX: Use transaction to make channel move atomic
                from deps.system_database import database_manager

                try:
                    with database_manager.data_access_transaction() as cursor:
                        move_time = datetime.now(timezone.utc)

                        # Upsert user_info
                        cursor.execute(
                            """
                            INSERT INTO user_info(id, display_name)
                            VALUES(:user_id, :user_display_name)
                            ON CONFLICT(id) DO UPDATE SET display_name = :user_display_name
                            WHERE id = :user_id;
                            """,
                            {"user_id": member.id, "user_display_name": member.display_name},
                        )

                        # Insert DISCONNECT from old channel
                        cursor.execute(
                            """
                            INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
                            VALUES (:user_id, :channel_id, :guild_id, :event, :time)
                            """,
                            {
                                "user_id": member.id,
                                "channel_id": before.channel.id,
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
                                "user_id": member.id,
                                "channel_id": after.channel.id,
                                "guild_id": guild_id,
                                "event": EVENT_CONNECT,
                                "time": move_time.isoformat(),
                            },
                        )
                        # Transaction commits on context manager exit
                except Exception as e:
                    print_error_log(f"on_voice_state_update: Error logging channel move: {e}")
                    # Transaction rolls back on exception

                # Update cache (after transaction)
                await data_access_remove_voice_user_list(guild_id, before.channel.id, member.id)
                user_activity = get_siege_activity(member)
                await data_access_update_voice_user_list(
                    guild_id,
                    after.channel.id,
                    member.id,
                    user_activity.details if user_activity else None,
                )
        except Exception as e:
            print_error_log(f"on_voice_state_update: Error logging user activity: {e}")

        # Check if the user joined a voice channel to send a voice message
        if after.channel is not None and after.channel.id in voice_channel_ids:
            # Check if the user is the only one in the voice channel
            if len(after.channel.members) == 1:
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
            voice_channel_ids = await data_access_get_guild_voice_channel_ids(guild_id)

            if voice_channel_ids is None:
                continue

            for voice_channel_id in voice_channel_ids:
                try:
                    channel = await data_access_get_channel(voice_channel_id)
                    if channel is None or not isinstance(channel, discord.VoiceChannel):
                        continue

                    # Insert DISCONNECT for all members in channel
                    for member in channel.members:
                        if not member.bot:
                            insert_user_activity(
                                member.id,
                                member.display_name,
                                voice_channel_id,
                                guild_id,
                                EVENT_DISCONNECT,
                                datetime.now(timezone.utc),
                            )
                            print_log(f"Shutdown cleanup: Disconnected {member.display_name} from {channel.name}")
                except Exception as e:
                    print_error_log(f"on_close: Error processing channel {voice_channel_id}: {e}")

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
            print_warning_log(f"on_presence_update: Main Siege text channel id not set for guild {guild_name}. Skipping.")
            return
        channel = await data_access_get_channel(text_channel_main_siege_id)
        if not channel:
            print_warning_log(f"on_presence_update: New user text channel not found for guild {guild_name}. Skipping.")
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
        await asyncio.sleep(5)  # Wait
        await send_automatic_lfg_message(
            self.bot, guild_id, channel_id
        )  # Send the actual command to see if we can send a message (depending of everyone state)
        self.last_task.pop(f"lfg-{guild_id}-{channel_id}", None)  # Remove the last task for the guild/channel

    async def send_match_start_gif_debounced(self, guild_id: int, channel_id: int) -> None:
        """
        Handle the request for match start GIF generation with debouncing.
        The goal is to debounce and only act on the last operation.
        """
        key = f"matchstartgif-{guild_id}-{channel_id}"
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
        try:
            await asyncio.sleep(5)  # Wait for all presence updates to settle

            # Check if 1+ users are now looking for a ranked match
            user_activities = await data_access_get_voice_user_list(guild_id, channel_id)
            aggregation = get_aggregation_siege_activity(user_activities)
            number_users = len(user_activities)
            if aggregation.looking_ranked_match >= 1 and number_users >= 2:
                print_log(f"Detected ranked match start in guild {guild_id}, channel {channel_id}. Sending GIF.")
                # Rate limit: once per hour per channel
                last_time = await data_access_get_last_match_start_gif_time(guild_id, channel_id)
                if last_time is None or (datetime.now(timezone.utc) - last_time) > timedelta(minutes=15):
                    from deps.bot_common_actions import send_match_start_gif

                    await send_match_start_gif(self.bot, guild_id, channel_id)
                    await data_access_set_last_match_start_gif_time(guild_id, channel_id, datetime.now(timezone.utc))
                else:
                    print_log(f"Match start GIF recently sent for guild {guild_id}, channel {channel_id}. Skipping.")
        except Exception as e:
            print_error_log(f"send_match_start_gif_debounced_cancellable_task: {e}")
        finally:
            self.last_task.pop(f"matchstartgif-{guild_id}-{channel_id}", None)

    async def auto_move_custom_game_debounced(self, guild_id: int, channel_id: int) -> None:
        """
        Handle the request for auto move custom game but if there is already a request, cancel it and wait again.
        The goal is to debounce and only act on the last operation
        """
        key = f"customgame-{guild_id}-{channel_id}"
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
            await move_members_between_voice_channel(team1_channel, lobby_channel)
            await move_members_between_voice_channel(team2_channel, lobby_channel)
        except Exception as e:
            print_error_log(f"auto_move_custom_game_debounced_cancellable_task: Error moving custom game users: {e}")
        finally:
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
                context = "\n".join(f"{m.author.display_name} said: {m.content}" for m in messages)
                try:
                    user_rank = get_user_rank_siege(message.author)
                    response = await asyncio.to_thread(
                        lambda: asyncio.run(
                            BotAISingleton().bot.generate_answer_when_mentioning_bot(
                                context, message.content, message.author.display_name, message.author.id, user_rank
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
