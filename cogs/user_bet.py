from typing import List
import discord
from discord.ext import commands
from discord import app_commands

from deps.bet.bet_data_class import BetUserTournament
from deps.bet.bet_functions import get_bet_user_wallet_for_tournament
from deps.tournaments.tournament_data_access import (
    fetch_active_tournament_by_guild,
)
from deps.values import COMMAND_BET, COMMAND_BET_ACTIVE_TOURNAMENT, COMMAND_BET_LEADERBOARD, COMMAND_BET_WALLET
from deps.mybot import MyBot
from deps.log import print_warning_log
from deps.tournaments.tournament_data_class import Tournament
from ui.bet_tournament_selector_for_active_tournament import BetTournamentSelectorForActiveMarket
from ui.bet_tournament_selector_for_leaderboard import BetTournamentSelectorForLeaderboard
from ui.bet_tournament_selector_for_market import BetTournamentSelectorForMarket


class UserBetFeatures(commands.Cog):
    """User command for the tournament that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_BET_WALLET)
    async def bet_see_wallet_amount(self, interaction: discord.Interaction):
        """
        See the amount of money in the wallet for the tournament
        """
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        list_tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
        if len(list_tournaments) == 0:
            print_warning_log(
                f"bet_see_wallet_amount: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {interaction.guild.name}({interaction.guild.id})."
            )
            await interaction.response.send_message("No active tournament available for you.", ephemeral=True)
        elif len(list_tournaments) == 1:
            tournament_id = list_tournaments[0].id
            wallet: BetUserTournament = get_bet_user_wallet_for_tournament(tournament_id, user_id)
            await interaction.response.send_message(f"You have ${wallet.amount:.2f}", ephemeral=True)
        else:
            # Combined message with all tournaments
            msg = "You have many wallets (one per tournament). Here are the amounts:\n"
            for tournament in list_tournaments:
                wallet: BetUserTournament = get_bet_user_wallet_for_tournament(tournament.id, user_id)
                msg += f"➡️ {tournament.name}: ${wallet.amount:.2f}\n"
            await interaction.response.send_message(msg, ephemeral=True)

    # @app_commands.command(name=COMMAND_BET_MARKET)
    # async def bet_market(self, interaction: discord.Interaction):
    #     """
    #     See the market (available games to bet)
    #     """
    #     guild_id = interaction.guild.id
    #     list_tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
    #     if len(list_tournaments) == 0:
    #         print_warning_log(
    #             f"bet_market: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {interaction.guild.name}({interaction.guild.id})."
    #         )
    #         await interaction.response.send_message("No active tournament available to bet.", ephemeral=True)
    #         return
    #     view = BetTournamentSelectorForMarket(list_tournaments)

    #     await interaction.response.send_message(
    #         "Choose the tournament to see the market",
    #         view=view,
    #         ephemeral=True,
    #     )

    @app_commands.command(name=COMMAND_BET)
    async def place_bet(self, interaction: discord.Interaction):
        """
        The command does:
        1) Show the tournament
        2) Upon selection, show the market (games available to bet)
        3) Allow the user to click on the game to bet
        4) The user select an amount to bet
        """
        guild_id = interaction.guild.id
        list_tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
        if len(list_tournaments) == 0:
            print_warning_log(
                f"place_bet: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {interaction.guild.name}({interaction.guild.id})."
            )
            await interaction.response.send_message("No active tournament available to bet.", ephemeral=True)
            return
        view = BetTournamentSelectorForMarket(list_tournaments)

        await interaction.response.send_message(
            "Choose the tournament to see the market",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_BET_ACTIVE_TOURNAMENT)
    async def bet_active_tournament(self, interaction: discord.Interaction):
        """
        See the active bet for a tournament
        """
        guild_id = interaction.guild.id
        list_tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
        if len(list_tournaments) == 0:
            print_warning_log(
                f"bet_active_tournament: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {interaction.guild.name}({interaction.guild.id})."
            )
            await interaction.response.send_message(
                "No active tournament available to visualize active bets.", ephemeral=True
            )
            return
        view = BetTournamentSelectorForActiveMarket(list_tournaments)

        await interaction.response.send_message(
            "Choose the tournament to see the active bets",
            view=view,
            ephemeral=False,
        )

    @app_commands.command(name=COMMAND_BET_LEADERBOARD)
    async def bet_leaderboard_command(self, interaction: discord.Interaction):
        """
        See the leaderboard for a tournament
        """
        guild_id = interaction.guild.id
        list_tournaments: List[Tournament] = fetch_active_tournament_by_guild(guild_id)
        if len(list_tournaments) == 0:
            print_warning_log(
                f"bet_leaderboard_command: No active tournament available for user {interaction.user.display_name}({interaction.user.id}) in guild {interaction.guild.name}({interaction.guild.id})."
            )
            await interaction.response.send_message(
                "No active tournament available to visualize a bet leaderboard.", ephemeral=True
            )
            return
        view = BetTournamentSelectorForLeaderboard(list_tournaments)

        await interaction.response.send_message(
            "Choose the tournament to see the leaderboard of the bets",
            view=view,
            ephemeral=False,
        )


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserBetFeatures(bot))
