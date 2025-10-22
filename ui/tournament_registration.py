"""User interface for the bot"""

import traceback
from typing import List
import discord
from discord.ui import View
from deps.data_access import data_access_get_channel, data_access_get_guild_tournament_text_channel_id
from deps.tournaments.tournament_data_class import Tournament
from deps.tournaments.tournament_functions import register_for_tournament
from deps.log import print_error_log, print_warning_log
from deps.tournaments.tournament_data_access import get_people_registered_for_tournament
from deps.values import COMMAND_TOURNAMENT_REGISTER_TOURNAMENT


class TournamentRegistration(View):
    """
    A view that allows the user to register to a tournament
    """

    def __init__(self, list_tournaments: List[Tournament]):
        super().__init__()
        self.list_tournaments = list_tournaments

        for t in self.list_tournaments:
            self.add_item(discord.ui.Button(label=t.name, custom_id=str(t.id)))

        self.first_response = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Callback function to check if the interaction is valid"""
        try:
            # Defer the interaction to prevent timeout issues
            await interaction.response.defer(ephemeral=True)

            # Check if the guild is present in the interaction
            guild = interaction.guild
            if guild is None:
                print_error_log("TournamentRegistration UI> Guild not found in the interaction")
                await interaction.followup.send("Guild not found in the interaction.", ephemeral=True)
                return True
            guild_id = guild.id

            # Save user responses
            tournament_id = int(interaction.data["custom_id"])
            reason = register_for_tournament(tournament_id, interaction.user.id)

            if not reason.is_successful:
                print_error_log(f"TournamentRegistration UI> Registration failed: {reason.text}")
                await interaction.followup.send(f"Registration to the tournament failed: {reason.text}", ephemeral=True)
                return True

            # Find the tournament from the id variable in the list of tournament to get the starting date
            tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
            if not tournament:
                print_error_log(f"Tournament not found for id: {tournament_id}")
                await interaction.followup.send("Tournament not found.", ephemeral=True)
                return True

            date_start = tournament.start_date.strftime("%Y-%m-%d")
            # Send final confirmation message with the saved data
            await interaction.followup.send(
                f"You are registered. A new message will tag you when the tournament will start ({date_start}).",
                ephemeral=True,
            )

            # Send a message in the tournament channel to encourage other to join
            channel_id = await data_access_get_guild_tournament_text_channel_id(guild_id)
            if channel_id is None:
                print_warning_log(f"TournamentRegistration UI> Channel id not found for guild id: {guild_id}")
                await interaction.followup.send("Tournament channel not found.", ephemeral=True)
                return True
            channel = await data_access_get_channel(channel_id)
            if channel is None:
                print_warning_log(f"TournamentRegistration UI> Channel not found for id: {channel_id}")
                await interaction.followup.send("Tournament channel not found.", ephemeral=True)
                return True
            tournament_users = get_people_registered_for_tournament(tournament_id)
            place_available = tournament.max_players - len(tournament_users)
            if place_available == 0:
                await channel.send(
                    f'{interaction.user.mention} has registered for the tournament "{tournament.name}".\n\nThe tournament is full and will start on {date_start}.'
                )
            else:
                await channel.send(
                    f'{interaction.user.mention} has registered for the tournament "{tournament.name}"!\n\nOnly {place_available} more spots available. Hurry, the tournament starts on {date_start}. Use the command /`{COMMAND_TOURNAMENT_REGISTER_TOURNAMENT}` to join.'
                )

            return True
        except Exception as e:
            print_error_log(f"TournamentRegistration UI>An error occurred: {e}")
            traceback.print_exc()  # This prints the full error traceback
            await interaction.followup.send("An unexpected error occurred. Please contact a moderator.", ephemeral=True)
            return False
