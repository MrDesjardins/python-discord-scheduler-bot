"""View for the user to configure their profile"""

import asyncio
from typing import Union
import discord
from deps.data_access import data_access_get_gaming_session_text_channel_id
from deps.bot_common_actions import set_member_role_from_current_rank
from deps.analytic_data_access import upsert_user_info
from deps.values import valid_time_zone_options
from deps.mybot import MyBot
from deps.siege import get_guild_rank_emoji
from deps.log import print_error_log
from deps.stats_cc import StatsCCClient

timezones_options = [discord.SelectOption(label=timezone, value=timezone) for timezone in valid_time_zone_options]


class SetupUserProfileView(discord.ui.View):
    """View for the user to configure their profile"""

    def __init__(self, bot: MyBot, guild: discord.Guild, member: discord.Member):
        super().__init__(timeout=60)
        self.bot = bot
        self.guild = guild
        self.member = member
        self.max_rank_account: Union[str, None] = None
        self.active_account: Union[str, None] = None
        self.user_timezone: Union[str, None] = None

        # Add timezone select
        self.timezone_select: discord.ui.Select = discord.ui.Select(
            placeholder="Select your timezone", options=timezones_options, custom_id="timezone_select"
        )
        self.add_item(self.timezone_select)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """OnChange of the timezone, we start the modal if value sets"""
        self.user_timezone = self.timezone_select.values[0] if self.timezone_select.values else None
        if self.user_timezone:
            self.timezone_select.disabled = True
            modal = SetupUserProfileModal(self)
            await interaction.response.send_modal(modal)
            return True
        await interaction.response.send_message("Please select a timezone.", ephemeral=True)
        return False


class SetupUserProfileModal(discord.ui.Modal, title="User Profile Setup"):
    """Modal that allows text box for the user name"""

    def __init__(self, view: SetupUserProfileView) -> None:
        super().__init__()
        self.view = view  # Pass view to access the view's variables

        self.max_rank_account_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Highest Ubisoft account name",
            placeholder="Name here",
            custom_id="max_name",
            required=True,
            style=discord.TextStyle.short,
        )
        self.add_item(self.max_rank_account_input)

        self.active_account_input: discord.ui.TextInput = discord.ui.TextInput(
            label="Active Ubisoft account name (empty if same)",
            placeholder="",
            custom_id="active_name",
            required=False,
            style=discord.TextStyle.short,
        )
        self.add_item(self.active_account_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Save the modal input values back to the view"""

        self.view.max_rank_account = self.max_rank_account_input.value.strip()
        self.view.active_account = self.active_account_input.value.strip() or self.view.max_rank_account

        # Ensure all required fields are filled out
        if not self.view.max_rank_account or not self.view.active_account or not self.view.user_timezone:
            await interaction.response.send_message("Please complete all fields.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # Unlike the unguarded tracker lookup introduced in d68bded, a provider
        # failure must produce a reply, and blocking HTTP must not stall Discord.
        try:
            profile_id, current_rank, max_mmr = await asyncio.to_thread(self.fetch_profile)
        except Exception as exc:
            print_error_log(f"Profile lookup failed for {self.view.member.id}: {exc}")
            await interaction.followup.send(
                "Could not look up your Ubisoft account on stats.cc. Check the account names and try again shortly. "
                "If this continues, ask a moderator to check the stats.cc API key and service.",
                ephemeral=True,
            )
            return

        # Perform the profile save actions
        try:
            upsert_user_info(
                self.view.member.id,
                self.view.member.display_name,
                self.view.max_rank_account,
                self.view.active_account,
                profile_id,
                self.view.user_timezone,
                max_mmr,
            )
        except Exception as e:
            print_error_log(f"Failed to save user profile for {self.view.member.id}: {str(e)}")
            await interaction.followup.send(
                f"❌ Failed to save profile",
                ephemeral=True,
            )
            return
        if not await set_member_role_from_current_rank(self.view.guild, self.view.member, current_rank):
            await interaction.followup.send(
                "❌ Profile saved, but I could not adjust your rank role. Please contact a moderator.",
                ephemeral=True,
            )
            return
        # Get stats channel
        channel_id = await data_access_get_gaming_session_text_channel_id(self.view.guild.id)

        # Send the follow-up message
        await interaction.followup.send(
            f"✅ Profile saved, role adjusted to {get_guild_rank_emoji(self.view.bot.guild_emoji.get(self.view.guild.id, {}), current_rank)} {current_rank} and after completing a voice session you will get your stats for `{self.view.active_account}` in <#{channel_id}>.",
            ephemeral=True,
        )

    def fetch_profile(self) -> tuple[str, str, int]:
        """Keep the HTTP session and all its requests on the worker thread."""
        with StatsCCClient() as client:
            return client.setup_profile(self.view.max_rank_account, self.view.active_account)
