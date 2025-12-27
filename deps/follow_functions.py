from deps.data_access import data_access_get_user
from deps.follow_data_access import fetch_all_followers_of_user_id
from deps.mybot import MyBot
from deps.log import print_error_log, print_log

async def send_private_notification_following_user(bot: MyBot, joined_user_id: int, guild_id: int, channel_id: int):
    """Sends a private notification to users who are following the joined user."""
    guild = bot.get_guild(guild_id)
    
    # Get all the users who is following the user who joined a voice channel
    followed_user_ids: list[int] = fetch_all_followers_of_user_id(joined_user_id)
    if not followed_user_ids:
        return  # No one is following this user, nothing to do

    # # Filter down the list for only users who are not currently in the same voice channel
    # guild_voice_channels = await data_access_get_guild_voice_channel_ids(guild_id)
    # if guild_voice_channels is None:
    #     guild_voice_channels = guild_voice_channels = await data_access_get_voice_user_list(guild_id, channel_id)
    # filtered_followed_user_ids = [user_id for user_id in followed_user_ids if user_id not in guild_voice_channels]

    # Filter using Discord bot API to ensure is not in a voice channel
    print_log(f"Filtering followers of user {joined_user_id} for guild {guild_id} to exclude those in voice channels. Founds {len(followed_user_ids)} followers.")
    filtered2 = []
    for user_id in followed_user_ids:
        user_discord = await data_access_get_user(guild, user_id)
        if user_discord is None:
            print_log(f"User {user_id} not found in guild {guild_id}; skipping notification for {joined_user_id}.")
            continue

        # If user_discord.voice and user_discord.voice.channel are truthy, the user is currently in a voice channel.
        if user_discord.voice and user_discord.voice.channel:
            print_log(f"User {user_id} is currently in voice channel {user_discord.voice.channel.name}; skipping notification for {joined_user_id}.")
            continue

        # Member exists and is not in a voice channel — notify them.
        filtered2.append(user_id)

    for discord_user_id in filtered2:
        user = bot.get_user(discord_user_id)
        if user:
            try:
                await user.send(
                    f"User <@{joined_user_id}> has joined <#{channel_id}> in **{guild.name}**."
                )
            except Exception as e:
                print_error_log(f"Failed to send DM to user {discord_user_id} for user {joined_user_id}: {e}")