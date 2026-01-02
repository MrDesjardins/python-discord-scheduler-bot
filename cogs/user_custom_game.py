from datetime import datetime, timezone
from typing import List, Union
import discord
from discord.ext import commands
from discord import app_commands

from deps.custom_match.custom_match_data_class import MapSuggestion
from deps.custom_match.custom_match_ui_functions import CompleteCommandView
from deps.custom_match.custom_match_values import MapAlgo, TeamAlgo
from deps.custom_match.custom_match_functions import (
    create_team_by_win_percentage,
    select_map_based_on_algorithm,
    select_team_by_algorithm,
)
from deps.data_access import (
    data_access_get_channel,
    data_access_get_channel,
    data_access_get_custom_game_voice_channels,
    data_access_get_member,
)
from deps.custom_match.custom_match_data_access import (
    data_access_fetch_user_subscription_for_guild,
    data_access_subscribe_custom_game,
    data_access_unsubscribe_custom_game,
)

from deps.values import (
    COMMAND_CUSTOM_GAME_LFG,
    COMMAND_CUSTOM_GAME_MAKE_TEAM,
    COMMAND_CUSTOM_GAME_SUBSCRIBE,
    COMMAND_CUSTOM_GAME_UNSUBSCRIBE,
    COMMAND_CUSTOM_GAME_SEE_SUBSCRIPTIONS,
)
from deps.mybot import MyBot
from deps.log import print_warning_log, print_error_log


