"""
Module to gather user activity data and calculate the time spent together
"""

from datetime import datetime, timezone
import math
from typing import List, Optional
from deps.data_access_data_class import UserInfo
from deps.system_database import database_manager
from deps.tournament_data_class import Tournament, TournamentGame

KEY_TOURNAMENT_GUILD = "tournament_guild"
KEY_TOURNAMENT_GAMES = "tournament_games"

SELECT_TOURNAMENT = """
    tournament.id,
    tournament.guild_id,
    tournament.name,
    tournament.registration_date,
    tournament.start_date,
    tournament.end_date,
    tournament.best_of,
    tournament.max_players,
    tournament.maps,
    tournament.has_started
    """


def delete_all_tournament_tables() -> None:
    """
    Delete all tables related to tournament
    """
    # print(f"Deleting all tables from database {database_manager.get_database_name()}")
    database_manager.get_cursor().execute("DELETE FROM user_tournament;")
    database_manager.get_cursor().execute("DELETE FROM tournament_game;")
    database_manager.get_cursor().execute("DELETE FROM tournament;")
    database_manager.get_conn().commit()


def data_access_insert_tournament(
    guild_id: int,
    name: str,
    registration_date_start: datetime,
    start_date: datetime,
    end_date: datetime,
    best_of: int,
    max_users: int,
    maps: str,
) -> int:
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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (guild_id, name, registration_date_start, start_date, end_date, best_of, max_users, maps),
    )
    tournament_id = cursor.lastrowid

    # Commit the transaction
    database_manager.get_conn().commit()

    return tournament_id


def data_access_create_bracket(tournament_id: int, total_players: int) -> None:
    """
    Create the games to be part of the tournament brackets
    """
    # Initialize a list to keep track of game IDs for the current level
    current_level = []

    cursor = database_manager.get_cursor()

    # Create only if not already created
    cursor.execute(
        """
        SELECT 1 FROM tournament_game WHERE tournament_id = ?;
    """,
        (tournament_id,),
    )
    if cursor.fetchone() is not None:
        return

    leaf_game_count = math.ceil(total_players / 2)
    # Generate leaf games (starting games at the bottom of the bracket)
    for i in range(leaf_game_count):
        cursor.execute(
            """
            INSERT INTO tournament_game (
                tournament_id, next_game1_id, next_game2_id
            ) VALUES (?, NULL, NULL);
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
                ) VALUES (?, ?, ?);
                """,
                (tournament_id, next_level_1, next_level_2),
            )
            game_id = cursor.lastrowid
            next_level.append(game_id)
        current_level = next_level

    # Commit the transaction
    database_manager.get_conn().commit()


def fetch_tournament_start_today(guild_id: int) -> List[Tournament]:
    """Fetch all tournament that are not over that the user are registered"""
    current_time = datetime.now(timezone.utc)
    query = f"""
        SELECT 
        {SELECT_TOURNAMENT},
        0 as current_user_count
        FROM tournament
        WHERE tournament.guild_id = :guild_id
        AND date(tournament.start_date) == date(:current_time);
        """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"guild_id": guild_id, "current_time": current_time},
        )
        .fetchall()
    )
    return [Tournament.from_db_row(row) for row in result]


def fetch_tournament_open_registration(guild_id: int) -> List[Tournament]:
    """
    Fetch all tournament for a guild where the registration is still open
    and that the tournament has not started yet with open space and
    that the amount of player is not reached the maximum
    """
    current_time = datetime.now(timezone.utc)
    query = f"""
                SELECT 
                    {SELECT_TOURNAMENT},
                    count(user_tournament.id) as current_user_count
                FROM tournament
                LEFT JOIN
                    user_tournament
                ON
                    tournament.id = user_tournament.tournament_id
                WHERE tournament.guild_id = :guild_id
                    AND date(tournament.start_date) > date(:current_time)
                    AND date(tournament.registration_date) <= date(:current_time)
                GROUP BY tournament.id
                HAVING
                    tournament.max_players > current_user_count;
                """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"guild_id": guild_id, "current_time": current_time},
        )
        .fetchall()
    )
    return [Tournament.from_db_row(row) for row in result]


def fetch_tournament_active_to_interact_for_user(guild_id: int, user_id: int) -> List[Tournament]:
    """Fetch all tournament that are not over that the user are registered"""
    current_time = datetime.now(timezone.utc)
    query = f"""
                SELECT 
                    {SELECT_TOURNAMENT},
                    0 as current_user_count
                FROM tournament
                INNER JOIN
                    user_tournament
                ON
                    tournament.id = user_tournament.tournament_id
                    AND user_tournament.user_id = :user_id
                WHERE tournament.guild_id = :guild_id
                    AND date(tournament.end_date) >= date(:current_time)
                    AND date(tournament.start_date) <= date(:current_time);
                """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"user_id": user_id, "guild_id": guild_id, "current_time": current_time},
        )
        .fetchall()
    )
    return [Tournament.from_db_row(row) for row in result]


def fetch_tournament_not_completed_for_user(guild_id: int, user_id: int) -> List[Tournament]:
    """Fetch all tournament that are not over that the user are registered"""
    current_time = datetime.now(timezone.utc)
    query = f"""
                SELECT 
                    {SELECT_TOURNAMENT},
                    0 as current_user_count
                FROM tournament
                INNER JOIN
                    user_tournament
                ON
                    tournament.id = user_tournament.tournament_id
                    AND user_tournament.user_id = :user_id
                WHERE tournament.guild_id = :guild_id
                    AND date(tournament.end_date) >= date(:current_time);
                """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"user_id": user_id, "guild_id": guild_id, "current_time": current_time},
        )
        .fetchall()
    )
    return [Tournament.from_db_row(row) for row in result]


