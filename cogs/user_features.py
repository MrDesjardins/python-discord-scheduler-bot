"""
User command for anything related to the user like their max rank, active rank, timezone, etc.
"""

from typing import Optional
from datetime import datetime, timezone
import discord
from discord.ext import commands
from discord import app_commands
from deps.functions_date import convert_to_eastern_date_time
from ui.confirmation_rank_view import ConfirmCancelView
from deps.bot_common_actions import adjust_role_from_ubisoft_max_account
from deps.data_access import (
    data_access_get_member,
    data_access_get_guild_private_channel_category_id,
    data_access_get_guild_active_private_channels,
    data_access_set_guild_active_private_channel,
    data_access_remove_guild_active_private_channel,
)
from deps.follow_data_access import fetch_all_followed_users_by_user_id, remove_following_user, save_following_user
from deps.streak_data_access import compute_current_streak, fetch_distinct_play_dates
from deps.analytic_data_access import (
    data_access_fetch_first_activity,
    data_access_fetch_last_activity,
    data_access_fetch_top_game_played_for_user,
    data_access_fetch_top_winning_partners_for_user,
    data_access_fetch_user_full_user_info,
    data_access_set_max_mmr,
    data_access_set_ubisoft_username_active,
    data_access_set_ubisoft_username_max,
    fetch_user_info_by_user_id,
    fetch_user_info_by_user_id_list,
    data_access_fetch_total_hours,
)
from deps.values import (
    COMMAND_ACTIVE_RANK_USER_ACCOUNT,
    COMMAND_FOLLOW_USER,
    COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL,
    COMMAND_LFG,
    COMMAND_MAX_RANK_USER_ACCOUNT,
    COMMAND_MY_STREAK,
    COMMAND_PRIVATE_CHANNEL,
    COMMAND_PRIVATE_CHANNEL_INVITE,
    COMMAND_SEE_FOLLOWED_USERS,
    COMMAND_UNFOLLOW_USER,
    PRIVATE_CHANNEL_MIN_HOURS,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_log, print_warning_log
from deps.siege import get_color_for_rank, get_list_users_with_rank, get_user_rank_emoji
from deps.functions import (
    get_url_user_profile_main,
    most_common,
)


class UserFeatures(commands.Cog):
    """User Features commands"""

    def __init__(self, bot: MyBot):
        self.bot = bot
        self.user_info_menu = app_commands.ContextMenu(
            name="User Info",
            callback=self.get_user_info,
        )
        self.user_follow = app_commands.ContextMenu(
            name="Follow User",
            callback=self.set_user_follow,
        )
        self.user_unfollow = app_commands.ContextMenu(
            name="Unfollow User",
            callback=self.set_user_unfollow,
        )
        # Add the command to the bot's command tree
        self.bot.tree.add_command(self.user_info_menu)
        self.bot.tree.add_command(self.user_follow)
        self.bot.tree.add_command(self.user_unfollow)

    async def _grant_private_channel_connect(
        self, channel: discord.VoiceChannel, guild: discord.Guild, member: discord.Member
    ) -> bool:
        """Grant a member view/connect permission, with role-overwrite fallback when member overwrite is blocked."""
        # If the user already has effective access (e.g., Administrator), no overwrite is needed.
        current_perms = channel.permissions_for(member)
        if current_perms.view_channel is True and current_perms.connect is True:
            return True

        try:
            await channel.set_permissions(member, view_channel=True, connect=True, move_members=False)
            # Discord may take a short moment to reflect updated effective permissions in cache.
            # If the API accepted the overwrite, treat it as success.
            return True
        except discord.Forbidden:
            pass

        if guild.me is None:
            return False

        # Fallback: grant connect to the highest role the member has that the bot can manage.
        manageable_roles = sorted(
            [
                role
                for role in member.roles
                if role != guild.default_role and role.position < guild.me.top_role.position
            ],
            key=lambda role: role.position,
            reverse=True,
        )
        for role in manageable_roles:
            try:
                await channel.set_permissions(role, view_channel=True, connect=True)
                print_warning_log(
                    f"_grant_private_channel_connect: Used role fallback {role.id} for member {member.id} in channel {channel.id}."
                )
                return True
            except discord.Forbidden:
                continue

        return False

    async def _cleanup_stale_private_channel_entries(self, guild: discord.Guild) -> dict[int, tuple[int, bool]]:
        """Remove stale/non-voice private-channel cache entries for a guild and return cleaned mapping."""
        guild_id = guild.id
        active_private_channels = await data_access_get_guild_active_private_channels(guild_id)
        if len(active_private_channels) == 0:
            return active_private_channels

        cleaned = dict(active_private_channels)
        stale_ids: list[int] = []

        for channel_id in list(cleaned.keys()):
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.VoiceChannel):
                continue
            try:
                fetched_channel = await guild.fetch_channel(channel_id)
                if isinstance(fetched_channel, discord.VoiceChannel):
                    continue
            except discord.NotFound:
                pass
            except discord.Forbidden:
                # Don't remove on permission errors; avoid destructive cleanup on transient permission config issues.
                continue
            except discord.HTTPException as e:
                print_error_log(
                    f"_cleanup_stale_private_channel_entries: Failed to fetch channel {channel_id} in guild {guild_id}: {e}"
                )
                continue

            stale_ids.append(channel_id)

        for channel_id in stale_ids:
            await data_access_remove_guild_active_private_channel(guild_id, channel_id)
            cleaned.pop(channel_id, None)

        if stale_ids:
            print_log(
                f"_cleanup_stale_private_channel_entries: Removed {len(stale_ids)} stale private-channel entries in guild {guild_id}."
            )

        return cleaned

    @app_commands.command(name=COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL)
    async def get_users_time_zone_from_voice_channel(
        self, interaction: discord.Interaction, voice_channel: Optional[discord.VoiceChannel] = None
    ):
        """Get the timezone of all users in a voice channel"""
        await interaction.response.defer()
        guild = interaction.guild
        if guild is None:
            print_error_log(
                f"""get_users_time_zone_from_voice_channel: No guild_id available for user {interaction.user.display_name}({interaction.user.id})."""
            )
            await interaction.followup.send("Guild not found for this user.", ephemeral=True)
            return
        user = interaction.user
        all_members_voice_channel = []
        voice_channel_name = ""

        if voice_channel is None:  # It wasn't explicitly provided
            if isinstance(user, discord.Member) and user.voice is not None and user.voice.channel is not None:
                all_members_voice_channel = user.voice.channel.members
                voice_channel_name = user.voice.channel.name
        else:
            all_members_voice_channel = voice_channel.members
            voice_channel_name = voice_channel.name

        users_id = [members.id for members in all_members_voice_channel]
        userid_member = {members.id: members for members in all_members_voice_channel}
        if len(users_id) == 0:
            await interaction.followup.send("No users in the voice channel.")
            return

        user_infos = fetch_user_info_by_user_id_list(users_id)

        embed = discord.Embed(
            title=f"{voice_channel_name} Channel Timezone",
            color=0x00FF00,
            timestamp=datetime.now(),
        )

        pacific = ""
        central = ""
        eastern = ""

        for user_info in user_infos:
            if user_info is None:
                continue
            member = userid_member.get(user_info.id)
            if member is None:
                print_error_log(
                    f"get_users_time_zone_from_voice_channel: Cannot find a member from user id {user_info.id}."
                )
                continue
            rank = get_user_rank_emoji(self.bot.guild_emoji.get(guild.id, {}), member)

            user_name = member.mention if member is not None else user_info.display_name
            if user_info is not None:
                entry = f"""{rank} {user_name} ({user_info.ubisoft_username_active if user_info.ubisoft_username_active is not None else user_info.ubisoft_username_max  if user_info.ubisoft_username_max is not None else '?'})"""
                if user_info.time_zone == "US/Eastern":
                    eastern += f"{entry}\n"
                elif user_info.time_zone == "US/Central":
                    central += f"{entry}\n"
                elif user_info.time_zone == "US/Pacific":
                    pacific += f"{entry}\n"

        embed.add_field(name="Pacific", value="-" if pacific == "" else pacific, inline=True)
        embed.add_field(name="Central", value="-" if central == "" else central, inline=True)
        embed.add_field(name="Eastern", value="-" if eastern == "" else eastern, inline=True)

        if len(user_infos) == 0:
            await interaction.followup.send("Cannot find users timezone.")
            return
        most_common_tz = most_common([user_info.time_zone for user_info in user_infos if user_info is not None])

        footer_text = f"Most common timezone: {most_common_tz if most_common_tz else 'Unknown'}"
        embed.set_footer(text=footer_text)
        await interaction.followup.send(content="", embed=embed)

    @app_commands.command(name=COMMAND_MAX_RANK_USER_ACCOUNT)
    async def set_max_user_account(self, interaction: discord.Interaction, ubisoft_connect_name: str):
        """
        Set your best (maximum MMR) Ubisoft Connect account user name
        """
        await interaction.response.defer(ephemeral=True)

        if interaction.guild is None:
            print_error_log(
                f"""set_max_user_account: No guild_id available for user {interaction.user.display_name}({interaction.user.id})."""
            )
            await interaction.followup.send("Guild not found for this command.", ephemeral=True)
            return
        view = ConfirmCancelView()
        await interaction.followup.send(
            f"""Are you sure you want to perform this action? If {ubisoft_connect_name} is not your real account you will face consequences.""",
            view=view,
            ephemeral=True,
        )

        # Wait for the user to interact with the view
        await view.wait()

        # Check the result after user clicks a button
        if view.result is None:
            await interaction.followup.send("No response, action timed out.")
        elif view.result:

            guild_id = interaction.guild.id
            member = await data_access_get_member(guild_id, interaction.user.id)
            if member is None:
                print_error_log(f"adjust_rank: Cannot find a member from user id {interaction.user.id}.")
                await interaction.followup.send("Cannot find the member", ephemeral=True)
                return
            data_access_set_ubisoft_username_max(interaction.user.id, ubisoft_connect_name)

            max_rank, max_mmr = await adjust_role_from_ubisoft_max_account(
                interaction.guild, member, ubisoft_connect_name
            )
            if max_rank is None:
                await interaction.followup.send(
                    """Sorry, we cannot change your role for the moment. Please contact a moderator to manually change it.""",
                    ephemeral=True,
                )
                return
            try:
                data_access_set_max_mmr(member.id, max_mmr)
            except Exception as e:
                print_error_log(f"set_max_user_account: Error setting max mmr: {e}")

            await interaction.followup.send(f"Found max rank {max_rank}, role adjusted", ephemeral=True)
        # Add code to perform the actual action here
        else:
            await interaction.followup.send("Action was canceled.", ephemeral=True)

    @app_commands.command(name=COMMAND_ACTIVE_RANK_USER_ACCOUNT)
    async def set_active_user_account(self, interaction: discord.Interaction, ubisoft_connect_name: str):
        """
        Set the Ubisoft Connect account user name that you are playing on
        """
        await interaction.response.defer(ephemeral=True)
        data_access_set_ubisoft_username_active(interaction.user.id, ubisoft_connect_name)
        await interaction.followup.send(f"You are playing on `{ubisoft_connect_name}`", ephemeral=True)

    @app_commands.command(name=COMMAND_LFG)
    async def looking_for_group(self, interaction: discord.Interaction, number_of_users_needed: Optional[int] = None):
        """Looking for group command"""
        await interaction.response.defer(ephemeral=False)
        user = interaction.user
        if interaction.guild_id is None:
            print_error_log(f"looking_for_group: No guild_id available for user {user.display_name}({user.id}).")
            await interaction.followup.send("Guild not found for this user.", ephemeral=True)
            return
        if isinstance(user, discord.Member) and user.voice is not None and user.voice.channel is not None:
            voice_channel = user.voice.channel
            # Get everyone in the voice channel
            members = voice_channel.members
            if isinstance(members, list):
                list_members_in_voice_channel = get_list_users_with_rank(self.bot, members, interaction.guild_id)
                current_count = len(members)
                missing_count = 5 - current_count if number_of_users_needed is None else number_of_users_needed
                if missing_count > 0:
                    if missing_count > 10:
                        await interaction.followup.send(
                            f"""The command is not sent to the channel. The {COMMAND_LFG} allows a maximum of 10 people.""",
                            ephemeral=True,
                        )
                    else:
                        await interaction.followup.send(
                            f"""@here {list_members_in_voice_channel} {'are' if current_count > 1 else 'is'} in the voice channel: <#{voice_channel.id}> and need {missing_count} more people."""
                        )
                else:
                    await interaction.followup.send(
                        f"""There are already five people in the voice channel: <#{voice_channel.id}>. The {COMMAND_LFG} will not 'at mention' the channel.""",
                        ephemeral=True,
                    )
            else:
                print_error_log(f"looking_for_group: Cannot find members in the voice channel {voice_channel.id}.")
                await interaction.followup.send(
                    "Something went wrong, please contact the moderator to check the issue.",
                    ephemeral=True,
                )
        else:
            await interaction.followup.send(f"To use the /{COMMAND_LFG} command you must be in a voice channel.")

    @app_commands.command(name=COMMAND_FOLLOW_USER)
    async def follow_user(self, interaction: discord.Interaction, user_to_follow: discord.User):
        """Follow a user command"""
        try:
            await interaction.response.defer(ephemeral=True)
        except discord.errors.NotFound:
            print_error_log(f"follow_user: Interaction expired for user {interaction.user.id}.")
            return

        user = interaction.user
        if interaction.guild_id is None:
            print_error_log(f"follow_user: No guild_id available for user {user.display_name}({user.id}).")
            await interaction.followup.send("Guild not found for this user.", ephemeral=True)
            return

        user_to_follow_info = await fetch_user_info_by_user_id(user_to_follow.id)
        if user_to_follow_info is None:
            print_error_log(f"follow_user: Cannot find user info for user id {user_to_follow.id}.")
            await interaction.followup.send(
                "The user you are trying to follow has not set up their profile yet.",
                ephemeral=True,
            )
            return
        now_utc = datetime.now(timezone.utc)
        try:
            save_following_user(user.id, user_to_follow.id, now_utc)
            await interaction.followup.send(
                f"You are now following {user_to_follow.mention}. You will be notified when they join a voice channel.",
                ephemeral=True,
            )
        except Exception as e:
            print_error_log(f"follow_user: Exception occurred while saving following user: {e}.")

            await interaction.followup.send(
                "Something went wrong, please contact the moderator to check the issue.",
                ephemeral=True,
            )

    @app_commands.command(name=COMMAND_UNFOLLOW_USER)
    async def unfollow_user(self, interaction: discord.Interaction, user_to_unfollow: discord.User):
        """Unfollow a user command"""
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        if interaction.guild_id is None:
            print_error_log(f"unfollow_user: No guild_id available for user {user.display_name}({user.id}).")
            await interaction.followup.send("Guild not found for this user.", ephemeral=True)
            return

        try:
            remove_following_user(user.id, user_to_unfollow.id)
            await interaction.followup.send(
                f"You have unfollowed {user_to_unfollow.mention}. You will no longer receive notifications when they join a voice channel.",
                ephemeral=True,
            )
        except Exception as e:
            print_error_log(f"unfollow_user: Exception occurred while removing following user: {e}.")
            await interaction.followup.send(
                "Something went wrong, please contact the moderator to check the issue.",
                ephemeral=True,
            )

    @app_commands.command(name=COMMAND_SEE_FOLLOWED_USERS)
    async def see_followed_users(self, interaction: discord.Interaction):
        """See all followed users command"""
        await interaction.response.defer(ephemeral=True)
        user = interaction.user
        if interaction.guild_id is None:
            print_error_log(f"see_followed_users: No guild_id available for user {user.display_name}({user.id}).")
            await interaction.followup.send("Guild not found for this user.", ephemeral=True)
            return

        try:
            guild = interaction.guild
            if guild is None:
                await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
                return

            followed_user_ids = fetch_all_followed_users_by_user_id(user.id)
            if not followed_user_ids:
                await interaction.followup.send(
                    "You are not following any users.",
                    ephemeral=True,
                )
                return

            followed_user_infos = fetch_user_info_by_user_id_list(followed_user_ids)
            followed_user_mentions = []
            for user_info in followed_user_infos:
                if user_info is not None:
                    member = guild.get_member(user_info.id)
                    if member is not None:
                        followed_user_mentions.append(member.mention)

            if followed_user_mentions:
                followed_users_str = "\n".join(followed_user_mentions)
                await interaction.followup.send(
                    f"You are following these users:\n{followed_users_str}",
                    ephemeral=True,
                )
            else:
                await interaction.followup.send(
                    "You are not following any users.",
                    ephemeral=True,
                )
        except Exception as e:
            print_error_log(f"see_followed_users: Exception occurred while fetching followed users: {e}.")
            await interaction.followup.send(
                "Something went wrong, please contact the moderator to check the issue.",
                ephemeral=True,
            )

    @app_commands.command(name=COMMAND_PRIVATE_CHANNEL)
    async def create_private_channel(self, interaction: discord.Interaction, track: bool = True):
        """Create a private voice channel. Only you can join and drag others in. Deleted when empty. Requires 350h of activity."""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            print_error_log(f"create_private_channel: Guild is None for user {interaction.user.id}.")
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = guild.id
        user = interaction.user
        await self._cleanup_stale_private_channel_entries(guild)

        hours = data_access_fetch_total_hours(user.id)
        if hours is None or hours < PRIVATE_CHANNEL_MIN_HOURS:
            await interaction.followup.send(
                f"You need at least {PRIVATE_CHANNEL_MIN_HOURS} hours of activity on this server to use this command. You currently have {hours or 0} hours.",
                ephemeral=True,
            )
            return

        category_id = await data_access_get_guild_private_channel_category_id(guild_id)
        if category_id is None:
            await interaction.followup.send(
                "The private channel category has not been configured. Please ask an administrator to set it up.",
                ephemeral=True,
            )
            return

        category = guild.get_channel(category_id)
        if not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "The configured category no longer exists. Please ask an administrator to reconfigure it.",
                ephemeral=True,
            )
            return

        creator = guild.get_member(user.id)
        if creator is None:
            await interaction.followup.send("Could not resolve your membership in this server.", ephemeral=True)
            return

        # Pre-check bot permissions in the category before touching the Discord API.
        # create_voice_channel needs MANAGE_CHANNELS + VIEW_CHANNEL.
        if guild.me is not None:
            bot_perms = category.permissions_for(guild.me)
            missing: list[str] = []
            if not bot_perms.manage_channels:
                missing.append("Manage Channels")
            if not bot_perms.view_channel:
                missing.append("View Channel")
            if missing:
                print_error_log(
                    f"create_private_channel: Bot missing {missing} in guild {guild_id} category {category_id}."
                )
                await interaction.followup.send(
                    f"This feature is not available yet. An administrator must grant the bot the following permissions inside the **{category.name}** category: **{', '.join(missing)}**.",
                    ephemeral=True,
                )
                return

        # Create the channel without any permission overwrites so that the creation API call
        # requires only MANAGE_CHANNELS (no role-overwrite permission checks). After the channel
        # exists we lock it via channel.set_permissions(), which is a separate API call that
        # only touches role overwrites and avoids Discord's member-overwrite hierarchy check.
        channel = None
        try:
            channel = await guild.create_voice_channel(
                name=f"{creator.display_name}'s private vc",
                category=category,
            )
            print_log(f"create_private_channel: Channel {channel.id} created in guild {guild_id}.")
        except discord.Forbidden:
            print_error_log(
                f"create_private_channel: Forbidden when creating channel in guild {guild_id} category {category_id}."
            )
            await interaction.followup.send(
                "The bot does not have the required permissions to create a channel in that category. Please ask an administrator to check the bot's permissions.",
                ephemeral=True,
            )
            return

        # Move creator in while the channel is still open (before locking connect).
        if creator.voice is not None:
            try:
                await creator.move_to(channel)
            except discord.Forbidden:
                print_warning_log(
                    f"create_private_channel: Forbidden when moving creator {user.id} to channel {channel.id}."
                )

        # Lock channel by default first, then explicitly allow creator as the final overwrite.
        try:
            await channel.set_permissions(guild.default_role, connect=False, move_members=False)
        except discord.Forbidden:
            print_warning_log(
                f"create_private_channel: Forbidden when setting default-role lock on channel {channel.id}. Channel left open."
            )

        creator_can_rejoin = await self._grant_private_channel_connect(channel, guild, creator)
        if not creator_can_rejoin:
            print_warning_log(
                f"create_private_channel: Could not grant creator rejoin permission for {user.id} on channel {channel.id}."
            )
            try:
                await channel.delete(reason="Could not grant creator access to private channel")
            except Exception as e:
                print_warning_log(
                    f"create_private_channel: Failed to delete unusable channel {channel.id} after permission failure: {e}"
                )
            await interaction.followup.send(
                "I couldn't grant you join access to your private channel (likely role hierarchy/category permission conflict), so I canceled creation. "
                "Please ask an admin to move the bot role higher and verify category voice permissions.",
                ephemeral=True,
            )
            return

        try:
            other_positions = [ch.position for ch in category.channels if ch.id != channel.id]
            bottom_position = max(other_positions) + 1 if other_positions else channel.position
            await channel.edit(position=bottom_position)
        except Exception as e:
            print_warning_log(f"create_private_channel: Could not set channel position: {e}")

        await data_access_set_guild_active_private_channel(guild_id, channel.id, user.id, track)

        success_message = (
            f"Your private channel <#{channel.id}> has been created. "
            f"Use `/privatechannelinvite` to grant others access. "
            f"You can leave and click the channel to rejoin. "
            f"The channel is deleted when empty."
        )
        await interaction.followup.send(success_message, ephemeral=True)

    @app_commands.command(name=COMMAND_PRIVATE_CHANNEL_INVITE)
    async def invite_to_private_channel(self, interaction: discord.Interaction, user: discord.Member):
        """Invite a member into your private voice channel by granting join access and sending them a DM."""
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        if guild is None:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        guild_id = guild.id
        invoker_id = interaction.user.id

        active_private_channels = await self._cleanup_stale_private_channel_entries(guild)
        creator_channel_ids = [
            ch_id for ch_id, (creator_id, _) in active_private_channels.items() if creator_id == invoker_id
        ]
        if len(creator_channel_ids) == 0:
            await interaction.followup.send("You do not have an active private channel.", ephemeral=True)
            return

        private_channel: Optional[discord.VoiceChannel] = None
        for creator_channel_id in creator_channel_ids:
            channel = guild.get_channel(creator_channel_id)
            if isinstance(channel, discord.VoiceChannel):
                private_channel = channel
                break

            try:
                fetched_channel = await guild.fetch_channel(creator_channel_id)
            except discord.NotFound:
                await data_access_remove_guild_active_private_channel(guild_id, creator_channel_id)
                continue
            except discord.Forbidden:
                await interaction.followup.send(
                    "I can't access your private channel right now. Please ask an admin to check channel permissions.",
                    ephemeral=True,
                )
                return
            except discord.HTTPException as e:
                print_error_log(
                    f"invite_to_private_channel: Failed to fetch channel {creator_channel_id} in guild {guild_id}: {e}"
                )
                await interaction.followup.send(
                    "I couldn't verify your private channel right now. Please try again in a moment.",
                    ephemeral=True,
                )
                return

            if isinstance(fetched_channel, discord.VoiceChannel):
                private_channel = fetched_channel
                break

            await data_access_remove_guild_active_private_channel(guild_id, creator_channel_id)

        if private_channel is None:
            await interaction.followup.send("Your private channel no longer exists.", ephemeral=True)
            return

        granted = await self._grant_private_channel_connect(private_channel, guild, user)
        if not granted:
            await interaction.followup.send(
                "I couldn't grant that member access. The bot role is likely too low in the role hierarchy.",
                ephemeral=True,
            )
            return

        jump_url = f"https://discord.com/channels/{guild_id}/{private_channel.id}"
        dm_sent = True
        try:
            await user.send(
                f"You were invited by **{interaction.user.display_name}** to join **{private_channel.name}** in **{guild.name}**.\n"
                f"Join here: {jump_url}"
            )
        except discord.Forbidden:
            dm_sent = False
        except discord.HTTPException as e:
            print_error_log(f"invite_to_private_channel: Failed to DM {user.id} in guild {guild_id}: {e}")
            dm_sent = False

        if dm_sent:
            await interaction.followup.send(
                f"{user.display_name} has been invited and can now click to join your private channel.",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(
                f"{user.display_name} has been granted access, but I couldn't DM them (their DMs may be closed).",
                ephemeral=True,
            )

    @app_commands.command(name=COMMAND_MY_STREAK)
    async def my_streak(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """Check how many consecutive days you (or another user) have played on this server."""
        await interaction.response.defer(ephemeral=True)

        if interaction.guild_id is None:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        target_user = user if user is not None else interaction.user
        play_dates = fetch_distinct_play_dates(target_user.id, interaction.guild_id)
        streak = compute_current_streak(play_dates)

        if streak == 0:
            msg = f"**{target_user.display_name}** has no active streak right now."
        else:
            msg = f"**{target_user.display_name}** is on a **{streak}-day streak**!"

        await interaction.followup.send(msg, ephemeral=True)

    async def get_user_info(self, interaction: discord.Interaction, user: discord.User) -> None:
        """Callback for the 'User Info' context menu."""
        print_log(
            f"get_user_info: Fetching user info for user {user.display_name}({user.id}) by {interaction.user.display_name}({interaction.user.id})."
        )
        # Acknowledge the interaction immediately
        await interaction.response.defer(ephemeral=True)

        user_info = await fetch_user_info_by_user_id(user.id)

        if user_info is None:
            print_error_log(f"get_user_info: Cannot find user info for user id {user.id}.")
            try:
                await interaction.user.send("The user has not set up their profile yet.")
                await interaction.followup.send("User info sent to your DMs!", ephemeral=True)
            except discord.Forbidden:
                print_error_log(
                    f"get_user_info: Cannot send DM to user {interaction.user.display_name}({interaction.user.id})."
                )
                await interaction.followup.send(
                    "The user has not set up their profile yet. (Could not send DM - please enable DMs from server members)",
                    ephemeral=True,
                )
            return
        print_log(
            f"get_user_info: Found user info for user {user.display_name}({user.id}). Now data_access_fetch_first_activity and data_access_fetch_last_activity."
        )
        first_activity = data_access_fetch_first_activity(user.id)
        last_activity = data_access_fetch_last_activity(user.id)
        display_name = user_info.ubisoft_username_max if user_info.ubisoft_username_max is not None else "Not set"
        guild_ctx = interaction.guild
        member_ctx = guild_ctx.get_member(user.id) if guild_ctx is not None else None
        embed_color = (
            get_color_for_rank(member_ctx) if member_ctx is not None else int(discord.Color.from_rgb(114, 137, 218))
        )
        active_ubi = user_info.ubisoft_username_active or ""
        embed = discord.Embed(
            title=f"{user.display_name} Info",
            description="""Top User Information""",
            color=embed_color,
            timestamp=datetime.now(),
            url=get_url_user_profile_main(active_ubi) if active_ubi else None,
        )
        if user.avatar is not None:
            embed.set_thumbnail(url=user.avatar.url)
        embed.add_field(name="User display name", value=f"{user_info.display_name}", inline=True)
        embed.add_field(
            name="Ubisoft Connect Max Account",
            value=f"{user_info.ubisoft_username_max if user_info.ubisoft_username_max is not None else 'Not set'}",
            inline=True,
        )
        embed.add_field(
            name="Ubisoft Connect Active Account",
            value=f"{user_info.ubisoft_username_active if user_info.ubisoft_username_active is not None else display_name}",
            inline=True,
        )
        embed.add_field(name="Max MMR Recorded", value=f"{user_info.max_mmr}", inline=True)
        embed.add_field(
            name="Time Zone",
            value=f"{user_info.time_zone if user_info.time_zone is not None else 'Not set'}",
            inline=True,
        )
        joined_display = "Unknown"
        if member_ctx is not None and member_ctx.joined_at is not None:
            joined_display = convert_to_eastern_date_time(member_ctx.joined_at)
        embed.add_field(
            name="Joined the server on",
            value=joined_display,
            inline=True,
        )
        embed.add_field(
            name="First Activity Recorded",
            value=f"{convert_to_eastern_date_time(first_activity) if first_activity is not None else 'No activity recorded'}",
            inline=True,
        )
        embed.add_field(
            name="Last Activity Recorded",
            value=f"{convert_to_eastern_date_time(last_activity) if last_activity is not None else 'No activity recorded'}",
            inline=True,
        )

        print_log(f"get_user_info: Now fetching user full info for user {user.display_name}({user.id}).")
        user_full_info = data_access_fetch_user_full_user_info(user.id)
        if user_full_info is not None:
            embed.add_field(
                name="Total Ranked Matches Played",
                value=f"{user_full_info.rank_match_played if user_full_info.rank_match_played is not None else 0}",
                inline=True,
            )
            embed.add_field(
                name="Rank K/D",
                value=f"{user_full_info.rank_kd_ratio if user_full_info.rank_kd_ratio is not None else 0:.2f}",
                inline=True,
            )
            embed.add_field(
                name="Win Rate",
                value=f"{user_full_info.rank_win_percentage if user_full_info.rank_win_percentage is not None else 0:.2f}%",
                inline=True,
            )

        print_log(f"get_user_info: Now fetching total hours for user {user.display_name}({user.id}).")
        hours = data_access_fetch_total_hours(user.id)
        if hours is not None:
            embed.add_field(name="Hours played on this server", value=f"{hours} hours", inline=True)

        print_log(f"get_user_info: Now fetching top game partners for user {user.display_name}({user.id}).")
        top_game_partners = data_access_fetch_top_game_played_for_user(user.id)
        if top_game_partners is not None and len(top_game_partners) > 0:
            partners_str = "\n".join(
                [f"{idx + 1}. {partner[0]} - {partner[1]} matches" for idx, partner in enumerate(top_game_partners)]
            )
            embed.add_field(name="Top Rank Partners", value=partners_str, inline=False)

        print_log(f"get_user_info: Now fetching top winning partners for user {user.display_name}({user.id}).")
        top_winning_partners = data_access_fetch_top_winning_partners_for_user(user.id)
        if top_winning_partners is not None and len(top_winning_partners) > 0:
            winning_partners_str = "\n".join(
                [
                    f"{idx + 1}. {partner[0]} - {partner[1]} match with {partner[2]*100:.1f}% win"
                    for idx, partner in enumerate(top_winning_partners)
                ]
            )
            embed.add_field(name="Top Winning Partners", value=winning_partners_str, inline=False)

        print_log(
            f"get_user_info: Sending user info embed to DM for user {interaction.user.display_name}({interaction.user.id})."
        )
        try:
            await interaction.user.send(embed=embed)
            await interaction.followup.send("User info sent to your DMs!", ephemeral=True)
        except discord.Forbidden:
            print_error_log(
                f"get_user_info: Cannot send DM to user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.followup.send(
                "Could not send DM. Please enable DMs from server members in your privacy settings. Here's the info:",
                embed=embed,
                ephemeral=True,
            )

    async def set_user_follow(self, interaction: discord.Interaction, user_to_follow: discord.User) -> None:
        """Callback for the 'Follow User' context menu."""
        user = interaction.user
        now_utc = datetime.now(timezone.utc)
        try:
            save_following_user(user.id, user_to_follow.id, now_utc)
            await interaction.response.send_message(
                f"You are now following {user_to_follow.mention}. You will be notified when they join a voice channel.",
                ephemeral=True,
            )
        except Exception as e:
            print_error_log(f"follow_user: Exception occurred while saving following user: {e}.")

            await interaction.response.send_message(
                "Something went wrong, please contact the moderator to check the issue.",
                ephemeral=True,
            )

    async def set_user_unfollow(self, interaction: discord.Interaction, user_to_unfollow: discord.User) -> None:
        """Callback for the 'Unfollow User' context menu."""
        user = interaction.user
        try:
            remove_following_user(user.id, user_to_unfollow.id)
            await interaction.response.send_message(
                f"You have unfollowed {user_to_unfollow.mention}. You will no longer receive notifications when they join a voice channel.",
                ephemeral=True,
            )
        except Exception as e:
            print_error_log(f"unfollow_user: Exception occurred while removing following user: {e}.")
            await interaction.response.send_message(
                "Something went wrong, please contact the moderator to check the issue.",
                ephemeral=True,
            )

    async def cog_unload(self) -> None:
        self.bot.tree.remove_command(self.user_info_menu.name, type=self.user_info_menu.type)
        self.bot.tree.remove_command(self.user_follow.name, type=self.user_follow.type)
        self.bot.tree.remove_command(self.user_unfollow.name, type=self.user_unfollow.type)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserFeatures(bot))