class UserCustomGameFeatures(commands.Cog):
    """User command for the custom game that the bot can interact with"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_CUSTOM_GAME_SUBSCRIBE)
    async def register_custom_game(self, interaction: discord.Interaction):
        """
        Register to a custom game
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        if interaction.guild is None:
            print_error_log(
                f"register_custom_game: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        current_datetime = datetime.now(timezone.utc)
        data_access_subscribe_custom_game(user_id, guild_id, current_datetime)
        await interaction.followup.send(
            content=f"{display_name} subscribed to future 10-man notifications using the /{COMMAND_CUSTOM_GAME_SUBSCRIBE}. To unsubscribe use /{COMMAND_CUSTOM_GAME_UNSUBSCRIBE}",
            ephemeral=False,
        )

    @app_commands.command(name=COMMAND_CUSTOM_GAME_UNSUBSCRIBE)
    async def unsubscribe_custom_game(self, interaction: discord.Interaction):
        """
        Unsubscribe from custom game notifications
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        if interaction.guild is None:
            print_error_log(f"see_custom_game_subscriptions: No guild available for user {display_name}({user_id}).")
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        user_ids: List[int] = data_access_fetch_user_subscription_for_guild(guild_id)
        if not user_ids:
            await interaction.followup.send(
                content="You are not currently subscribed to custom game notifications in this server.", ephemeral=True
            )
            return

        data_access_unsubscribe_custom_game(user_id, guild_id)

        await interaction.followup.send(content=f"{display_name} unsubscribed to 10-man notifications", ephemeral=False)

    @app_commands.command(name=COMMAND_CUSTOM_GAME_SEE_SUBSCRIPTIONS)
    async def see_custom_game_subscriptions(self, interaction: discord.Interaction):
        """
        See all users subscribed to custom game notifications
        """
        await interaction.response.defer()
        if interaction.guild is None:
            print_error_log(
                f"see_custom_game_subscriptions: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        user_ids: List[int] = data_access_fetch_user_subscription_for_guild(guild_id)
        if not user_ids:
            await interaction.followup.send(
                content="No users are currently subscribed to custom game notifications in this server.", ephemeral=True
            )
            return

        member_mentions = []
        for user_id in user_ids:
            member: Union[discord.Member, None] = await data_access_get_member(guild_id, user_id)
            if member:
                member_mentions.append(member.display_name)
            else:
                member_mentions.append(f"User ID {user_id} (not found in guild)")

        mentions_text = ", ".join(member_mentions)
        await interaction.followup.send(
            content=f"Users subscribed to custom game notifications: {mentions_text}", ephemeral=True
        )

    @app_commands.command(name=COMMAND_CUSTOM_GAME_LFG)
    async def custom_game_lfg(self, interaction: discord.Interaction):
        """
        Look for a custom game
        """
        await interaction.response.defer()
        user_id = interaction.user.id
        display_name = interaction.user.display_name
        if interaction.guild is None:
            print_error_log(f"custom_game_lfg: No guild available for user {display_name}({user_id}).")
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id
        user_ids: List[int] = data_access_fetch_user_subscription_for_guild(guild_id)
        if not user_ids:
            await interaction.followup.send(
                content="No users are currently subscribed to custom game notifications in this server.", ephemeral=True
            )
            return

        member_mentions = []
        for user_id in user_ids:
            member: Union[discord.Member, None] = await data_access_get_member(guild_id, user_id)
            if member:
                member_mentions.append(member.mention)
            else:
                member_mentions.append(f"User ID {user_id} (not found in guild)")

        mentions_text = ", ".join(member_mentions)
        await interaction.followup.send(content=f"{mentions_text} are you available for a 10-man?", ephemeral=True)

    @app_commands.command(name=COMMAND_CUSTOM_GAME_MAKE_TEAM)
    async def custom_game_make_team(self, interaction: discord.Interaction, team_algo: TeamAlgo):
        """
        Get all the users from the custom game voice channels and make two teams depending of a selected algorithm
        """
        await interaction.response.defer()
        if interaction.guild is None:
            print_error_log(
                f"custom_game_make_team: No guild available for user {interaction.user.display_name}({interaction.user.id})."
            )
            await interaction.response.send_message("Cannot perform this operation in this guild.", ephemeral=True)
            return
        guild = interaction.guild
        guild_id = guild.id

        lobby_channel_id, team1_channel_id, team2_channel_id = await data_access_get_custom_game_voice_channels(
            guild_id
        )
        if not lobby_channel_id or not team1_channel_id or not team2_channel_id:
            await interaction.followup.send(
                content="Custom game voice channels are not properly configured. Please contact an administrator.",
                ephemeral=True,
            )
            return

        lobby_channel = await data_access_get_channel(lobby_channel_id)
        users_lobby_voice_channel: List[discord.Member] = lobby_channel.members
        if len(users_lobby_voice_channel) == 0:
            await interaction.followup.send(
                content=f"No users are currently in the <#{lobby_channel_id}>.", ephemeral=True
            )
            return
        user_ids = [m.id for m in users_lobby_voice_channel]
        # Map Suggestions
        map_name_1 = await select_map_based_on_algorithm(MapAlgo.WORSE_MAPS_FIRST, user_ids)
        map_name_2 = await select_map_based_on_algorithm(MapAlgo.BEST_MAPS_FIRST, user_ids)
        map_name_3 = await select_map_based_on_algorithm(MapAlgo.LEAST_PLAYED, user_ids)
        map_name_4 = await select_map_based_on_algorithm(MapAlgo.RANDOM, user_ids)

        await interaction.followup.send(
            content=f"""# Map suggestions\n
## By worse maps first (losing rate)\n {format_map(map_name_1)}
## By best maps first (winning rate)\n {format_map(map_name_2)}
## By least played maps first (count)\n {format_map(map_name_3)}
## Randomly selected map\n {format_map(map_name_4)}
                                        """,
            ephemeral=False,
        )

        if isinstance(lobby_channel, discord.VoiceChannel):
            users_lobby_voice_channel: List[discord.Member] = lobby_channel.members
            teams = await select_team_by_algorithm(team_algo, users_lobby_voice_channel)
            await interaction.followup.send(
                content=f"Teams created using logic: {teams.logic}\n\n{teams.explanation}", ephemeral=False
            )
            # Show a button to move the users to their respective channels

            async def on_move_into_team_channels() -> None:
                # Move users to their respective channels
                team1_channel = await data_access_get_channel(team1_channel_id)
                team2_channel = await data_access_get_channel(team2_channel_id)
                if not isinstance(team1_channel, discord.VoiceChannel) or not isinstance(
                    team2_channel, discord.VoiceChannel
                ):
                    print_warning_log(f"custom_game_make_team: Team channels are not voice channels.")
                    return

                for member in teams.team1.members:
                    try:
                        await member.move_to(team1_channel)
                    except discord.Forbidden:
                        print_error_log(
                            f"custom_game_make_team: Forbidden: Failed to move member {member.display_name} to Team Alpha channel: {e}"
                        )
                    except Exception as e:
                        print_error_log(
                            f"custom_game_make_team: Failed to move member {member.display_name} to Team Alpha channel: {e}"
                        )

                for member in teams.team2.members:
                    try:
                        await member.move_to(team2_channel)
                    except discord.Forbidden:
                        print_error_log(
                            f"custom_game_make_team: Forbidden: Failed to move member {member.display_name} to Team Beta channel: {e}"
                        )
                    except Exception as e:
                        print_error_log(
                            f"custom_game_make_team: Failed to move member {member.display_name} to Team Beta channel: {e}"
                        )
                        
            async def on_move_back_lobby() -> None:
                # Move all users back to the lobby channel
                lobby_channel = await data_access_get_channel(lobby_channel_id)
                team1_channel = await data_access_get_channel(team1_channel_id)
                team2_channel = await data_access_get_channel(team2_channel_id)
                if not isinstance(lobby_channel, discord.VoiceChannel):
                    print_warning_log(f"custom_game_make_team: Lobby channel is not a voice channel.")
                    return
                for member in team1_channel.members:
                    try:
                        await member.move_to(lobby_channel)
                    except discord.Forbidden:
                        print_error_log(
                            f"custom_game_make_team: Forbidden: Failed to move member {member.display_name} back to Lobby channel: {e}"
                        )
                    except Exception as e:
                        print_error_log(
                            f"custom_game_make_team: Failed to move member {member.display_name} back to Lobby channel: {e}"
                        )
                for member in team2_channel.members:
                    try:
                        await member.move_to(lobby_channel)
                    except discord.Forbidden:
                        print_error_log(
                            f"custom_game_make_team: Forbidden: Failed to move member {member.display_name} back to Lobby channel: {e}"
                        )
                    except Exception as e:
                        print_error_log(
                            f"custom_game_make_team: Failed to move member {member.display_name} back to Lobby channel: {e}"
                        )
                
            view = CompleteCommandView(author_id=interaction.user.id, on_move_into_team_channels=on_move_into_team_channels, on_move_back_lobby=on_move_back_lobby)

            await interaction.followup.send(
                content="Click the button below to auto-assign people their teams voice channels.", view=view
            )

        else:
            print_warning_log(f"custom_game_make_team: Lobby channel ID {lobby_channel_id} is not a voice channel.")
            await interaction.followup.send(
                content="Lobby voice channel is not found or not a voice channel. Please contact an administrator.",
                ephemeral=True,
            )
            return


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(UserCustomGameFeatures(bot))


def format_map(map_suggestions: List[MapSuggestion]) -> str:
    formatted_maps = []
    for suggestion in map_suggestions:
        formatted_maps.append(f"- {suggestion.map_name} ({suggestion.count})")
    return "\n".join(formatted_maps)
