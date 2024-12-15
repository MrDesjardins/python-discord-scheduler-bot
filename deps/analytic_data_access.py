"""
Module to gather user activity data and calculate the time spent together
"""

from datetime import date
from typing import Dict, List, Optional
from deps.data_access_data_class import UserInfo, UserActivity
from deps.analytic_database import database_manager
from deps.analytic_functions import compute_users_weights
from deps.cache import (
    get_cache,
)
from deps.tournament_data_class import Tournament, TournamentGame

KEY_USER_INFO = "user_info"
KEY_TOURNAMENT_GUILD = "tournament_guild"
KEY_TOURNAMENT_GAMES = "tournament_games"


def delete_all_tables() -> None:
    """
    Delete all tables
    """
    print(f"Deleting all tables from database {database_manager.get_database_name()}")
    database_manager.get_cursor().execute("DELETE FROM user_info")
    database_manager.get_cursor().execute("DELETE FROM user_activity")
    database_manager.get_cursor().execute("DELETE FROM user_weights")
    database_manager.get_conn().commit()


def delete_all_user_weights():
    """
    Erase everything to start the calculation from scratch
    """
    database_manager.get_cursor().execute("DELETE FROM user_weights")
    database_manager.get_conn().commit()


def insert_user_activity(user_id, user_display_name, channel_id, guild_id, event, time) -> None:
    """
    Log a user activity in the database
    """
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_info(id, display_name)
      VALUES(:user_id, :user_display_name)
      ON CONFLICT(id) DO UPDATE SET
        display_name = :user_display_name
      WHERE id = :user_id;
    """,
        {"user_id": user_id, "user_display_name": user_display_name},
    )
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp)
    VALUES (?, ?, ?, ?, ?)
    """,
        (user_id, channel_id, guild_id, event, time),
    )
    database_manager.get_conn().commit()


def fetch_user_info() -> Dict[int, UserInfo]:
    """
    Fetch all user names from the user_info table
    """
    database_manager.get_cursor().execute(
        "SELECT id, display_name, ubisoft_username_max, ubisoft_username_active, time_zone FROM user_info"
    )
    return {row[0]: UserInfo(*row) for row in database_manager.get_cursor().fetchall()}


async def fetch_user_info_by_user_id(user_id: int) -> Optional[UserInfo]:
    """
    Fetch a user name from the user_info table
    """

    def fetch_from_db():
        result = (
            database_manager.get_cursor()
            .execute(
                "SELECT id, display_name, ubisoft_username_max, ubisoft_username_active, time_zone FROM user_info WHERE id = ?",
                (user_id,),
            )
            .fetchone()
        )
        if result is not None:
            return UserInfo(*result)
        else:
            # Handle the case where no user was found, e.g., return None or raise an exception
            return None  # Or raise an appropriate exception

    return await get_cache(True, f"{KEY_USER_INFO}:{user_id}", fetch_from_db)


def fetch_user_info_by_user_id_list(user_id_list: list[int]) -> List[Optional[UserInfo]]:
    """
    Return the list of user info for the given list of user ids.
    If not user info is found, return None
    """
    list_ids = ",".join("?" for _ in user_id_list)
    database_manager.get_cursor().execute(
        f"""
        SELECT id, display_name, ubisoft_username_max, ubisoft_username_active, time_zone 
        FROM user_info WHERE id IN ({list_ids})
        """,
        user_id_list,  # Pass user_id_list as the parameter values for the ? placeholders
    )
    # Fetch all results and store them in a dictionary by user id
    result = {user.id: user for user in (UserInfo(*row) for row in database_manager.get_cursor().fetchall())}

    result_with_none = []
    for user_id in user_id_list:
        user_info = result.get(user_id)
        if user_info is None:
            result_with_none.append(None)
        else:
            result_with_none.append(user_info)
    return result_with_none


def fetch_user_activities(from_day: int = 3600, to_day: int = 0) -> list[UserActivity]:
    """
    Fetch all connect and disconnect events from the user_activity table
    """
    database_manager.get_cursor().execute(
        """
        SELECT user_id, channel_id, event, timestamp, guild_id
        FROM user_activity
        WHERE timestamp >= datetime('now', ? ) AND timestamp <= datetime('now', ?)
        ORDER BY timestamp
        """,
        (f"-{from_day} days", f"-{to_day} days"),
    )
    # Convert the result to a list of UserActivity objects
    return [UserActivity(*row) for row in database_manager.get_cursor().fetchall()]


