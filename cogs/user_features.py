"""
User command for anything related to the user like their max rank, active rank, timezone, etc.
"""

from typing import Optional
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
from ui.confirmation_rank_view import ConfirmCancelView
from deps.bot_common_actions import adjust_role_from_ubisoft_max_account
from deps.data_access import (
    data_access_get_member,
)
from deps.analytic_data_access import (
    data_access_set_ubisoft_username_active,
    data_access_set_ubisoft_username_max,
    fetch_user_info_by_user_id_list,
)
from deps.values import (
    COMMAND_ACTIVE_RANK_USER_ACCOUNT,
    COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL,
    COMMAND_LFG,
    COMMAND_MAX_RANK_USER_ACCOUNT,
)
from deps.mybot import MyBot
from deps.log import print_error_log
from deps.siege import get_list_users_with_rank, get_user_rank_emoji
from deps.functions import (
    most_common,
)


class UserFeatures(commands.Cog):
    """User Features commands"""

    def __init__(self, bot: MyBot):
        self.bot = bot

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

        embed.set_footer(text=f"Most common timezone: {most_common_tz}")
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
            # member: discord.Member = interaction.guild.get_member(interaction.user.id)
            if member is None:
                print_error_log(f"adjust_rank: Cannot find a member from user id {interaction.user.id}.")
                await interaction.followup.send("Cannot find the member", ephemeral=True)
                return
            data_access_set_ubisoft_username_max(interaction.user.id, ubisoft_connect_name)
            max_rank = await adjust_role_from_ubisoft_max_account(interaction.guild, member, ubisoft_connect_name)
            if max_rank is None:
                await interaction.followup.send(
                    """Sorry, we cannot change your role for the moment. Please contact a moderator to manually change it.""",
                    ephemeral=True,
                )
                return
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


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserFeatures(bot))
