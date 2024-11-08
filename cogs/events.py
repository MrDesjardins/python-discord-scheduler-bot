from datetime import datetime, timedelta, timezone
from typing import Optional
import asyncio
from discord.ext import commands
import discord
from deps.analytic_data_access import fetch_user_info_by_user_id, insert_user_activity
from deps.analytic_database import EVENT_CONNECT, EVENT_DISCONNECT
from deps.data_access_data_class import UserInfo
from deps.bot_common_actions import send_daily_question_to_a_guild, send_notification_voice_channel, update_vote_message
from deps.data_access import (
    data_access_get_channel,
    data_access_get_gaming_session_last_activity,
    data_access_get_gaming_session_text_channel_id,
    data_access_get_guild,
    data_access_get_guild_text_channel_id,
    data_access_get_guild_voice_channel_ids,
    data_access_get_member,
    data_access_get_message,
    data_access_get_reaction_message,
    data_access_get_user,
    data_access_set_gaming_session_last_activity,
    data_access_set_reaction_message,
)
from deps.log import print_log, print_warning_log, print_error_log
from deps.mybot import MyBot
from deps.functions import get_empty_votes
from deps.functions_r6_tracker import get_r6tracker_user_recent_matches, get_user_gaming_session_stats
from deps.models import SimpleUser, UserMatchInfoSessionAggregate
from deps.siege import get_color_for_rank, get_user_rank_emoji
from deps.values import EMOJI_TO_TIME


