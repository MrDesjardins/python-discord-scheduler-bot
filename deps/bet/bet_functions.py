"""
Function to calculate the gain and lost of bets
"""

from datetime import datetime, timezone
from typing import List, Optional
from deps.analytic_data_access import (
    data_access_fetch_user_full_match_info,
    fetch_user_info_by_user_id,
    data_access_fetch_users_full_match_info,
)
from deps.bet.bet_data_access import (
    data_access_create_bet_game,
    data_access_create_bet_user_game,
    data_access_create_bet_user_wallet_for_tournament,
    data_access_fetch_bet_games_by_tournament_id,
    data_access_get_all_wallet_for_tournament,
    data_access_get_bet_game_ready_to_close,
    data_access_get_bet_ledger_entry_for_tournament,
    data_access_get_bet_user_game_for_tournament,
    data_access_get_bet_user_game_ready_for_distribution,
    data_access_get_bet_user_game_waiting_match_complete,
    data_access_get_bet_user_wallet_for_tournament,
    data_access_update_bet_game_probability,
    data_access_update_bet_user_tournament,
    data_access_update_bet_user_game_distribution_completed,
    data_access_update_bet_game_distribution_completed,
    data_access_insert_bet_ledger_entry,
)
from deps.bet.bet_data_class import BetGame, BetLedgerEntry, BetUserGame, BetUserTournament
from deps.tournaments.tournament_data_class import Tournament, TournamentGame
from deps.tournaments.tournament_data_access import (
    fetch_tournament_by_id,
    fetch_tournament_games_by_tournament_id,
    fetch_tournament_team_members_by_leader,
)
from deps.data_access_data_class import UserInfo
from deps.system_database import database_manager
from deps.log import print_error_log, print_log
from deps.tournaments.tournament_models import TournamentNode

DEFAULT_MONEY = 1000
MIN_BET_AMOUNT = 10
DYNAMIC_ADJUSTMENT_PERCENTAGE = 1.1


