import discord
from discord.ext import commands
from discord import app_commands

from deps.values import (
    COMMAND_TOURNAMENT_REGISTER_TOURNAMENT,
    COMMAND_TOURNAMENT_SEE_BRACKET_TOURNAMENT,
    COMMAND_TOURNAMENT_SEND_SCORE_TOURNAMENT,
)
from deps.mybot import MyBot
from deps.log import print_warning_log


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

        await interaction.followup.send(f"TODO", ephemeral=False)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserTournamentFeatures(bot))
