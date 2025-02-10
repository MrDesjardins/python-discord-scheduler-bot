from datetime import date, datetime, timezone
from typing import List, Optional
import discord
from discord.ext import commands
from discord import app_commands
from deps.bet.bet_functions import generate_msg_bet_leaderboard
from deps.tournaments.tournament_data_access import (
    data_access_insert_tournament,
    fetch_tournament_active_to_interact_for_user,
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
)
from deps.data_access import (
    data_access_get_member,
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
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.tournaments.tournament_functions import (
    build_tournament_tree,
    clean_maps_input,
    get_tournament_final_result_positions,
    start_tournament,
)
from deps.tournaments.tournament_discord_actions import generate_bracket_file
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
        maps: str = TOURNAMENT_MAPS,
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
        clean_maps = clean_maps_input(maps)
        data_access_insert_tournament(
            guild_id,
            name,
            registration_date_start_date,
            start_date_date,
            end_date_date,
            best_of_number,
            max_users_number,
            clean_maps,
        )
        await interaction.followup.send(f"Created tournament {name}", ephemeral=True)

    @app_commands.command(name=COMMAND_TOURNAMENT_START_TOURNAMENT)
    @commands.has_permissions(administrator=True)
    async def start_tournament_by_id(self, interaction: discord.Interaction, tournament_id: int):
        """Start tournament"""
        await interaction.response.defer(ephemeral=True)

        if interaction.user.id == interaction.guild.owner_id:
            tournament: Tournament = fetch_tournament_by_id(tournament_id)
            await start_tournament(tournament)
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
        view = TournamentMatchScoreReport(list_tournaments, user_id)
        await interaction.response.send_message(
            "Choose the tournament to report a match lost",
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name=COMMAND_TOURNAMENT_END_TOURNAMENT)
    async def send_end_tournament_by_mod(self, interaction: discord.Interaction, tournament_id: int):
        """
        In case the last report does not work, a mod can display the winners and the bet leaderboard
        """
        await interaction.response.defer()
        tournament: Optional[Tournament] = fetch_tournament_by_id(tournament_id)

        if tournament is None:
            print_warning_log(f"send_end_tournament_by_mod: cannot find tournament {tournament_id}.")
            await interaction.response.send_message("No active tournament available", ephemeral=True)
            return

        tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
        tournament_tree = build_tournament_tree(tournament_games)
        if tournament_tree is None:
            print_error_log(
                f"TournamentMatchScoreReport: process_tournament_result: Failed to build tournament tree for tournament {tournament_id}. Skipping."
            )
        final_score = get_tournament_final_result_positions(tournament_tree)
        file = generate_bracket_file(tournament_id)
        if final_score is None:
            await interaction.followup.send(file=file, ephemeral=False)
        else:
            # Tournament is over. We show the winners
            try:
                m1 = await data_access_get_member(interaction.guild_id, final_score.first_place_user_id)
                first_place = m1.mention if m1 else "Unknown"
                m2 = await data_access_get_member(interaction.guild_id, final_score.second_place_user_id)
                second_place = m2.mention if m2 else "Unknown"
                m3_1 = await data_access_get_member(interaction.guild_id, final_score.third_place_user_id_1)
                third_place1 = m3_1.mention if m3_1 else "Unknown"
                m3_2 = await data_access_get_member(interaction.guild_id, final_score.third_place_user_id_2)
                third_place2 = m3_2.mention if m3_2 else "None"
            except Exception as e:
                # Might go in here in development since there is no member in the guild
                print_error_log(
                    f"TournamentMatchScoreReport: process_tournament_result: Error while fetching member: {e}"
                )
                first_place = "Unknown"
                second_place = "Unknown"
                third_place1 = "Unknown"
                third_place2 = "Unknown"
            await interaction.followup.send(file=file, ephemeral=False)
            third_place_full = f"{third_place1} and {third_place2}" if third_place2 != "None" else third_place1
            await interaction.followup.send(
                f"The tournament **{tournament.name}** has finished!\n Winners are:\n🥇 {first_place}\n🥈 {second_place}\n🥉 {third_place_full} ",
                ephemeral=False,
            )

            # Generate leaderboard at the end of the tournament
            try:
                msg_better_list = await generate_msg_bet_leaderboard(tournament)
            except Exception as e:
                print_error_log(
                    f"TournamentMatchScoreReport: process_tournament_result: Error while generating bet leaderboard: {e}"
                )
                msg_better_list = ""
            if msg_better_list != "":
                await interaction.followup.send(
                    f"Top Better Wallet Value for the tournament **{tournament.name}** are:\n{msg_better_list}",
                    ephemeral=False,
                )


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModTournament(bot))
