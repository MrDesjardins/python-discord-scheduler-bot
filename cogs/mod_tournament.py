"""
Moderator command related to the tournament feature
"""

from datetime import date, datetime, timezone
from typing import List
import discord
from discord.ext import commands
from discord import app_commands
from deps.tournaments.tournament_data_access import (
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
    COMMAND_TOURNAMENT_END_TOURNAMENT,
    COMMAND_TOURNAMENT_MOD_SEND_SCORE_TOURNAMENT,
    COMMAND_TOURNAMENT_START_TOURNAMENT,
)
from deps.mybot import MyBot
from deps.log import print_error_log, print_warning_log
from deps.tournaments.tournament_models import BestOf, TournamentSize
from deps.tournaments.tournament_values import TOURNAMENT_MAPS
from deps.tournaments.tournament_data_class import Tournament
from deps.tournaments.tournament_functions import (
    clean_maps_input,
    start_tournament,
)
from deps.tournaments.tournament_ui_functions import (
    post_end_tournament_messages,
)
from ui.tournament_match_score_report import TournamentMatchScoreReport


class ModTournament(commands.Cog):
    """Moderator commands for settings the channels that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_TOURNAMENT_CHANNEL_SET_CHANNEL)
    @commands.has_permissions(administrator=True)
    async def set_tournament_text_channel(self, interaction: discord.Interaction, channel: discord.TextChannel) -> None:
        """
        An administrator can set the channel where the tournament message will be sent
        """
        guild_id = interaction.guild_id
        if guild_id is None:
            print_error_log("set_tournament_text_channel: Guild ID is None.")
            return
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
        guild = interaction.guild
        if guild is None:
            print_error_log("see_tournament_text_channel: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_guild_tournament_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"No tournament channel in guild {guild.name}. Skipping.")
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
        maps: str = TOURNAMENT_MAPS,
        team_size: int = 1,
    ):
        """Create a tournament"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("create_tournament: Guild is None.")
            return
        guild_id = guild.id
        channel_id = await data_access_get_guild_tournament_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"create_tournament:No tournament channel in guild {guild.name}. Skipping.")
            await interaction.followup.send("Tournament text channel not set.", ephemeral=True)
            return

        registration_date_start_date = datetime.strptime(registration_date_start, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        start_date_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_date_date = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        best_of_number = best_of.value
        max_users_number = max_users.value
        clean_maps = clean_maps_input(maps)
        if team_size < 1 or team_size > 2:
            await interaction.followup.send(
                "Team size must be 1 or 2 players.",
                ephemeral=True,
            )
            return
        data_access_insert_tournament(
            guild_id,
            name,
            registration_date_start_date,
            start_date_date,
            end_date_date,
            best_of_number,
            max_users_number,
            clean_maps,
            team_size,
        )
        await interaction.followup.send(f"Created tournament {name}", ephemeral=True)

    @app_commands.command(name=COMMAND_TOURNAMENT_START_TOURNAMENT)
    @commands.has_permissions(administrator=True)
    async def start_tournament_by_id(self, interaction: discord.Interaction, tournament_id: int):
        """Start tournament"""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if guild is None:
            print_error_log("start_tournament_by_id: Guild is None.")
            return

        if interaction.user.id == guild.owner_id:
            tournament = fetch_tournament_by_id(tournament_id)
            if tournament is None:
                await interaction.followup.send(
                    f"Tournament with id {tournament_id} not found",
                    ephemeral=True,
                )
                return
            await start_tournament(tournament)
            await interaction.followup.send(f"Tournament '{tournament.name}' Started", ephemeral=True)
        else:
            await interaction.followup.send(
                "Only the owner of the guild can reset the cache",
                ephemeral=True,
            )

    @app_commands.command(name=COMMAND_TOURNAMENT_MOD_SEND_SCORE_TOURNAMENT)
    async def send_score_tournament_by_mod(self, interaction: discord.Interaction, member: discord.Member):
        """
        Select a user, then a tournament to make the user report a lost match
        """
        user_id = member.id
        guild = interaction.guild
        if guild is None:
            print_error_log("send_score_tournament_by_mod: Guild is None.")
            return
        guild_id = guild.id
        list_tournaments: List[Tournament] = fetch_tournament_active_to_interact_for_user(guild_id, user_id)

        if len(list_tournaments) == 0:
            print_warning_log(
                f"""send_score_tournament_by_mod: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {guild.name}({guild.id})."""
            )
            await interaction.response.send_message(
                f"No active tournament available for {member.display_name}.",
                ephemeral=True,
            )
            return
        view = TournamentMatchScoreReport(list_tournaments, user_id)
        await interaction.response.send_message(
            "Choose the tournament to report a match lost",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_TOURNAMENT_END_TOURNAMENT)
    @commands.has_permissions(administrator=True)
    async def send_end_tournament_by_mod(self, interaction: discord.Interaction, tournament_id: int):
        """
        Mod can display the winners and the bet leaderboard if the system didn't do it automatically
        """
        await interaction.response.defer()
        try:
            await post_end_tournament_messages(interaction, tournament_id)
        except Exception as e:
            print_error_log(f"send_end_tournament_by_mod: {e}")
            await interaction.followup.send(
                "Error while displaying the end of the tournament",
                ephemeral=True,
            )


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModTournament(bot))
