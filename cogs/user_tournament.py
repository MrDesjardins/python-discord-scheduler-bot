from typing import List
import discord
from discord.ext import commands
from discord import app_commands

from deps.tournaments.tournament_data_access import (
    fetch_tournament_not_completed_for_user,
    fetch_tournament_active_to_interact_for_user,
    fetch_tournament_by_guild_user_can_register,
    fetch_active_tournament_by_guild,
)
from deps.values import (
    COMMAND_TOURNAMENT_REGISTER_TOURNAMENT,
    COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT,
    COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT,
)
from deps.mybot import MyBot
from deps.log import print_warning_log, print_error_log
from deps.tournaments.tournament_data_class import Tournament
from ui.tournament_match_score_report import TournamentMatchScoreReport
from ui.tournament_registration import TournamentRegistration
from ui.tournament_see_bracket import TournamentSeeBracket


class UserTournamentFeatures(commands.Cog):
    """User command for the tournament that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_TOURNAMENT_REGISTER_TOURNAMENT)
    async def register_tournament(self, interaction: discord.Interaction):
        """
        Register to a tournament
        """
        user_id = interaction.user.id
        if interaction.guild is None:
            print_error_log(
                f"register_tournament: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        list_tournaments: List[Tournament] = fetch_tournament_by_guild_user_can_register(guild_id, user_id)
        if len(list_tournaments) == 0:
            list_tournaments_users = fetch_tournament_not_completed_for_user(guild_id, user_id)
            if len(list_tournaments_users) == 0:
                print_warning_log(
                    f"No tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {guild.name}({guild.id})."
                )
                await interaction.response.send_message("No new tournament available for you.", ephemeral=True)
                return
            else:
                tournament_names = ", ".join([t.name for t in list_tournaments_users])
                print_warning_log(
                    f"No tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {guild.name}({guild.id}). You are in these tournaments: {tournament_names}"
                )
                await interaction.response.send_message(
                    f"No new tournament available for you. You are in these tournaments: {tournament_names}",
                    ephemeral=True,
                )
            return

        view = TournamentRegistration(list_tournaments)

        await interaction.response.send_message(
            "Choose the tournament to register",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT)
    async def send_score_tournament(self, interaction: discord.Interaction):
        """
        The loser needs to send this command after the match
        """
        user_id = interaction.user.id
        if interaction.guild is None:
            print_error_log(
                f"send_score_tournament: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        list_tournaments: List[Tournament] = fetch_tournament_active_to_interact_for_user(guild_id, user_id)
        if len(list_tournaments) == 0:
            print_warning_log(
                f"send_score_tournament: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {guild.name}({guild.id})."
            )
            await interaction.response.send_message("No active tournament available for you.", ephemeral=True)
            return

        view = TournamentMatchScoreReport(list_tournaments)

        msg = "Click on the tournament and report the score" if len(list_tournaments) > 1 else "Report the score"
        await interaction.response.send_message(
            msg,
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT)
    async def see_braket_tournament(self, interaction: discord.Interaction):
        """
        See the complete bracket for the tournament
        """
        if interaction.guild is None:
            print_error_log(
                f"see_braket_tournament: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        list_tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
        if len(list_tournaments) == 0:
            print_warning_log(
                f"see_braket_tournament: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {guild.name}({guild.id})."
            )
            await interaction.response.send_message("No active tournament.", ephemeral=True)
            return
        view = TournamentSeeBracket(list_tournaments)
        await interaction.response.send_message(
            "Choose the tournament to see the bracket",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserTournamentFeatures(bot))
