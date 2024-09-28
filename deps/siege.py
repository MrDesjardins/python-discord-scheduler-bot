""" Information about Siege """

import discord

def get_user_rank_emoji(guild_emoji: dict[str, str], user: discord.Member) -> str:
    """
    Check the user's roles to determine their rank
    The function assumes a specific 8 roles with 8 emojis which might not be the case for your server
    """
    for role in user.roles:
        if role.name in ["Champion", "Diamond", "Emerald", "Platinum", "Gold", "Silver", "Bronze", "Copper"]:
            print(f"Role: {role.name} found")
            return f"<:{role.name}:{guild_emoji[role.name]}>"
    print("No rank found")

    return f"<:Copper:{guild_emoji['Copper']}>" if "Copper" in guild_emoji else "N/A"
