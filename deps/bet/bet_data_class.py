""" Model for the betting system"""

import dataclasses
import datetime

from deps.functions import convert_to_datetime


def moneyline_odd(prob: float) -> float:
    """
    Return the moneyline odd for a given probability
    """
    if prob < 0.5:
        return 100 / prob
    else:
        return -1 * ((100 * prob) / (1 - prob))


@dataclasses.dataclass
class BetUserTournament:
    """Represent the user wallet for a specific tournament"""

    id: int
    tournament_id: int
    user_id: int
    amount: float

    @staticmethod
    def from_db_row(row):
        """Create a BetUserTournament object from a database row"""
        return BetUserTournament(
            id=row[0],
            tournament_id=row[1],
            user_id=row[2],
            amount=row[3],
        )


@dataclasses.dataclass
class BetGame:
    """Represent the probability. Calculated once the two users are determined, before they play"""

    id: int
    tournament_id: int
    game_id: int
    probability_user_1_win: float
    probability_user_2_win: float
    bet_distributed: bool

    @staticmethod
    def from_db_row(row):
        """Create a BetUserGame object from a database row"""
        return BetGame(
            id=row[0],
            tournament_id=row[1],
            game_id=row[2],
            probability_user_1_win=row[3],
            probability_user_2_win=row[4],
            bet_distributed=bool(row[5]),
        )

    def odd_user_1(self):
        """Return the odd for user 1"""
        return 1 / self.probability_user_1_win

    def moneyline_odd_user_1(self):
        """Return the moneyline odd for user 1"""
        prob = self.probability_user_1_win
        return moneyline_odd(prob)

    def odd_user_2(self):
        """Return the odd for user 2"""
        return 1 / self.probability_user_2_win

    def moneyline_odd_user_2(self):
        """Return the moneyline odd for user 1"""
        prob = self.probability_user_2_win
        return moneyline_odd(prob)


@dataclasses.dataclass
class BetUserGame:
    """Represent one bet"""

    id: int
    tournament_id: int
    bet_game_id: int
    user_id: int
    amount: float
    user_id_bet_placed: int
    time_bet_placed: datetime
    """
    The probability is persisted in case in the future we have dynamic odds
    and we want to know the odds at the time of the bet
    """
    probability_user_win_when_bet_placed: float
    bet_distributed: bool

    @staticmethod
    def from_db_row(row):
        """Create a BetUserGame object from a database row"""
        return BetUserGame(
            id=row[0],
            tournament_id=row[1],
            bet_game_id=row[2],
            user_id=row[3],
            amount=row[4],
            user_id_bet_placed=row[5],
            time_bet_placed=convert_to_datetime(row[6]),
            probability_user_win_when_bet_placed=row[7],
            bet_distributed=bool(row[8]),
        )


@dataclasses.dataclass
class BetLedgerEntry:
    """Represent the amount distributed to the winners/loser of a bet"""

    id: int
    tournament_id: int
    game_id: int
    bet_game_id: int
    bet_user_game_id: int
    user_id: int
    amount: float

    @staticmethod
    def from_db_row(row):
        """Create a BetUserGame object from a database row"""
        return BetLedgerEntry(
            id=row[0],
            tournament_id=row[1],
            game_id=row[2],
            bet_game_id=row[3],
            bet_user_game_id=row[4],
            user_id=row[5],
            amount=row[6],
        )
