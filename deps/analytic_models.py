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
