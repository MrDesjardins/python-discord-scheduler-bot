""" Information about Siege """

import discord


def get_user_rank_emoji(guild_emoji: dict[str, str], user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    The function assumes a specific 8 roles with 8 emojis which might not be the case for your server
    """
    if user is None:
        return get_guil_rank_emoji(guild_emoji, "Copper")
    
    for role in user.roles:
        if role.name in [
            "Champion",
            "Diamond",
            "Emerald",
            "Platinum",
            "Gold",
            "Silver",
            "Bronze",
            "Copper",
        ]:
            print(f"Role: {role.name} found")
            return get_guil_rank_emoji(guild_emoji, role.name)
    print("No rank found")

    return get_guil_rank_emoji(guild_emoji, "Copper")


def get_guil_rank_emoji(guild_emoji: dict[str, str], emoji_name: str) -> str:
    """
    Extract the full emoji code for Discord to use from the emoji name and the guild emoji dictionary
    which contain the unique ID for the emoji
    """

    if emoji_name in [
        "Champion",
        "Diamond",
        "Emerald",
        "Platinum",
        "Gold",
        "Silver",
        "Bronze",
        "Copper",
    ]:
        if emoji_name in guild_emoji:
            emoji_id = guild_emoji[emoji_name]
            return f"<:{emoji_name}:{emoji_id}>"
    print("No rank found")

    return f"<:Copper:{guild_emoji['Copper']}>" if "Copper" in guild_emoji else "N/A"
