"""
Function to calculate the gain and lost of bets
"""

from datetime import datetime, timezone
from typing import List, Optional
from deps.analytic_data_access import fetch_user_info_by_user_id
from deps.bet.bet_data_access import (
    data_access_create_bet_game,
    data_access_create_bet_user_game,
    data_access_create_bet_user_wallet_for_tournament,
    data_access_fetch_bet_games_by_tournament_id,
    data_access_get_all_wallet_for_tournament,
    data_access_get_bet_user_game_ready_for_distribution,
    data_access_get_bet_user_wallet_for_tournament,
    data_access_update_bet_user_tournament,
    data_access_update_bet_user_game_distribution_completed,
    data_access_update_bet_game_distribution_completed,
    data_access_insert_bet_ledger_entry,
)
from deps.bet.bet_data_class import BetGame, BetLedgerEntry, BetUserGame, BetUserTournament
from deps.tournament_data_class import Tournament, TournamentGame
from deps.tournament_data_access import fetch_tournament_games_by_tournament_id
from deps.data_access_data_class import UserInfo
from deps.system_database import database_manager

DEFAULT_MONEY = 1000


def get_total_pool_for_game(
    tournament_game: TournamentGame, bet_on_games: List[BetUserGame]
) -> tuple[float, float, float]:
    """
    Get the total amount bet on a specific game and also the amount bet on each user (which sum to the total)
    """
    total_amount_bet_on_user_1 = 0
    total_amount_bet_on_user_2 = 0
    for bet in bet_on_games:
        if bet.user_id_bet_placed == tournament_game.user1_id:
            total_amount_bet_on_user_1 += bet.amount
        elif bet.user_id_bet_placed == tournament_game.user2_id:
            total_amount_bet_on_user_2 += bet.amount
    total_amount_bet = total_amount_bet_on_user_1 + total_amount_bet_on_user_2
    return total_amount_bet, total_amount_bet_on_user_1, total_amount_bet_on_user_2


# def calculate_gain_lost_for_open_bet_game(
#     tournament_game: TournamentGame, bet_on_games: List[BetUserGame]
# ) -> List[BetLedgerEntry]:
#     """
#     Calculate the distribution of gains and losses for a game
#     Called when:
#         This is called at the end of a game (we know the winner)
#     Algo use a shared pool
#     """
#     bet_on_games_not_distributed = [bet for bet in bet_on_games if not bet.bet_distributed]

#     total_amount_bet, total_amount_bet_on_user_1, total_amount_bet_on_user_2 = get_total_pool_for_game(
#         tournament_game, bet_on_games
#     )
#     houst_cut = 0  # 0.05
#     net_pool = total_amount_bet * (1 - houst_cut)
#     winner_id = tournament_game.user_winner_id
#     if winner_id is None:
#         return []
#     if winner_id == tournament_game.user1_id:
#         multiplier = net_pool / total_amount_bet_on_user_1
#     else:
#         multiplier = net_pool / total_amount_bet_on_user_2
#     winning_distributions: List[BetLedgerEntry] = []
#     for bet in bet_on_games_not_distributed:
#         if bet.user_id_bet_placed == winner_id:
#             winning_amount = bet.amount * multiplier
#         else:
#             winning_amount = 0
#         winning_distributions.append(
#             BetLedgerEntry(
#                 id=0,
#                 tournament_id=tournament_game.tournament_id,
#                 game_id=bet.game_id,
#                 user_id=bet.user_id,
#                 amount=winning_amount,
#             )
#         )
#     return winning_distributions


