import io
from typing import List
import discord
from discord.ext import commands
from discord import app_commands

from deps.tournament_data_access import fetch_tournament_games_by_tournament_id, fetch_active_tournament_by_guild
from deps.values import (
    COMMAND_TOURNAMENT_REGISTER_TOURNAMENT,
    COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT,
    COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT,
)
from deps.mybot import MyBot
from deps.log import print_log, print_warning_log
from tournament_functions import build_tournament_tree
from deps.tournament_data_class import Tournament, TournamentGame
from deps.tournament_visualizer import plot_tournament_bracket


class UserTournamentFeatures(commands.Cog):
    """User command for the tournament that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_TOURNAMENT_REGISTER_TOURNAMENT)
    async def register_tournament(self, interaction: discord.Interaction):
        """
        A user can register to an existing tournament if it is not full and before the tournament starts and aftert the registration opens
        """
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild.id

        await interaction.followup.send(f"TODO", ephemeral=False)

    @app_commands.command(name=COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT)
    async def send_score_tournament(self, interaction: discord.Interaction):
        """
        One of the two players can send the score of the match
        """
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild.id
        
        await interaction.followup.send(f"TODO", ephemeral=False)

    @app_commands.command(name=COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT)
    async def see_braket_tournament(self, interaction: discord.Interaction):
        """
        See the complete bracket for the tournament
        """
        await interaction.response.defer(ephemeral=False)
        guild_id = interaction.guild.id
        tournament: List[Tournament] = await fetch_active_tournament_by_guild(guild_id)
        if len(tournament) == 0:
            print_log(f"No active tournament in guild {interaction.guild.name}. Skipping.")
            await interaction.followup.send("No active tournament in this server.", ephemeral=False)
            return

        for t in tournament:
            tournament_games: List[TournamentGame] = await fetch_tournament_games_by_tournament_id(t.id)
            tournament_tree = build_tournament_tree(tournament_games)
            if tournament_tree is None:
                print_warning_log(f"Failed to build tournament tree for tournament {t.id}. Skipping.")
                await interaction.followup.send("Failed to build tournament tree.", ephemeral=False)
                return
            img_bytes = plot_tournament_bracket(tournament_tree, False)
            bytesio = io.BytesIO(img_bytes)
            bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
            file = discord.File(fp=bytesio, filename="plot.png")
            await interaction.response.send_message(file=file, ephemeral=False)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserTournamentFeatures(bot))
