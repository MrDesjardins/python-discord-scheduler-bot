from deps.data_access import data_access_get_guild, data_access_get_member
from deps.follow_data_access import fetch_all_followers_of_user_id
from deps.mybot import MyBot
from deps.log import print_error_log, print_log


async def send_private_notification_following_user(bot: MyBot, joined_user_id: int, guild_id: int, channel_id: int):
    """Sends a private notification to users who are following the joined user."""

    # Get all the users who is following the user who joined a voice channel
    followed_user_ids: list[int] = fetch_all_followers_of_user_id(joined_user_id)
    if not followed_user_ids:
        return  # No one is following this user, nothing to do

    # Filter using Discord bot API to ensure is not in a voice channel
    print_log(
        f"Filtering followers of user {joined_user_id} for guild {guild_id} to exclude those in voice channels. Founds {len(followed_user_ids)} followers."
    )
    users_to_notify = []
    for user_id in followed_user_ids:
        member = await data_access_get_member(guild_id, user_id)
        if member is None:
            print_log(f"User {user_id} not found in guild {guild_id}; skipping notification for {joined_user_id}.")
            continue

        # If member.voice and member.voice.channel are truthy, the user is currently in a voice channel.
        if member.voice and member.voice.channel:
            print_log(
                f"User {user_id} is currently in voice channel {member.voice.channel.name}; skipping notification for {joined_user_id}."
            )
            continue

        # Member exists and is not in a voice channel — notify them.
        users_to_notify.append(user_id)

    guild = await data_access_get_guild(guild_id)
    joined_member = guild.get_member(joined_user_id) if guild else None
    joined_name = joined_member.display_name if joined_member else str(joined_user_id)
    channel = guild.get_channel(channel_id) if guild else None
    channel_name = channel.name if channel else str(channel_id)

    for discord_user_id in users_to_notify:
        user = bot.get_user(discord_user_id)
        if user:
            try:
                await user.send(f"**{joined_name}** joined **{channel_name}**!")
            except Exception as e:
                print_error_log(f"Failed to send DM to user {discord_user_id} for user {joined_user_id}: {e}")
