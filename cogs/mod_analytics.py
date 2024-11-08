import io
import discord
from discord.ext import commands
from discord import app_commands
from deps.analytic_visualizer import display_graph_cluster_people
from deps.values import COMMAND_SHOW_COMMUNITY
from deps.mybot import MyBot


class ModAnalytics(commands.Cog):
    """Moderator commands for analytics"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_SHOW_COMMUNITY)
    @commands.has_permissions(administrator=True)
    async def community_show_image(self, interaction: discord.Interaction, from_day_ago: int = 90, to_day_ago: int = 0):
        """Activate or deactivate the bot voice message"""
        img_bytes = display_graph_cluster_people(False, from_day_ago, to_day_ago)
        bytesio = io.BytesIO(img_bytes)
        bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
        file = discord.File(fp=bytesio, filename="plot.png")
        await interaction.response.send_message(file=file, ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModAnalytics(bot))