def distribute_gain_on_recent_ended_game(tournament_id: int) -> None:
    """
    Get all the TournamentGame that are completed (winner is known) with their BetUserGame list
    and calculate the gain and lost for each. Close the BetUserGame, the BetGame and update the
    wallet (bet_user_tournament)
    """
    bet_user_games: List[BetUserGame] = data_access_get_bet_user_game_ready_for_distribution(tournament_id)
    tournament_games: TournamentGame = fetch_tournament_games_by_tournament_id(tournament_id)

    for tournament_game in tournament_games:
        if tournament_game.user_winner_id is None:
            continue
        bets = [bet for bet in bet_user_games if bet.tournament_id == tournament_id]
        winning_distributions = calculate_gain_lost_for_open_bet_game(tournament_game, bets)

        with database_manager.data_access_transaction():
            for winning_distribution in winning_distributions:
                if winning_distribution.amount > 0:
                    wallet = get_bet_user_wallet_for_tournament(tournament_id, winning_distribution.user_id)
                    wallet.amount += winning_distribution.amount
                    data_access_update_bet_user_tournament(wallet.id, wallet.amount)
                data_access_insert_bet_ledger_entry(winning_distribution)
            for bet_user_game in bets:
                data_access_update_bet_user_game_distribution_completed(bet_user_game.id)
                data_access_update_bet_game_distribution_completed(bet_user_game.bet_game_id)
        # Auto-Commit after the with if no exception


def calculate_gain_lost_for_open_bet_game(
    tournament_game: TournamentGame, bet_on_games: List[BetUserGame], houst_cut=0
) -> List[BetLedgerEntry]:
    """
    Calculate the distribution of gains and losses for a game
    Called when:
        This is called at the end of a game (we know the winner)
    Algo use a conventional odd and support dynamic odd
    The algo uses the Overround.
    Vigorish would be adjusted_odd = fair_odd * (1 - houst_cut)
    """
    bet_on_games_not_distributed = [bet for bet in bet_on_games if not bet.bet_distributed]

    winner_id = tournament_game.user_winner_id
    if winner_id is None:
        return []

    winning_distributions: List[BetLedgerEntry] = []
    for bet in bet_on_games_not_distributed:
        if bet.user_id_bet_placed == winner_id:
            fair_odd = 1 / bet.probability_user_win_when_bet_placed
            adjusted_odd = fair_odd / (1 + houst_cut)
            winning_amount = bet.amount * adjusted_odd
        else:
            winning_amount = 0
        winning_distributions.append(
            BetLedgerEntry(
                id=0,
                tournament_id=tournament_game.tournament_id,
                game_id=tournament_game.id,
                bet_game_id=bet.bet_game_id,
                bet_user_game_id=bet.id,
                user_id=bet.user_id,
                amount=winning_amount,
            )
        )
    return winning_distributions


def get_bet_user_wallet_for_tournament(tournament_id: int, user_id: int) -> BetUserTournament:
    """
    Get the wallet of a user for a specific tournament
    """
    wallet: Optional[BetUserTournament] = data_access_get_bet_user_wallet_for_tournament(tournament_id, user_id)

    if wallet is None:
        data_access_create_bet_user_wallet_for_tournament(tournament_id, user_id, DEFAULT_MONEY)
        wallet = data_access_get_bet_user_wallet_for_tournament(tournament_id, user_id)
    return wallet


async def system_generate_game_odd(tournament_id: int) -> None:
    """
    Generate the odd for all available games of a tournament
    Available games are games that have not started yet

    This function should be used:
        1) When a new tournament is created
        2) When a new game is created (two reports are created)

    This function is idempotent
    """
    # 1 Get the tournament games
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

    # 2 Get the current bet_game for the tournament
    bet_games: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)

    # 3 Get the tournament games without bet_game
    # 3.1 Create a dictionary of the ids of the bet_game
    bet_game_ids = {game.game_id for game in bet_games}

    # 3.2 Get the games without bet_game
    games_without_bet_game = [game for game in tournament_games if game.id not in bet_game_ids]

    # 3.3 Remove from the game without bet game the one that have already a winner and those without two users
    games_without_bet_game = [
        game
        for game in games_without_bet_game
        if game.user1_id is not None and game.user2_id is not None and game.user_winner_id is None
    ]
    # 4 Generate the odd for the games without bet_game
    for game in games_without_bet_game:
        # 4.1 Get the wallet of the two users
        user_info1: Optional[UserInfo] = await fetch_user_info_by_user_id(game.user1_id)
        user_info2: Optional[UserInfo] = await fetch_user_info_by_user_id(game.user2_id)
        if user_info1 is None or user_info2 is None:
            odd_user1 = 0.5
            odd_user2 = 0.5
        else:
            # Here find a way like getting the user MMR
            odd_user1 = 0.5
            odd_user2 = 0.5
        # 4.3 Insert the generated odd into the database
        data_access_create_bet_game(tournament_id, game.id, odd_user1, odd_user2)


