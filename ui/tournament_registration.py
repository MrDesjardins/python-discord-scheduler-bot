""" User interface for the bot"""

from typing import List
import discord
from discord.ui import View
from deps.data_access import data_access_get_channel, data_access_get_guild_tournament_text_channel_id
from deps.tournament_data_class import Tournament
from deps.tournament_functions import register_for_tournament
from deps.log import print_error_log, print_warning_log
from deps.tournament_data_access import get_people_registered_for_tournament


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

        # Defer the interaction to prevent timeout issues
        await interaction.response.defer(ephemeral=True)
        # Save user responses
        tournament_id = int(interaction.data["custom_id"])
        register_for_tournament(tournament_id, interaction.user.id)

        # Find the tournament from the id variable in the list of tournament to get the starting date
        tournament = next((t for t in self.list_tournaments if t.id == tournament_id), None)
        if not tournament:
            print_error_log(f"Tournament not found for id {self.list_tournaments}")
            return True

        date_start = tournament.start_date.strftime("%Y-%m-%d")
        # Send final confirmation message with the saved data
        await interaction.followup.send(
            f"You are registered. A new message will tag you when the tournament will start ({date_start}).",
            ephemeral=True,
        )

        # Send a message in the tournament channel to encourage other to join
        guild_id = interaction.guild.id
        channel_id = await data_access_get_guild_tournament_text_channel_id(guild_id)
        if channel_id is None:
            print_warning_log(f"TournamentRegistration UI> Channel id not found for guild id {guild_id}")
            return True
        channel = await data_access_get_channel(channel_id)
        if channel is None:
            print_warning_log(f"TournamentRegistration UI> Channel not found for id {channel_id}")
            return True
        tournament_users = get_people_registered_for_tournament(tournament_id)
        place_available = tournament.max_players - len(tournament_users)
        if place_available == 0:
            await channel.send(
                f'{interaction.user.mention} has registered for the tournament "{tournament.name}". The tournament is full and will start on {date_start}.'
            )
        else:
            await channel.send(
                f'{interaction.user.mention} has registered for the tournament "{tournament.name}". Only {place_available} spots available.'
            )
        return True
