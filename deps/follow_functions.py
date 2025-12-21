from deps.data_access import data_access_get_guild_voice_channel_ids, data_access_get_voice_user_list
from deps.follow_data_access import fetch_all_followers_of_user_id
from deps.mybot import MyBot

async def send_private_notification_following_user(bot: MyBot, joined_user_id: int, guild_id: int, channel_id: int):
    """Sends a private notification to users who are following the joined user."""
    guild = bot.get_guild(guild_id)
    
    # Get all the users who is following the user who joined a voice channel
    followed_user_ids: list[int] = fetch_all_followers_of_user_id(joined_user_id)
    if not followed_user_ids:
        return  # No one is following this user, nothing to do

    # Filter down the list for only users who are not currently in an official voice channel
    guild_voice_channels = await data_access_get_guild_voice_channel_ids(guild_id)
    if guild_voice_channels is None:
        guild_voice_channels = guild_voice_channels = await data_access_get_voice_user_list(guild_id, channel_id)
    filtered_followed_user_ids = [user_id for user_id in followed_user_ids if user_id not in guild_voice_channels]

    for discord_user_id in filtered_followed_user_ids:
        user = bot.get_user(discord_user_id)
        if user:
            try:
                await user.send(
                    f"User <@{joined_user_id}> has joined <#{channel_id}> in **{guild.name}**."
                )
            except Exception as e:
                print(f"Failed to send DM to user {discord_user_id} for user {joined_user_id}: {e}")