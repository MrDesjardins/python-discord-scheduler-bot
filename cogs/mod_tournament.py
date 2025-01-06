from datetime import date, datetime, timezone
from typing import List
import discord
from discord.ext import commands
from discord import app_commands
from deps.tournament_data_access import (
    data_access_insert_tournament,
    fetch_tournament_active_to_interact_for_user,
    fetch_tournament_by_id,
)
from deps.data_access import (
    data_access_set_guild_tournament_text_channel_id,
    data_access_get_guild_tournament_text_channel_id,
)
from deps.values import (
    COMMAND_TOURNAMENT_CHANNEL_GET_CHANNEL,
    COMMAND_TOURNAMENT_CHANNEL_SET_CHANNEL,
    COMMAND_TOURNAMENT_CREATE_TOURNAMENT,
    COMMAND_TOURNAMENT_MOD_SEND_SCORE_TOURNAMENT,
    COMMAND_TOURNAMENT_START_TOURNAMENT,
)
from deps.mybot import MyBot
from deps.log import print_warning_log
from deps.tournament_models import BestOf, TournamentSize
from deps.tournament_values import TOURNAMENT_MAPS
from deps.tournament_data_class import Tournament
from deps.tournament_functions import start_tournament
from ui.tournament_match_score_report import TournamentMatchScoreReport


class ModTournament(commands.Cog):
    """Moderator commands for settings the channels that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_TOURNAMENT_CHANNEL_SET_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_tournament_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """
        An administrator can set the channel where the tournament message will be sent
        """
        guild_id = interaction.guild.id
        data_access_set_guild_tournament_text_channel_id(guild_id, channel.id)

        await interaction.response.send_message(
            f"Confirmed to send tournament message into #{channel.name}.",
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_TOURNAMENT_CHANNEL_GET_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def see_tournament_text_channel(self, interaction: discord.Interaction):
        """Display the text channel configured"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_guild_tournament_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No tournament channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Tournament text channel not set.", ephemeral=True)
            return

        await interaction.followup.send(f"The tournament text channel is <#{channel_id}>", ephemeral=True)

    @app_commands.command(name=COMMAND_TOURNAMENT_CREATE_TOURNAMENT)
    @commands.has_permissions(administrator=True)
    async def create_tournament(
        self,
        interaction: discord.Interaction,
        name: str,
        registration_date_start: str = date.today().strftime("%Y-%m-%d"),
        start_date: str = date.today().strftime("%Y-%m-%d"),
        end_date: str = date.today().strftime("%Y-%m-%d"),
        best_of: BestOf = BestOf.THREE,
        max_users: TournamentSize = TournamentSize.SIXTEEN,
    ):
        """Create a tournament"""
        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        channel_id = await data_access_get_guild_tournament_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"create_tournament:No tournament channel in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("Tournament text channel not set.", ephemeral=True)
            return

        registration_date_start_date = datetime.strptime(registration_date_start, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        start_date_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date_date = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        best_of_number = best_of.value
        max_users_number = max_users.value
        data_access_insert_tournament(
            guild_id,
            name,
            registration_date_start_date,
            start_date_date,
            end_date_date,
            best_of_number,
            max_users_number,
            TOURNAMENT_MAPS,
        )
        await interaction.followup.send(f"Created tournament {name}", ephemeral=True)

    @app_commands.command(name=COMMAND_TOURNAMENT_START_TOURNAMENT)
    @commands.has_permissions(administrator=True)
    async def start_tournament_by_id(self, interaction: discord.Interaction, tournament_id: int):
        """Start tournament"""
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id == interaction.guild.owner_id:
            tournament: Tournament = fetch_tournament_by_id(tournament_id)
            start_tournament(tournament)
            await interaction.followup.send(f"Tournament '{tournament.name}' Started", ephemeral=True)
        else:
            await interaction.followup.send("Only the owner of the guild can reset the cache", ephemeral=True)

    @app_commands.command(name=COMMAND_TOURNAMENT_MOD_SEND_SCORE_TOURNAMENT)
    async def send_score_tournament_by_mod(self, interaction: discord.Interaction, member: discord.Member):
        """
        Select a user, then a tournament to make the user report a lost match
        """
        user_id = member.id
        guild_id = interaction.guild.id
        list_tournaments: List[Tournament] = fetch_tournament_active_to_interact_for_user(guild_id, user_id)

        if len(list_tournaments) == 0:
            print_warning_log(
                f"send_score_tournament_by_mod: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {interaction.guild.name}({interaction.guild.id})."
            )
            await interaction.response.send_message(
                f"No active tournament available for {member.display_name}.", ephemeral=True
            )
            return
        view = TournamentMatchScoreReport(list_tournaments)
        await interaction.response.send_message(
            "Choose the tournament to report a match lost",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModTournament(bot))
