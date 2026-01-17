"""
Analytics Settings Data Access Module

This module handles user profile settings and preferences including
timezone, Ubisoft usernames, R6 Tracker IDs, and MMR values.

Functions:
- data_access_set_usertimezone: Set user's timezone preference
- data_access_set_ubisoft_username_max: Set user's max MMR Ubisoft username
- data_access_set_ubisoft_username_active: Set user's active Ubisoft username
- data_access_set_max_mmr: Set user's maximum MMR value
- data_access_set_r6_tracker_id: Set user's R6 Tracker ID
- upsert_user_info: Insert or update complete user profile
- get_active_user_info: Get profiles of users active in time range
"""

from datetime import datetime
from typing import Union

from deps.analytic_constants import USER_INFO_SELECT_FIELD, KEY_USER_INFO
from deps.data_access_data_class import UserInfo
from deps.system_database import database_manager
from deps.analytic_activity_data_access import (
    fetch_user_infos_with_activity,
    fetch_user_info_by_user_id_list,
)


def data_access_set_usertimezone(user_id: int, timezone: str) -> None:
    """
    Set the timezone for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET time_zone = :timezone
      WHERE id = :user_id
    """,
        {"user_id": user_id, "timezone": timezone},
    )
    database_manager.get_conn().commit()


def data_access_set_ubisoft_username_max(user_id: int, username: str) -> None:
    """
    Set the timezone for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET ubisoft_username_max = :name
      WHERE id = :user_id
    """,
        {"user_id": user_id, "name": username},
    )
    database_manager.get_conn().commit()


def data_access_set_ubisoft_username_active(user_id: int, username: str) -> None:
    """
    Set the active user name and reset the R6 Tracker ID which will be set back from the active
    user name once the user play
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET ubisoft_username_active = :name,
      r6_tracker_active_id = NULL
      WHERE id = :user_id
    """,
        {"user_id": user_id, "name": username},
    )
    database_manager.get_conn().commit()


def data_access_set_max_mmr(user_id: int, max_mmr: int) -> None:
    """
    Set the max mmr
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET max_mmr = :max_mmr
      WHERE id = :user_id
    """,
        {"user_id": user_id, "max_mmr": max_mmr},
    )
    database_manager.get_conn().commit()


def data_access_set_r6_tracker_id(user_id: int, r6_tracker_active_id: str) -> None:
    """
    Set the r6_tracker_active_id for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET r6_tracker_active_id = :r6_tracker_active_id
      WHERE id = :user_id
    """,
        {"user_id": user_id, "r6_tracker_active_id": r6_tracker_active_id},
    )
    database_manager.get_conn().commit()


def upsert_user_info(
    user_id: int,
    display_name: str,
    user_max_account_name: str,
    user_active_account: str,
    r6_tracker_active_id: Union[str, None],
    user_timezone: str,
    max_mmr: int,
) -> None:
    """
    Insert or Update the user info
    """
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_info(id, display_name, ubisoft_username_max, ubisoft_username_active, r6_tracker_active_id, time_zone, max_mmr)
      VALUES(:user_id, :user_display_name, :user_max_account_name, :user_active_account, :r6_tracker_active_id, :user_timezone, :max_mmr)
      ON CONFLICT(id) DO UPDATE SET
        display_name = :user_display_name,
        ubisoft_username_max = :user_max_account_name,
        ubisoft_username_active = :user_active_account,
        r6_tracker_active_id = :r6_tracker_active_id,
        time_zone = :user_timezone,
        max_mmr = :max_mmr
      WHERE id = :user_id;
    """,
        {
            "user_id": user_id,
            "user_display_name": display_name,
            "user_max_account_name": user_max_account_name,
            "user_active_account": user_active_account,
            "r6_tracker_active_id": r6_tracker_active_id,
            "user_timezone": user_timezone,
            "max_mmr": max_mmr,
        },
    )

    database_manager.get_conn().commit()


def get_active_user_info(from_time: datetime, to_time: datetime) -> list[UserInfo]:
    """
    Get the list of UserInfo of active user
    """
    # Get the list of user who were active
    user_ids = fetch_user_infos_with_activity(from_time, to_time)

    # Get the user info to get the ubisoft name
    user_infos = fetch_user_info_by_user_id_list(user_ids)

    # Remove user without active or max account
    return [
        user_info for user_info in user_infos if user_info is not None and user_info.ubisoft_username_active is not None
    ]