class MyEventsCog(commands.Cog):
    lock = asyncio.Lock()

    def __init__(self, bot: MyBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        """Main function to run when the bot is ready"""
        bot = self.bot
        print_log(f"{bot.user} has connected to Discord!")
        print_log(f"Bot latency: {bot.latency} seconds")
        tasks = []
        for guild in bot.guilds:
            print_log(f"Checking in guild: {guild.name} ({guild.id})")
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
            for command in commands_reg:
                print_log(f"\t\t/{command.name}")

            bot.guild_emoji[guild.id] = {}
            for emoji in guild.emojis:
                bot.guild_emoji[guild.id][emoji.name] = emoji.id
                print_log(f"Guild emoji: {emoji.name} -> {emoji.id}")

            channel_id = await data_access_get_guild_text_channel_id(guild.id)
            if channel_id is None:
                print_log(
                    f"\tThe administrator of the guild {guild.name} did not configure the channel to send the daily message."
                )
                continue

            channel: discord.TextChannel = await data_access_get_channel(channel_id)

            if channel:
                permissions = self.check_bot_permissions(channel)
                print_log(f"\tBot permissions in channel {channel.name}: {permissions}")
            else:
                print_warning_log(f"\tChannel ID {channel_id} not found in guild {guild.name}")
            tasks.append(send_daily_question_to_a_guild(bot, guild))

        # Running all tasks concurrently and waiting for them to finish
        await asyncio.gather(*tasks)

    def check_bot_permissions(self, channel: discord.TextChannel) -> dict:
        """Check the bot permissions in a specific channel"""
        bot_permissions = channel.permissions_for(channel.guild.me)

        permissions = {
            "read_messages": bot_permissions.read_messages,
            "send_messages": bot_permissions.send_messages,
            "manage_messages": bot_permissions.manage_messages,
            "add_reactions": bot_permissions.add_reactions,
            "read_message_history": bot_permissions.read_message_history,
        }

        return permissions

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, reaction: discord.RawReactionActionEvent):
        """User adds a reaction to a message"""
        await self.adjust_reaction(reaction, False)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, reaction: discord.RawReactionActionEvent):
        """User removes a reaction to a message"""
        await self.adjust_reaction(reaction, True)

    async def adjust_reaction(self, reaction: discord.RawReactionActionEvent, remove: bool):
        """Adjust the reaction with add or remove"""

        channel_id = reaction.channel_id
        guild_id = reaction.guild_id
        message_id = reaction.message_id
        user_id = reaction.user_id
        guild: discord.Guild = await data_access_get_guild(guild_id)
        channel: discord.TextChannel = await data_access_get_channel(channel_id)
        text_message_reaction: discord.Message = await data_access_get_message(guild_id, channel_id, message_id)
        user: discord.User = await data_access_get_user(guild_id, user_id)
        member: discord.Member = await data_access_get_member(guild_id, user_id)
        text_channel_configured_for_bot: discord.TextChannel = await data_access_get_guild_text_channel_id(guild_id)
        reaction_emoji = reaction.emoji

        if user is None:
            print_error_log(f"User not found for user {user_id}. Skipping.")
            return

        if member is None:
            print_error_log(f"Member not found for user {user_id}. Skipping.")
            return

        print_log(
            f"adjust_reaction: {'Add' if remove is False else 'Remove'} reaction for {user_id} ({member.display_name}) at time {reaction_emoji}"
        )
        # We do not act on message that are not in the Guild's text channel
        if text_channel_configured_for_bot is None or text_channel_configured_for_bot != channel_id:
            # The reaction was on another channel, we allow it
            return

        if not channel or not text_message_reaction or not user or not guild or not member:
            print_log("End-Before Adjusting reaction")
            return

        if user.bot:
            return  # Ignore reactions from bots

        # Check if the message is older than 24 hours
        if text_message_reaction.created_at < datetime.now(timezone.utc) - timedelta(days=1):
            await user.send("You can't vote on a message that is older than 24 hours.")
            return

        # Ensure no one is adding additional reactions
        emoji_from_list = EMOJI_TO_TIME.get(str(reaction_emoji))
        if emoji_from_list is None:
            await text_message_reaction.remove_reaction(reaction_emoji, member)
            await user.send("You cannot add reaction beside the one provided. Each reaction is a time slot.")
            return

        # Cache all users for this message's reactions to avoid redundant API calls
        channel_message_votes = await data_access_get_reaction_message(guild_id, channel_id, message_id)
        async with self.lock:
            # In the case there is no vote in the cache, we need to populate it with all the potential votes
            if not channel_message_votes:
                print_log(f"adjust_reaction: Add empty vote for message {message_id}")
                channel_message_votes = get_empty_votes()
                # Iterate over each reaction in the message only if it's not cached
                for react in text_message_reaction.reactions:
                    time_voted = EMOJI_TO_TIME.get(str(react.emoji))
                    if time_voted:
                        users = [u async for u in react.users() if not u.bot]
                        for user in users:
                            channel_message_votes[time_voted].append(
                                SimpleUser(
                                    user_id,
                                    member.display_name,
                                    get_user_rank_emoji(self.bot.guild_emoji.get(guild_id), member),
                                )
                            )
                # Always update the cache to avoid other event to save a new empty list of votes
                data_access_set_reaction_message(guild_id, channel_id, message_id, channel_message_votes)
                print_log(f"adjust_reaction: Setting reaction users for message {message_id} in cache")

            # Add or Remove Action
            print_log(f"adjust_reaction: Updating for the current reaction {message_id}")
            time_voted = EMOJI_TO_TIME.get(str(reaction_emoji))
            if remove:
                # Remove the user from the message votes
                for time_v, value in channel_message_votes.items():
                    if time_v == time_voted:
                        for single_vote in value:
                            if user.id == single_vote.user_id:
                                print_log(
                                    f"adjust_reaction: Found in {message_id} entry of the user for reaction {reaction_emoji}. Removing."
                                )
                                channel_message_votes[time_voted].remove(single_vote)
                                break
            else:
                # Add the user to the message votes
                time_voted = EMOJI_TO_TIME.get(str(reaction_emoji))
                if time_voted:
                    if any(user.id == u.user_id for u in channel_message_votes[time_voted]):
                        print_log(
                            f"adjust_reaction: User {user.id} ({member.display_name}) already voted for {time_voted} in message {message_id}"
                        )
                    else:
                        channel_message_votes[time_voted].append(
                            SimpleUser(
                                user.id,
                                member.display_name,
                                get_user_rank_emoji(self.bot.guild_emoji.get(guild_id), member),
                            )
                        )
                        print_log(f"adjust_reaction: Updating reaction users for message {message_id} in cache")
            # Always update the cache
            data_access_set_reaction_message(guild_id, channel_id, message_id, channel_message_votes)

            print_log("adjust_reaction: End Adjusting reaction")
            # await rate_limiter(update_vote_message, message, message_votes)
        # Lock is released here
        await update_vote_message(text_message_reaction, channel_message_votes)

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
            text_channel_id = await data_access_get_guild_text_channel_id(guild_id)
            if text_channel_id is None:
                print_warning_log(f"Text channel not set for guild {guild.name}. Skipping.")
                continue

            # Log user activity
            try:
                if before.channel is None and after.channel is not None:
                    # User joined a voice channel
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
                    await self.send_session_stats(member, guild_id)
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
            except Exception as e:
                print_error_log(f"on_voice_state_update: Error logging user activity: {e}")

            # Check if the user joined a voice channel to send a voice message
            if after.channel is not None and after.channel.id in voice_channel_ids:
                # Check if the user is the only one in the voice channel
                if len(after.channel.members) == 1:
                    await send_notification_voice_channel(self.bot, guild_id, member, after.channel, text_channel_id)

    async def send_session_stats(self, member: discord.Member, guild_id: int) -> None:
        """
        Get the statistic of a user and post it
        """
        last_hour = 12
        if member.bot:
            return  # Ignore bot

        # Only perform the action if it wasn't done in the last hour
        current_time = datetime.now(timezone.utc)
        last_activity = await data_access_get_gaming_session_last_activity(member.id, guild_id)
        # Only shows the stats once per hour per user maximum
        if last_activity is not None and last_activity > current_time - timedelta(hours=1):
            return None

        # Get the user ubisoft name
        user_info: UserInfo = await fetch_user_info_by_user_id(member.id)
        if user_info is None or user_info.ubisoft_username_active is None:
            return None

        try:
            matches = get_r6tracker_user_recent_matches(user_info.ubisoft_username_active)
            await data_access_set_gaming_session_last_activity(member.id, guild_id, current_time)
        except Exception as e:
            print_error_log(f"Error getting the user stats from R6 tracker: {e}")
            return None

        aggregation: Optional[UserMatchInfoSessionAggregate] = get_user_gaming_session_stats(
            user_info.ubisoft_username_active, current_time - timedelta(hours=last_hour), matches
        )
        if aggregation is None:
            return None

        channel_id: int = await data_access_get_gaming_session_text_channel_id(guild_id)
        channel: discord.TextChannel = await data_access_get_channel(channel_id)
        # We never sent the message, so we send it, add the reactions and save it in the cache
        embed_msg = self.get_gaming_session_user_embed_message(member, aggregation, last_hour)
        await channel.send(content="", embed=embed_msg)

    def get_gaming_session_user_embed_message(
        self, member: discord.Member, aggregation: UserMatchInfoSessionAggregate, last_hour: int
    ) -> discord.Embed:
        """Create the stats message"""
        title = f"{member.display_name} Stats"
        embed = discord.Embed(
            title=title,
            description=f"{member.mention} played {aggregation.match_count} matches: {aggregation.match_win_count} wins and {aggregation.match_loss_count} losses.",
            color=get_color_for_rank(member),
            timestamp=datetime.now(),
            url=f"https://r6.tracker.network/r6siege/profile/ubi/{aggregation.ubisoft_username_active}",
        )
        # Get the list of kill_death into a string with comma separated
        str_kd = "\n".join(
            f"Match #{i+1} ({map_name}): {kd}"
            for i, (kd, map_name) in enumerate(
                reversed(list(zip(aggregation.kill_death_assist, aggregation.maps_played)))
            )
        )
        embed.set_thumbnail(url=member.avatar.url)

        embed.add_field(name="Starting Pts", value=aggregation.started_rank_points, inline=True)
        diff = (
            "+" + str(aggregation.total_gained_points)
            if aggregation.total_gained_points > 0
            else str(aggregation.total_gained_points)
        )
        embed.add_field(name="Ending Pts", value=f"{aggregation.ended_rank_points}", inline=True)
        embed.add_field(name="Pts Variation", value=diff, inline=True)
        embed.add_field(name="Total Kills", value=aggregation.total_kill_count, inline=True)
        embed.add_field(name="Total Deaths", value=aggregation.total_death_count, inline=True)
        embed.add_field(name="Total Assists", value=aggregation.total_assist_count, inline=True)
        embed.add_field(name="Total TK", value=aggregation.total_tk_count, inline=True)
        embed.add_field(name="Total 3k round", value=aggregation.total_round_with_3k, inline=True)
        embed.add_field(name="Total 4k round", value=aggregation.total_round_with_3k, inline=True)
        embed.add_field(name="Total Ace round", value=aggregation.total_round_with_aces, inline=True)
        embed.add_field(name="Kill/Death/Asssist Per Match", value=str_kd, inline=False)
        embed.set_footer(text=f"Your stats for the last {last_hour} hours")
        return embed


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(MyEventsCog(bot))
