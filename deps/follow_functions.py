from deps.follow_data_access import fetch_all_followers_of_user_id
from deps.mybot import MyBot


async def send_private_notification_following_user(bot: MyBot, joined_user_id: int, guild_id: int, channel_id: int):
    """Sends a private notification to users who are following the joined user."""

    followed_users: list[int] = fetch_all_followers_of_user_id(joined_user_id)
    if not followed_users:
        return  # No one is following this user, nothing to do

    guild = bot.get_guild(guild_id)

    for discord_user_id in followed_users:
        user = bot.get_user(discord_user_id)
        if user:
            try:
                await user.send(
                    f"User <@{joined_user_id}> has joined <#{channel_id}> in **{guild.name}**."
                )
            except Exception as e:
                print(f"Failed to send DM to user {discord_user_id.follower_user_id}: {e}")