"""Contains the dataclasses for the analytic models"""

from dataclasses import dataclass
from deps.data_access_data_class import UserInfo


@dataclass
class UserInfoWithCount:
    """User info with a count"""

    user: UserInfo
    count: int


@dataclass
class UserOperatorCount:
    """User info about the operator with a count"""

    user: str  # Display name
    operator_name: str
    count: int


@dataclass
class UserMapStats:
    """One user's ranked record and most-played operators on a single map."""

    matches: int
    wins: int
    top_operators: list[tuple[str, int]]

    @property
    def win_rate(self) -> float:
        """Win rate in percent (0 when the user never played the map)."""
        return self.wins * 100 / self.matches if self.matches else 0.0
