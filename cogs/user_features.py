from typing import Optional
import discord
from datetime import datetime
from discord.ext import commands
from discord import app_commands
from deps.bot_common_actions import adjust_role_from_ubisoft_max_account
from ui.confirmation_rank_view import ConfirmCancelView
from deps.data_access import (
    data_access_get_member,
)
from deps.analytic_data_access import (
    data_access_set_ubisoft_username_active,
    data_access_set_ubisoft_username_max,
    fetch_user_info_by_user_id_list,
)
from deps.data_access_data_class import UserInfo
from deps.values import (
    COMMAND_ACTIVE_RANK_USER_ACCOUNT,
    COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL,
    COMMAND_MAX_RANK_USER_ACCOUNT,
)
from deps.mybot import MyBot
from deps.log import print_error_log
from deps.siege import get_user_rank_emoji
from deps.functions import (
    most_common,
)


class UserFeatures(commands.Cog):
    """User Features commands"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_GET_USERS_TIME_ZONE_FROM_VOICE_CHANNEL)
    async def get_users_time_zone_from_voice_channel(
        self, interaction: discord.Interaction, voice_channel: discord.VoiceChannel
    ):
        """Get the timezone of all users in a voice channel"""
        await interaction.response.defer()
        users_id = [members.id for members in voice_channel.members]
        userid_member = {members.id: members for members in voice_channel.members}
        if len(users_id) == 0:
            await interaction.followup.send("No users in the voice channel.")
            return

        user_infos: Optional[UserInfo] = fetch_user_info_by_user_id_list(users_id)

        embed = discord.Embed(
            title=f"{voice_channel.name} Timezone",
            color=0x00FF00,
            timestamp=datetime.now(),
        )

        pacific = ""
        central = ""
        eastern = ""

        for user_info in user_infos:
            rank = get_user_rank_emoji(self.bot.guild_emoji.get(interaction.guild.id), userid_member.get(user_info.id))
            member = userid_member.get(user_info.id)

            user_name = member.display_name if member is not None else user_info.display_name
            if user_info is not None:
                if user_info.time_zone == "US/Eastern":
                    eastern += f"{rank} {user_name}\n"
                elif user_info.time_zone == "US/Central":
                    central += f"{rank} {user_name}\n"
                elif user_info.time_zone == "US/Pacific":
                    pacific += f"{rank} {user_name}\n"

        embed.add_field(name="Pacific", value="-" if pacific == "" else pacific, inline=True)
        embed.add_field(name="Central", value="-" if central == "" else central, inline=True)
        embed.add_field(name="Eastern", value="-" if eastern == "" else eastern, inline=True)

        if len(user_infos) == 0:
            await interaction.followup.send("Cannot find users timezone.")
            return
        most_common_tz = most_common([user_info.time_zone for user_info in user_infos])

        embed.set_footer(text=f"Most common timezone: {most_common_tz}")
        await interaction.followup.send(content="", embed=embed)

    @app_commands.command(name=COMMAND_MAX_RANK_USER_ACCOUNT)
    async def set_max_user_account(self, interaction: discord.Interaction, ubisoft_connect_name: str):
        """
        Your best (maximum MMR) Ubisoft Connect account
        """
        await interaction.response.defer(ephemeral=True)

        view = ConfirmCancelView()
        await interaction.followup.send(
            f"Are you sure you want to perform this action? If {ubisoft_connect_name} is not your real account you will face consequences.",
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
            member: discord.Member = await data_access_get_member(guild_id, interaction.user.id)
            # member: discord.Member = interaction.guild.get_member(interaction.user.id)
            if member is None:
                print_error_log(f"adjust_rank: Cannot find a member from user id {interaction.user.id}.")
                await interaction.followup.send("Cannot find the member", ephemeral=True)
                return
            data_access_set_ubisoft_username_max(interaction.user.id, ubisoft_connect_name)
            max_rank = adjust_role_from_ubisoft_max_account(interaction.guild, member, ubisoft_connect_name)
            if max_rank is None:
                await interaction.followup.send(
                    "Sorry, we cannot change your role for the moment. Please contact a moderator to manually change it.",
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
        Ubisoft Connect account that you are playing on
        """
        await interaction.response.defer(ephemeral=True)
        data_access_set_ubisoft_username_active(interaction.user.id, ubisoft_connect_name)
        await interaction.followup.send(f"You are playing on `{ubisoft_connect_name}`", ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserFeatures(bot))
