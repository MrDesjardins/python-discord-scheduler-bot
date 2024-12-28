"""
Module to gather access to the cached data
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
import base64
import dill as pickle
from deps.system_database import database_manager
from deps.log import print_error_log


def delete_all_tables() -> None:
    """
    Delete all tables
    """
    # print(f"Deleting all tables from database {database_manager.get_database_name()}")
    database_manager.get_cursor().execute("DELETE FROM cache")
    database_manager.get_conn().commit()


def set_value(key: str, value: str, ttl_seconds: Optional[int]) -> None:
    """
    Set a value in the cache
    """
    expiration = (
        None if ttl_seconds is None else (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
    )
    pickled_value = pickle.dumps(value)  # Serialize the value
    encoded_value = base64.b64encode(pickled_value).decode("utf-8")  # Base64 encode it

    try:
        database_manager.get_cursor().execute(
            """
      INSERT OR REPLACE INTO cache(key, value, expiration)
      VALUES (:key, :value, :expiration)
      """,
            {
                "key": key,
                "value": encoded_value,
                "expiration": expiration,
            },
        )
        database_manager.get_conn().commit()
    except Exception as e:
        database_manager.get_conn().rollback()  # Ensure rollback on error
        print_error_log(f"Error setting cache value: {e}")


def clear_expired_cache() -> None:
    """
    Delete all the expired cache
    """
    current_date_time = datetime.now(timezone.utc).isoformat()

    try:
        database_manager.get_cursor().execute(
            """
          DELETE FROM cache
          WHERE expiration <= :current_time
          AND expiration IS NOT NULL
          """,
            {"current_time": current_date_time},
        )
        database_manager.get_conn().commit()
    except Exception as e:
        print_error_log(f"Error expiring cache value: {e}")


def get_value(key: str) -> str:
    """
    Get a value from the cache
    """
    result = (
        database_manager.get_cursor()
        .execute(
            """
    SELECT value
    FROM cache
    WHERE key = :key
    """,
            {"key": key},
        )
        .fetchone()
    )
    if result is None:
        return None

    encoded_value = result[0]  # Get the encoded value
    pickled_value = base64.b64decode(encoded_value)  # Decode the Base64 value
    value = pickle.loads(pickled_value)  # Deserialize the value
    return value


def remove_key(key: str) -> None:
    """
    Remove a key from the cache
    """
    try:
        database_manager.get_cursor().execute(
            """
      DELETE FROM cache
      WHERE key = :key
      """,
            {"key": key},
        )
        database_manager.get_conn().commit()
    except Exception as e:
        database_manager.get_conn().rollback()  # Ensure rollback on error
        print_error_log(f"Error remove key value: {e}")


def remove_key_by_prefix(prefix: str) -> int:
    """
    Remove a key from the cache
    """
    try:
        database_manager.get_cursor().execute(
            """
      DELETE FROM cache
      WHERE key LIKE :prefix
      """,
            {"prefix": f"{prefix}%"},
        )
        row_count = database_manager.get_cursor().rowcount  # Get the number of affected rows
        database_manager.get_conn().commit()
        return row_count
    except Exception as e:
        database_manager.get_conn().rollback()  # Ensure rollback on error
        print_error_log(f"Error remove by prefix key value: {e}")
        return 0