def fetch_tournament_by_guild_user_can_register(guild_id: int, user_id: int) -> List[Tournament]:
    """
    Fetch all tournements that we can register to for a guild and a specific user
    """
    current_time = datetime.now(timezone.utc)
    query = f"""
            SELECT 
                {SELECT_TOURNAMENT},
                0 as current_user_count
            FROM tournament
            WHERE tournament.guild_id = :guild_id
                AND date(tournament.registration_date) <= date(:current_time)
                AND date(tournament.start_date) > date(:current_time)
                AND NOT EXISTS (
                    SELECT 1 
                    FROM user_tournament 
                    WHERE user_tournament.tournament_id = tournament.id 
                    AND user_tournament.user_id = :user_id
                );
            """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"user_id": user_id, "guild_id": guild_id, "current_time": current_time},
        )
        .fetchall()
    )
    return [Tournament.from_db_row(row) for row in result]


def fetch_active_tournament_by_guild(guild_id: int) -> List[Tournament]:
    """
    Fetch all tournements that we can register to for a guild
    """
    current_time = datetime.now(timezone.utc)
    query = f"""
            SELECT 
                {SELECT_TOURNAMENT},
                0 as current_user_count
            FROM tournament
            WHERE guild_id = :guild_id 
                AND date(start_date) <= date(:current_time) 
                AND date(end_date) >= date(:current_time);
            """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"guild_id": guild_id, "current_time": current_time},
        )
        .fetchall()
    )
    return [Tournament.from_db_row(row) for row in result]


def fetch_tournament_games_by_tournament_id(tournament_id: int) -> List[TournamentGame]:
    """
    Fetch a user name from the user_info table
    """

    result = (
        database_manager.get_cursor()
        .execute(
            """
            SELECT  id,
                    tournament_id,
                    user1_id,
                    user2_id,
                    user_winner_id,
                    score,
                    map,
                    timestamp,
                    next_game1_id,
                    next_game2_id
            FROM tournament_game WHERE tournament_id = :tournament_id
            """,
            {"tournament_id": tournament_id},
        )
        .fetchall()
    )
    if result is not None:
        return [TournamentGame.from_db_row(row) for row in result]
    else:
        # Handle the case where no user was found, e.g., return None or raise an exception
        return []


def block_registration_today_tournament_start(date_to_start: datetime) -> None:
    """
    Block registration for a tournament.
    """

    date_only = date_to_start.isoformat()  # Get today's date when the function is called

    database_manager.get_cursor().execute(
        """
        UPDATE tournament
        SET has_started = 1
        WHERE date(start_date) = date(?);
        """,
        (date_only,),
    )
    database_manager.get_conn().commit()


def get_people_registered_for_tournament(tournament_id: int) -> List[UserInfo]:
    """
    Get the list of people who registered for a tournament.
    """
    database_manager.get_cursor().execute(
        """
        SELECT user_id, 
              display_name, 
              ubisoft_username_max, 
              ubisoft_username_active, 
              r6_tracker_active_id,
              time_zone
        FROM user_tournament
        LEFT JOIN user_info ON user_tournament.user_id = user_info.id
        WHERE tournament_id = :tournament_id;
        """,
        {"tournament_id": tournament_id},
    )

    return [UserInfo(*row) for row in database_manager.get_cursor().fetchall()]


def save_tournament(tournament: Tournament) -> Tournament:
    """
    Save the tournament games.
    """
    cursor = database_manager.get_cursor()
    cursor.execute(
        """
        UPDATE tournament
            SET max_players = :max_players
        WHERE id = :tournament_id;
        """,
        {"max_players": tournament.max_players, "tournament_id": tournament.id},
    )

    database_manager.get_conn().commit()


def save_tournament_games(games: List[TournamentGame]) -> None:
    """
    Save the tournament games.
    """
    cursor = database_manager.get_cursor()
    for game in games:
        if game is None:
            continue
        cursor.execute(
            """
            UPDATE tournament_game
            SET user1_id = ?,
                user2_id = ?,
                map = ?,
                user_winner_id = ?,
                score = ?,
                timestamp = ?
            WHERE id = ?;
            """,
            (game.user1_id, game.user2_id, game.map, game.user_winner_id, game.score, game.timestamp, game.id),
        )

    database_manager.get_conn().commit()


def fetch_tournament_by_id(tournament_id: int) -> Optional[Tournament]:
    """
    Fetch a tournament by its ID.
    """
    query = f"""
            SELECT 
                 {SELECT_TOURNAMENT},
                0 as current_user_count
            FROM tournament
            WHERE id = :tournament_id;
            """
    result = (
        database_manager.get_cursor()
        .execute(
            query,
            {"tournament_id": tournament_id},
        )
        .fetchone()
    )
    if result is not None:
        return Tournament.from_db_row(result)
    else:
        return None


def register_user_for_tournament(tournament_id: int, user_id: int, registration_date: datetime) -> None:
    """
    Register a user for a tournament.
    """
    cursor = database_manager.get_cursor()
    cursor.execute(
        """
        INSERT INTO user_tournament (tournament_id, user_id, registration_date)
        VALUES (:tournament_id, :user_id, :registration_date);
        """,
        {"tournament_id": tournament_id, "user_id": user_id, "registration_date": registration_date},
    )
    database_manager.get_conn().commit()
