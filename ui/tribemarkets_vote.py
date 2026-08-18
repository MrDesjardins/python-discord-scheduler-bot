"""Interactive Discord controls for TribeMarkets match predictions."""

from __future__ import annotations

import discord

from deps.log import print_warning_log
from deps.tribemarkets import MatchMarket, TribeMarketsClient, TribeMarketsIntegrationError


class TribeMarketsVoteButton(discord.ui.Button[discord.ui.View]):
    """One outcome button that creates a private, expiring confirmation link."""

    def __init__(self, market: MatchMarket, *, label: str, outcome_id: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            label=label,
            style=style,
            custom_id=f"tribemarkets:vote:{market.market_id}:{outcome_id}",
        )
        self.market = market
        self.outcome_id = outcome_id

    async def callback(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None or interaction.channel_id is None or interaction.message is None:
            await interaction.response.send_message(
                "This prediction button is only available inside the match Discord message.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            response = await TribeMarketsClient().create_vote_intent(
                self.market,
                guild_id=interaction.guild.id,
                channel_id=interaction.channel_id,
                message_id=interaction.message.id,
                interaction_id=interaction.id,
                discord_user_id=interaction.user.id,
                outcome_id=self.outcome_id,
            )
            url = response.get("url")
            if not isinstance(url, str) or not url:
                raise TribeMarketsIntegrationError("TribeMarkets did not return a confirmation URL")
            await interaction.followup.send(
                f"Review and confirm your **{self.label}** prediction privately: {url}\n"
                "The link expires shortly and clicking the button alone does not spend credits.",
                ephemeral=True,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except TribeMarketsIntegrationError as exc:
            print_warning_log(
                "TribeMarkets vote intent unavailable: "
                f"guild={interaction.guild.id} community={self.market.community_id} "
                f"status={exc.status_code or 'unknown'} error={exc}"
            )
            detail = str(exc).strip() or "The TribeMarkets API did not provide an error message."
            # Keep the API's status and sanitized error envelope visible to the
            # member. A generic "market may be closed" message hid actionable
            # integration problems such as a missing guild binding.
            await interaction.followup.send(
                f"I could not create the private confirmation link. {detail[:1500]}",
                ephemeral=True,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print_warning_log(f"TribeMarkets Discord vote button failed: {exc}")
            await interaction.followup.send(
                "Something went wrong creating the private confirmation link. Please try again shortly.",
                ephemeral=True,
            )


class TribeMarketsVoteView(discord.ui.View):
    """Yes/No controls for one binary TribeMarkets market."""

    def __init__(self, market: MatchMarket, *, disabled: bool = False) -> None:
        super().__init__(timeout=None)
        self.add_item(
            TribeMarketsVoteButton(
                market, label="Predict Yes", outcome_id=market.yes_outcome_id, style=discord.ButtonStyle.success
            )
        )
        self.add_item(
            TribeMarketsVoteButton(
                market, label="Predict No", outcome_id=market.no_outcome_id, style=discord.ButtonStyle.danger
            )
        )
        if disabled:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True