def calculate_time_spent_from_db(from_day: int, to_day: int) -> None:
    """
    Function to calculate time spent together and insert weights
    """
    delete_all_user_weights()

    # Fetch all user activity data, ordered by room and timestamp
    activity_data = fetch_user_activities(from_day, to_day)

    user_weights = compute_users_weights(activity_data)

    # Insert accumulated weights into the user_weights table
    for (user_a, user_b, channel_id), total_weight in user_weights.items():
        database_manager.get_cursor().execute(
            """
        INSERT INTO user_weights (user_a, user_b, channel_id, weight)
        VALUES (?, ?, ?, ?)
        """,
            (user_a, user_b, channel_id, total_weight),
        )
    database_manager.get_conn().commit()


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
    Set the timezone for a user
    """
    database_manager.get_cursor().execute(
        """
    UPDATE user_info
      SET ubisoft_username_active = :name
      WHERE id = :user_id
    """,
        {"user_id": user_id, "name": username},
    )
    database_manager.get_conn().commit()


def upsert_user_info(user_id, display_name, user_max_account_name, user_active_account, user_timezone) -> None:
    """
    Log a user activity in the database
    """
    database_manager.get_cursor().execute(
        """
    INSERT INTO user_info(id, display_name, ubisoft_username_max, ubisoft_username_active, time_zone)
      VALUES(:user_id, :user_display_name, :user_max_account_name, :user_active_account, :user_timezone)
      ON CONFLICT(id) DO UPDATE SET
        display_name = :user_display_name,
        ubisoft_username_max = :user_max_account_name,
        ubisoft_username_active = :user_active_account,
        time_zone = :user_timezone
      WHERE id = :user_id;
    """,
        {
            "user_id": user_id,
            "user_display_name": display_name,
            "user_max_account_name": user_max_account_name,
            "user_active_account": user_active_account,
            "user_timezone": user_timezone,
        },
    )

    database_manager.get_conn().commit()


def data_access_insert_tournament(
    guild_id: int,
    name: str,
    registration_date_start: date,
    start_date: date,
    end_date: date,
    best_of: int,
    max_users: int,
    maps: str,
) -> None:
    """
    Insert a tournament and its associated games in a binary bracket system.

    :param name: Name of the tournament.
    :param registration_date_start: Registration start date.
    :param start_date: Tournament start date.
    :param end_date: Tournament end date.
    :param best_of: Best-of value for games.
    :param max_users: Maximum number of players (must be a power of 2).
    :param database_manager: A database manager object for handling connections and queries.
    """
    if max_users & (max_users - 1) != 0:
        raise ValueError("max_users must be a power of 2 (e.g., 4, 8, 16, ...).")

    # Insert tournament into the tournament table
    cursor = database_manager.get_cursor()
    cursor.execute(
        """
        INSERT INTO tournament (
            guild_id, name, registration_date, start_date, end_date, best_of, max_players, maps
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (guild_id, name, registration_date_start, start_date, end_date, best_of, max_users, maps),
    )
    tournament_id = cursor.lastrowid

    # Helper function to recursively create the binary bracket
    def create_bracket(tournament_id: int, num_games: int) -> List[dict]:
        games = []

        # Initialize a list to keep track of game IDs for the current level
        current_level = []

        # Generate leaf games (final games at the bottom of the bracket)
        for i in range(num_games):
            cursor.execute(
                """
                INSERT INTO tournament_game (
                    tournament_id, next_game1_id, next_game2_id
                ) VALUES (?, NULL, NULL)
                """,
                (tournament_id,),
            )
            game_id = cursor.lastrowid
            current_level.append(game_id)

        # Build the bracket upwards
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                next_level_1 = current_level[i] if i < len(current_level) else None
                next_level_2 = current_level[i + 1] if i + 1 < len(current_level) else None
                cursor.execute(
                    """
                    INSERT INTO tournament_game (
                        tournament_id, next_game1_id, next_game2_id
                    ) VALUES (?, ?, ?)
                    """,
                    (tournament_id, next_level_1, next_level_2),
                )
                game_id = cursor.lastrowid
                next_level.append(game_id)
            current_level = next_level

        return games

    # Calculate the total number of games for the given max_users
    total_games = max_users - 1

    # Create the bracket
    create_bracket(tournament_id, total_games)

    # Commit the transaction
    database_manager.get_conn().commit()


async def fetch_active_tournament_bu_guild(guild_id: int) -> Optional[List[Tournament]]:
    """
    Fetch a user name from the user_info table
    """

    def fetch_from_db():
        result = (
            database_manager.get_cursor()
            .execute(
                """
                SELECT 
                    id,
                    guild_id,
                    name TEXT ,
                    registration_date,
                    start_date,
                    end_date,
                    best_of,
                    max_players,
                    maps TEXT
                FROM tournament
                WHERE guild_id = ? AND registration_date <= datetime('now') AND end_date >= datetime('now')
              """,
                (guild_id,),
            )
            .fetchone()
        )
        if result is not None:
            return Tournament(*result)
        else:
            # Handle the case where no user was found, e.g., return None or raise an exception
            return None  # Or raise an appropriate exception

    return await get_cache(True, f"{KEY_TOURNAMENT_GUILD}:{guild_id}", fetch_from_db, 60)


async def fetch_tournament_games_by_tournament_id(tournament_id: int) -> List[TournamentGame]:
    """
    Fetch a user name from the user_info table
    """

    def fetch_from_db():
        result = (
            database_manager.get_cursor()
            .execute(
                """
                SELECT  id,
                        tournament_id ,
                        user1_id ,
                        user2_id ,
                        user_winner_id,
                        timestamp ,
                        next_game1_id ,
                        next_game2_id ,
              FROM tournament_game WHERE id = ?
              """,
                (tournament_id,),
            )
            .fetchone()
        )
        if result is not None:
            return TournamentGame(*result)
        else:
            # Handle the case where no user was found, e.g., return None or raise an exception
            return []

    return await get_cache(True, f"{KEY_TOURNAMENT_GAMES}:{tournament_id}", fetch_from_db, 60)