def get_total_pool_for_game(
    tournament_game: TournamentGame, bet_on_games: List[BetUserGame]
) -> tuple[float, float, float]:
    """
    Get the total amount bet on a specific game and also the amount bet on each user (which sum to the total)
    """
    total_amount_bet_on_user_1 = 0.0
    total_amount_bet_on_user_2 = 0.0
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
    and calculate the gain and lost for each.
    Goals:
        1) Close the BetUserGame (if some users bet on a game)
        2) Close the BetGame (separated in case no user bet on a game)
        3) Distribute gain in wallet (bet_user_tournament if winner)
    """
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    tournament_games_dict = {tournament_game.id: tournament_game for tournament_game in tournament_games}
    bet_games: List[BetGame] = data_access_get_bet_game_ready_to_close(tournament_id)
    bet_games_dict = {game.id: game for game in bet_games}
    bet_user_games: List[BetUserGame] = data_access_get_bet_user_game_ready_for_distribution(tournament_id)

    # Loop the bet_user_games and calculate the gain and lost
    with database_manager.data_access_transaction():
        # Find the bet_user_games that are ready for distribution
        bet_user_games_ready_for_distribution = []
        for bet_user_game in bet_user_games:
            bet_game = bet_games_dict.get(bet_user_game.bet_game_id, None)
            if bet_game is None:
                print_error_log(
                    f"distribute_gain_on_recent_ended_game: bet_game not found for bet_user_game {bet_user_game.bet_game_id}"
                )
                continue
            tournament_game = tournament_games_dict.get(bet_game.tournament_game_id, None)
            if tournament_game is None:
                print_error_log(
                    f"distribute_gain_on_recent_ended_game: TournamentGame not found for bet_game {bet_game.id}"
                )
                continue
            if tournament_game.user_winner_id is None:
                continue

            bet_user_games_ready_for_distribution.append(bet_user_game)
            # Calculate the gain and lost for the bet_user_games that are ready for distribution ONLY
            winning_distributions = calculate_gain_lost_for_open_bet_game(tournament_game, [bet_user_game])
            # At the moment, winning_distribution is always a list wiht 1 item
            for winning_distribution in winning_distributions:
                if winning_distribution.amount > 0:
                    wallet = get_bet_user_wallet_for_tournament(tournament_id, winning_distribution.user_id)
                    wallet.amount += winning_distribution.amount
                    data_access_update_bet_user_tournament(wallet.id, wallet.amount)
                data_access_insert_bet_ledger_entry(winning_distribution)
        for bet_user_game in bet_user_games_ready_for_distribution:
            data_access_update_bet_user_game_distribution_completed(bet_user_game.id)
        for bet_game in bet_games:
            data_access_update_bet_game_distribution_completed(bet_game.id)
    # Auto-Commit after the with if no exception


def calculate_gain_lost_for_open_bet_game(
    tournament_game: TournamentGame, bet_on_games: List[BetUserGame], houst_cut_fraction=0
) -> List[BetLedgerEntry]:
    """
    Calculate the distribution of gains and losses for a game
    Called when:
        This is called at the end of a game (we know the winner)
    Algo use a conventional odd and support dynamic odd
    The algo uses the Overround.
    Vigorish would be adjusted_odd = fair_odd * (1 - houst_cut)
    """
    if tournament_game.id is None:
        return []
    winner_id = tournament_game.user_winner_id
    if winner_id is None:
        return []

    bet_on_games_not_distributed = [bet for bet in bet_on_games if not bet.bet_distributed]

    winning_distributions: List[BetLedgerEntry] = []
    for bet in bet_on_games_not_distributed:
        if bet.user_id_bet_placed == winner_id:
            fair_odd = 1 / bet.probability_user_win_when_bet_placed
            adjusted_odd = fair_odd / (1 + houst_cut_fraction)
            winning_amount = bet.amount * adjusted_odd
        else:
            winning_amount = 0
        winning_distributions.append(
            BetLedgerEntry(
                id=0,
                tournament_id=tournament_game.tournament_id,
                tournament_game_id=tournament_game.id,
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
    if wallet is None:
        raise ValueError("Error creating wallet")
    return wallet


def get_bet_user_amount_active_bet(tournament_id: int, user_id: int) -> float:
    """
    Get the amount of money a user has bet on active games
    """

    # Get all the active bet for the tournament (not efficient but always limited and allows reusability of the function)
    bet_user_games: List[BetUserGame] = data_access_get_bet_user_game_waiting_match_complete(tournament_id)
    # Filter for the user
    bet_user_games_for_user = [bet for bet in bet_user_games if bet.user_id == user_id]
    total_amount = sum(bet.amount for bet in bet_user_games_for_user)
    return total_amount


async def system_generate_game_odd(tournament_id: int) -> None:
    """
    Generate the odd for all available games of a tournament
    Available games are games that have not started yet

    This function should be used:
        1) When a new tournament is created
        2) When a new game is created (two reports are created)

    This function is idempotent
    """
    # 0 Check if the tournament exists
    tournament: Optional[Tournament] = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        raise ValueError(f"Tournament with id {tournament_id} does not exist")

    # 1 Get the tournament games
    tournament_games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)

    # 2 Get the current bet_game for the tournament
    bet_games: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_id)

    # 3 Get the tournament games without bet_game
    # 3.1 Create a dictionary of the ids of the bet_game
    bet_game_ids = {game.tournament_game_id for game in bet_games}

    # 3.2 Get the games without bet_game that have 2 users but without winner yet
    games_without_bet_game = [
        game
        for game in tournament_games
        if game.id not in bet_game_ids
        and game.user1_id is not None
        and game.user2_id is not None
        and game.user_winner_id is None
    ]

    # 3.3 Remove from the game without bet game the one that have already a winner and those without two users
    games_without_bet_game = [
        game
        for game in games_without_bet_game
        if game.user1_id is not None and game.user2_id is not None and game.user_winner_id is None
    ]
    # 4 Generate the odd for the games without bet_game
    for game in games_without_bet_game:
        if game.id is None:
            continue
        # 4.1 Get the wallet of the two users (these are the leaders in case of a team tournament)
        user_info1: Optional[UserInfo] = (
            await fetch_user_info_by_user_id(game.user1_id) if game.user1_id is not None else None
        )
        user_info2: Optional[UserInfo] = (
            await fetch_user_info_by_user_id(game.user2_id) if game.user2_id is not None else None
        )
        if user_info1 is None or user_info2 is None:
            odd_user1 = 0.5
            odd_user2 = 0.5
        else:
            # Here find a way like getting the user MMR
            if tournament.team_size > 1:
                # If the tournament is a team tournament, we need to get the team members
                team_members = fetch_tournament_team_members_by_leader(tournament_id)
                team1_members: List[int] = team_members.get(game.user1_id, []) if game.user1_id is not None else []
                team2_members: List[int] = team_members.get(game.user2_id, []) if game.user2_id is not None else []
                odd_user1, odd_user2 = define_odds_between_two_teams(
                    [user_info1.id] + team1_members, [user_info2.id] + team2_members
                )
            else:
                # If the tournament is a single player tournament, we can use the user id directly
                odd_user1, odd_user2 = define_odds_between_two_users(user_info1.id, user_info2.id)
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
    bet_game_ids = {game.tournament_game_id for game in bet_games}

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
        raise ValueError("The bet on this game does not exist")
    bet_game: BetGame = bet_games[0]
    tournament_game_id = bet_game.tournament_game_id
    games: List[TournamentGame] = fetch_tournament_games_by_tournament_id(tournament_id)
    game: List[TournamentGame] = [game for game in games if game.id == tournament_game_id]
    if len(game) == 0:
        raise ValueError("The game does not exist")
    single_game: TournamentGame = game[0]
    if single_game.user_winner_id is not None:
        raise ValueError("The game is already finished")

    # 1.5 Check if the user is betting on a game where a member of their team is playing
    tournament = fetch_tournament_by_id(tournament_id)
    if tournament is None:
        raise ValueError("The tournament does not exist")
    if tournament.team_size > 1:
        leader_teammates = fetch_tournament_team_members_by_leader(tournament_id)
        # Loop all key and then all values of each key
        for leader, teammates in leader_teammates.items():
            team_ids = [leader] + teammates
            if user_who_is_betting_id in team_ids and user_id_bet_placed_on in team_ids:
                raise ValueError("The user cannot bet on a game where a member of their team is playing")
    else:
        if single_game.user1_id == user_who_is_betting_id or single_game.user2_id == user_who_is_betting_id:
            raise ValueError("The user cannot bet on a game where he/she is playing")
    if amount < MIN_BET_AMOUNT:
        raise ValueError(f"The minimum amount to bet is ${MIN_BET_AMOUNT}")

    # 2 Get the wallet of the user
    wallet: BetUserTournament = get_bet_user_wallet_for_tournament(tournament_id, user_who_is_betting_id)
    if wallet.amount < amount:
        raise ValueError(
            f"The user does not have enough money. The bet amount is ${amount} but the user has only ${wallet.amount:.2f}"
        )

    # 3 Calculate the probability when the bet is placed
    is_user_1 = user_id_bet_placed_on == single_game.user1_id
    if is_user_1:
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

    try:
        dynamically_adjust_bet_game_odd(bet_game, is_user_1)
        data_access_update_bet_game_probability(bet_game, True)
    except Exception as e:
        print_error_log(f"place_bet_for_game: Error adjusting the odd: {e}")


def dynamically_adjust_bet_game_odd(game: BetGame, reduce_probability_user_1: bool) -> None:
    """Adjust the odd of a bet_game when a user place a bet"""

    if reduce_probability_user_1:
        game.probability_user_1_win *= DYNAMIC_ADJUSTMENT_PERCENTAGE
        game.probability_user_2_win = 1 - game.probability_user_1_win
    else:
        game.probability_user_2_win *= DYNAMIC_ADJUSTMENT_PERCENTAGE
        game.probability_user_1_win = 1 - game.probability_user_2_win


async def generate_msg_bet_leaderboard(tournament: Tournament) -> str:
    """
    Get a message that is a list of all the user who betted on a tournament in order of larger amountin their wallet
    """
    if tournament.id is None:
        return ""
    wallets: List[BetUserTournament] = data_access_get_all_wallet_for_tournament(tournament_id=tournament.id)
    open_bets_not_distributed: List[BetUserGame] = data_access_get_bet_user_game_waiting_match_complete(tournament.id)
    # Get all wallet amount by member
    for bet in open_bets_not_distributed:
        # Find user wallet
        wallet = next((w for w in wallets if w.user_id == bet.user_id), None)
        amount_bet = bet.amount
        if wallet:
            wallet.amount += amount_bet

    wallets_sorted = sorted(wallets, key=lambda x: x.amount, reverse=True)
    msg = ""
    rank = 1
    for wallet in wallets_sorted:
        member1 = await fetch_user_info_by_user_id(wallet.user_id)
        user1_display = member1.display_name if member1 else wallet.user_id

        msg += f"{rank} - {user1_display} - ${wallet.amount:.2f}\n"
        rank += 1
    return msg.strip()


def define_odds_between_two_users(user1_id: int, user2_id: int) -> tuple[float, float]:
    """
    Function to call when a user place a bet on a bet_game (not a match)

    Logic:
    1) Get the stats of the two users
    2) Calculate the average kill count
    3) Calculate the odd for each user by dividing the average kill count by the sum of the two average kill count
    """
    # Here find a way like getting the user MMR
    user_1_stats = data_access_fetch_user_full_match_info(user1_id)
    user_2_stats = data_access_fetch_user_full_match_info(user2_id)

    total_game_1 = len(user_1_stats)
    total_game_2 = len(user_2_stats)

    if total_game_1 == 0 or total_game_2 == 0:
        return 0.5, 0.5

    sum_kill_count_1 = sum([game.kill_count for game in user_1_stats])
    sum_kill_count_2 = sum([game.kill_count for game in user_2_stats])

    avg_kill_count_1 = sum_kill_count_1 / total_game_1 if total_game_1 > 0 else 0
    avg_kill_count_2 = sum_kill_count_2 / total_game_2 if total_game_2 > 0 else 0

    odd_user1 = (
        avg_kill_count_1 / (avg_kill_count_1 + avg_kill_count_2) if avg_kill_count_1 + avg_kill_count_2 > 0 else 0.5
    )
    odd_user2 = 1 - odd_user1

    return odd_user1, odd_user2


def define_odds_between_two_teams(team_1_user_ids: list[int], team_2_user_ids: list[int]) -> tuple[float, float]:
    """
    Function to call when a user place a bet on a bet_game to calculate the odds between two teams

    Logic:
    1) Get the stats of the two list of users
    2) Calculate the average kill count
    3) Calculate the odd for each team by dividing the average kill count by the sum of the two average kill count
    """
    # Get all match info for the two teams
    team_1_stats = data_access_fetch_users_full_match_info(team_1_user_ids)
    team_2_stats = data_access_fetch_users_full_match_info(team_2_user_ids)

    total_game_1 = len(team_1_stats)
    total_game_2 = len(team_2_stats)

    if total_game_1 == 0 or total_game_2 == 0:
        return 0.5, 0.5

    sum_kill_count_1 = sum([game.kill_count for game in team_1_stats])
    sum_kill_count_2 = sum([game.kill_count for game in team_2_stats])

    avg_kill_count_1 = sum_kill_count_1 / total_game_1 if total_game_1 > 0 else 0
    avg_kill_count_2 = sum_kill_count_2 / total_game_2 if total_game_2 > 0 else 0

    odd_team1 = (
        avg_kill_count_1 / (avg_kill_count_1 + avg_kill_count_2) if avg_kill_count_1 + avg_kill_count_2 > 0 else 0.5
    )
    odd_team2 = 1 - odd_team1

    return odd_team1, odd_team2


async def generate_msg_bet_game(tournament_game: TournamentNode) -> str:
    """Generate a message that show who won and lost their bet"""
    all_bet_game: List[BetGame] = data_access_fetch_bet_games_by_tournament_id(tournament_game.tournament_id)
    bet_game_for_tournament_game: List[BetGame] = [
        bet for bet in all_bet_game if bet.tournament_game_id == tournament_game.id
    ]
    if len(bet_game_for_tournament_game) != 1:
        print_error_log(f"generate_msg_bet_game: BetGame not found for tournament_game {tournament_game.id}. Skipping.")
        return ""
    bet_game = bet_game_for_tournament_game[0]
    print_log(
        f"generate_msg_bet_game: bet_game.id {bet_game.id} and tournament_game.id = {tournament_game.id} found for tournament_game {tournament_game.id}"
    )
    all_bet_user_game: List[BetUserGame] = data_access_get_bet_user_game_for_tournament(tournament_game.tournament_id)
    print_log(f"generate_msg_bet_game: all_bet_user_game count = {len(all_bet_user_game)}")
    all_bet_user_game_dict = {bet.id: bet for bet in all_bet_user_game}

    all_ledger_entry: List[BetLedgerEntry] = data_access_get_bet_ledger_entry_for_tournament(
        tournament_game.tournament_id
    )
    ledger_for_bet_game = [entry for entry in all_ledger_entry if entry.bet_game_id == bet_game.id]

    print_log(
        f"generate_msg_bet_game: all_ledger_entry count = {len(all_ledger_entry)} but for the bet_game.id = {bet_game.id} there is only ledger_for_bet_game {len(ledger_for_bet_game)}"
    )
    msg = ""
    for ledger_entry in ledger_for_bet_game:
        member1 = await fetch_user_info_by_user_id(ledger_entry.user_id)
        user1_display = member1.display_name if member1 else ledger_entry.user_id
        bet_user_game = all_bet_user_game_dict.get(ledger_entry.bet_user_game_id, None)
        if bet_user_game is None:
            print_error_log(
                f"generate_msg_bet_game: BetUserGame not found for ledger_entry {ledger_entry.id}. Skipping."
            )
            continue
        if ledger_entry.amount == 0:
            msg += f"📉 {user1_display} bet ${bet_user_game.amount:.2f} and loss it all\n"
        else:
            gain_in_percent = (ledger_entry.amount - bet_user_game.amount) / bet_user_game.amount * 100
            msg += f"📈 {user1_display} bet ${bet_user_game.amount:.2f} and won ${ledger_entry.amount:.2f} (+{gain_in_percent:.2f}%)\n"
    return msg.strip()
