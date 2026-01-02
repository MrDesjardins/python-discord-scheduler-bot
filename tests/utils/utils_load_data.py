"""
Utility functions for loading data in tests
"""

from datetime import datetime, timezone
from deps.analytic_data_access import upsert_user_info


def init_users_database() -> None:
    """Initialize the users in the database for testing"""
    for i in range(1, 20):
        upsert_user_info(
            i, f"User{i}", f"User{i}#000{i}", f"User{i}#000{i}", f"User{i}#000{i}", datetime.now(timezone.utc), 1000 + i
        )