def get_open_bet_games_for_tournament(tournament_id: int) -> List[TournamentGame]:
    """
    Get all the possible game where bet_game are legit to receive bets
    """
    # 1 Get the tournament games
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

    # 2 Get the current bet_game for the tournament
    bet_games: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)

    # 3 Get the tournament games without bet_game
    # 3.1 Create a dictionary of the ids of the bet_game
    bet_game_ids = {game.game_id for game in bet_games}

    # 3.2 Get the games that have 2 userrs but without winner yet
    games_without_bet_game = [
        game
        for game in tournament_games
        if game.id in bet_game_ids
        and game.user1_id is not None
        and game.user2_id is not None
        and game.user_winner_id is None
    ]
    return games_without_bet_game


def place_bet_for_game(
    tournament_id: int, bet_game_id: int, user_who_is_betting_id: int, amount: float, user_id_bet_placed_on: int
) -> None:
    """
    Function to call when a user place a bet on a bet_game (not a match)
    """
    # 1 Get the bet game
    bet_games_tournament: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)
    bet_games: List[BetGame] = [game for game in bet_games_tournament if game.id == bet_game_id]
    if len(bet_games) == 0:
        raise ValueError("The Bet on this game does not exist")
    bet_game = bet_games[0]
    game_id = bet_game.game_id
    games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    game: List[TournamentGame] = [game for game in games if game.id == game_id]
    if len(game) == 0:
        raise ValueError("The game does not exist")
    game: TournamentGame = game[0]
    if game.user_winner_id is not None:
        raise ValueError("The game is already finished")
    # 2 Get the wallet of the user
    wallet: BetUserTournament = get_bet_user_wallet_for_tournament(tournament_id, user_who_is_betting_id)
    if wallet.amount < amount:
        raise ValueError("The user does not have enough money")

    # 3 Calculate the probability when the bet is placed
    if user_id_bet_placed_on == game.user1_id:
        probability = bet_game.probability_user_1_win
    else:
        probability = bet_game.probability_user_2_win

    # 4 Insert the bet into the database
    current_date = datetime.now(timezone.utc)
    data_access_create_bet_user_game(
        tournament_id, bet_game.id, user_who_is_betting_id, amount, user_id_bet_placed_on, current_date, probability
    )
    wallet.amount -= amount
    data_access_update_bet_user_tournament(wallet.id, wallet.amount, True)


async def generate_msg_bet_leaderboard(tournament: Tournament) -> str:
    """
    Get a message that is a list of all the user who betted on a tournament in order of larger amountin their wallet
    """
    wallets: List[BetUserTournament] = data_access_get_all_wallet_for_tournament(tournament_id=tournament.id)
    wallets_sorted = sorted(wallets, key=lambda x: x.amount, reverse=True)
    msg = ""
    rank = 1
    for wallet in wallets_sorted:
        member1 = await fetch_user_info_by_user_id(wallet.user_id)
        user1_display = member1.display_name if member1 else wallet.user1_id

        msg += f"{rank} - {user1_display} - ${wallet.amount:.2f}\n"
        rank += 1
    return msg.strip()
