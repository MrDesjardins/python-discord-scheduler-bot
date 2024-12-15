"""
Module to gather user activity data and calculate the time spent together
"""

from datetime import date
from typing import Dict, List, Optional
from deps.data_access_data_class import UserInfo
from deps.cache import get_cache
from deps.system_database import database_manager
from deps.tournament_data_class import Tournament, TournamentGame

KEY_TOURNAMENT_GUILD = "tournament_guild"
KEY_TOURNAMENT_GAMES = "tournament_games"


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
                        score,
                        map,
                        timestamp,
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

def block_registration_today_tournament_start(date_to_start:Optional[date]=None) -> None:
    """
    Block registration for a tournament.
    """
    if date_to_start is None:
        date_to_start = date.today().isoformat()  # Get today's date when the function is called

    database_manager.get_cursor().execute(
        """
        UPDATE tournament
        SET has_started = 1
        WHERE date(start_date) = ?;
        """,
        (date_to_start,),
    )
    database_manager.get_conn().commit()

def get_tournaments_starting_today(date_to_start:Optional[date]=None) -> List[Tournament]:
    """
    Get the list of tournaments that are starting today.
    """
    if date_to_start is None:
        date_to_start = date.today().isoformat()  # Get today's date when the function is called

    database_manager.get_cursor().execute(
        """
        SELECT 
            id,
            guild_id,
            name,
            registration_date,
            start_date,
            end_date,
            best_of,
            max_players,
            maps
        FROM tournament
        WHERE date(start_date) = ?;
        """,
        (date_to_start,),
    )

    return [Tournament(*row) for row in database_manager.get_cursor().fetchall()]

def get_people_registered_for_tournament(tournament_id:int) -> List[UserInfo]:
    """
    Get the list of people who registered for a tournament.
    """
    database_manager.get_cursor().execute(
        """
        SELECT user_id, 
              display_name, 
              ubisoft_username_max, 
              ubisoft_username_active, 
              time_zone
        FROM user_tournament
        LEFT JOIN user_info ON user_tournament.user_id = user_info.id
        WHERE tournament_id = ?;
        """,
        (tournament_id,),
    )

    return [UserInfo(*row) for row in database_manager.get_cursor().fetchall()]

def save_tournament_games(games:List[TournamentGame]) -> None:
    """
    Save the tournament games.
    """
    cursor = database_manager.get_cursor()
    for game in games:
        cursor.execute(
            """
            UPDATE tournament_game
            SET user1_id = ?,
                user2_id = ?,
                map = ?
            WHERE id = ?;
            """,
            (game.user1_id, game.user2_id, game.map),
        )

    database_manager.get_conn().commit()