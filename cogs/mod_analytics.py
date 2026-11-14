"""
Command for moderator only concerning analytic
"""

import asyncio
import io
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands
from deps.app_command_checks import admin_only
from deps.analytic_plot_catalog import PLOTS, render_predefined_plot
from deps.analytic_time_range import PERIOD_LABELS, resolve_day_range
from deps.analytic_visualizer import display_graph_cluster_people
from deps.log import print_error_log
from deps.values import COMMAND_SHOW_COMMUNITY, COMMAND_SHOW_PLOT
from deps.mybot import MyBot

GRAPH_CHOICES = [app_commands.Choice(name=plot.label, value=plot.key) for plot in PLOTS.values()]
PERIOD_CHOICES = [app_commands.Choice(name=label, value=str(index)) for index, label in enumerate(PERIOD_LABELS)]

# matplotlib and plotly keep global figure state, so only one graph may render at a time.
_PLOT_LOCK = asyncio.Lock()


class ModAnalytics(commands.Cog):
    """Moderator commands for analytics"""

    def __init__(self, bot: MyBot):
        self.bot = bot

    @app_commands.command(name=COMMAND_SHOW_COMMUNITY)
    @admin_only
    async def community_show_image(
        self,
        interaction: discord.Interaction,
        from_day_ago: int = 90,
        to_day_ago: int = 0,
    ):
        """Activate or deactivate the bot voice message"""
        img_bytes = display_graph_cluster_people(False, from_day_ago, to_day_ago)
        if img_bytes is None:
            await interaction.response.send_message("Failed to generate community graph.", ephemeral=True)
            return
        bytesio = io.BytesIO(img_bytes)
        bytesio.seek(0)  # Ensure the BytesIO cursor is at the beginning
        file = discord.File(fp=bytesio, filename="plot.png")
        await interaction.response.send_message(file=file, ephemeral=True)

    @app_commands.command(
        name=COMMAND_SHOW_PLOT,
        description="Render one of the predefined analytics graphs.",
    )
    @app_commands.describe(
        graph="Which predefined graph to render",
        period="Time window preset",
        from_day_ago="Custom start in days ago; overrides the period preset",
        to_day_ago="Custom end in days ago (defaults to today)",
        user="Required by the per-user graphs",
        top="How many partners to show for the outside-partner graph",
    )
    @app_commands.choices(graph=GRAPH_CHOICES, period=PERIOD_CHOICES)
    @admin_only
    async def show_plot(  # pylint: disable=too-many-arguments
        self,
        interaction: discord.Interaction,
        graph: str,
        period: str = "0",
        from_day_ago: Optional[int] = None,
        to_day_ago: Optional[int] = None,
        user: Optional[discord.User] = None,
        top: int = 10,
    ):
        """Render a botadmin visualization from Discord."""
        await interaction.response.defer(ephemeral=True)

        try:
            from_day, to_day = resolve_day_range(int(period), from_day_ago, to_day_ago)
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return

        try:
            async with _PLOT_LOCK:
                image_bytes = await asyncio.to_thread(
                    render_predefined_plot,
                    graph,
                    from_day,
                    to_day,
                    user.id if user is not None else None,
                    top,
                )
        except ValueError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print_error_log(f"modplot: failed to render '{graph}': {exc}")
            await interaction.followup.send(
                "Failed to generate the graph. Check the bot log for details.",
                ephemeral=True,
            )
            return

        bytesio = io.BytesIO(image_bytes)
        bytesio.seek(0)
        file = discord.File(fp=bytesio, filename=f"{graph}.png")
        await interaction.followup.send(file=file, ephemeral=True)


async def setup(bot):
    """Setup function to add this cog to the bot"""
    await bot.add_cog(ModAnalytics(bot))
