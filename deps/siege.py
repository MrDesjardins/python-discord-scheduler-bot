""" Information about Siege """

import discord

EMOJI_CHAMPION = "<:Champion:1279550703311917208>"
EMOJI_DIAMOND = "<:Diamond:1279550706373623883> "
EMOJI_EMERALD = "<:Emerald:1279550712233197619> "
EMOJI_PLATINUM = "<:Platinum:1279550709616087052>"
EMOJI_GOLD = "<:Gold:1279550707971915776> "
EMOJI_SILVER = "<:Silver:1279550710941483038"
EMOJI_BRONZE = "<:Bronze:1279550704427597826> "
EMOJI_COPPER = "<:Copper:1279550705551802399> "


def get_user_rank_emoji(user: discord.Member) -> str:
    """Check the user's roles to determine their rank
    The function assumes a specific 8 roles with 8 emojis which might not be the case for your server
    """
    for role in user.roles:
        print(f"Checking role {role.name}")
        if role.name == "Champion":
            return EMOJI_CHAMPION
        elif role.name == "Diamond":
            return EMOJI_DIAMOND
        elif role.name == "Emerald":
            return EMOJI_EMERALD
        elif role.name == "Platinum":
            return EMOJI_PLATINUM
        elif role.name == "Gold":
            return EMOJI_GOLD
        elif role.name == "Silver":
            return EMOJI_SILVER
        elif role.name == "Bronze":
            return EMOJI_BRONZE
        elif role.name == "Copper":
            return EMOJI_COPPER
    print("No rank found")
    return EMOJI_COPPER
