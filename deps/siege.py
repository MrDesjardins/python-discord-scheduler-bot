""" Information about Siege """

import discord

siege_ranks = [
    "Champion",
    "Diamond",
    "Emerald",
    "Platinum",
    "Gold",
    "Silver",
    "Bronze",
    "Copper",
]


def get_color_for_rank(member: discord.Member) -> int:
    """Return a color per rank"""
    color_map = {
        "Champion": 0xFFC0CB,  # Pink
        "Diamond": 0x800080,  # Purple
        "Emerald": 0x008000,  # Green
        "Platinum": 0x00FFFF,  # Cyan
        "Gold": 0xFFFF00,  # Yellow
        "Silver": 0x8080800,  # Gray
        "Bronze": 0xD2691E,  # Dark Orange
        "Copper": 0x8B0000,  # Dark Red
    }
    for role in member.roles:
        if role.name in siege_ranks:
            return color_map.get(role.name, 0x8B0000)

    return color_map.get("Copper", 0x8B0000)


def get_user_rank_siege(guild_emoji: dict[str, str], user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    """
    if user is None:
        return get_guil_rank_emoji(guild_emoji, "Copper")

    for role in user.roles:
        if role.name in siege_ranks:
            return role.name
    return "Copper"


def get_user_rank_emoji(guild_emoji: dict[str, str], user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    The function assumes a specific 8 roles with 8 emojis which might not be the case for your server
    """
    if user is None:
        return get_guil_rank_emoji(guild_emoji, "Copper")

    for role in user.roles:
        if role.name in siege_ranks:
            print(f"Role: {role.name} found")
            return get_guil_rank_emoji(guild_emoji, role.name)
    print("No rank found")

    return get_guil_rank_emoji(guild_emoji, "Copper")


def get_guil_rank_emoji(guild_emoji: dict[str, str], emoji_name: str) -> str:
    """
    Extract the full emoji code for Discord to use from the emoji name and the guild emoji dictionary
    which contain the unique ID for the emoji
    """

    if emoji_name in siege_ranks:
        if emoji_name in guild_emoji:
            emoji_id = guild_emoji[emoji_name]
            return f"<:{emoji_name}:{emoji_id}>"
    print("No rank found")

    return f"<:Copper:{guild_emoji['Copper']}>" if "Copper" in guild_emoji else "N/A"
