"""Helpers for rendering tournament betting leaderboard messages."""
# pylint: disable=duplicate-code

from typing import List

from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.bet.bet_data_access import (
    data_access_get_all_wallet_for_tournament,
    data_access_get_bet_user_game_waiting_match_complete,
)
from deps.bet.bet_data_class import BetUserGame, BetUserTournament
from deps.tournaments.tournament_data_class import Tournament


async def generate_msg_bet_leaderboard(tournament: Tournament) -> str:
    """Build a leaderboard message ranked by wallet amount for one tournament."""
    if tournament.id is None:
        return ""

    wallets: List[BetUserTournament] = data_access_get_all_wallet_for_tournament(tournament_id=tournament.id)
    open_bets_not_distributed: List[BetUserGame] = data_access_get_bet_user_game_waiting_match_complete(
        tournament.id
    )

    for bet in open_bets_not_distributed:
        wallet = next((w for w in wallets if w.user_id == bet.user_id), None)
        if wallet:
            wallet.amount += bet.amount

    wallets_sorted = sorted(wallets, key=lambda wallet: wallet.amount, reverse=True)
    msg = ""
    rank = 1
    for wallet in wallets_sorted:
        member = await fetch_user_info_by_user_id(wallet.user_id)
        user_display = member.display_name if member else wallet.user_id
        msg += f"{rank} - {user_display} - ${wallet.amount:.2f}\n"
        rank += 1
    return msg.strip()
