"""
Common code for the gatherer and analyse
"""

import sqlite3

EVENT_CONNECT = "connect"
EVENT_DISCONNECT = "disconnect"
DATABASE_NAME = "user_activity.db"
DATABASE_NAME_TEST = "user_activity_test.db"


class DatabaseManager:
    """Handle the database connection to the right file"""

    def __init__(self, name):
        """Initialize the database manager name which correspond to the file name"""
        self.set_database_name(name)

    def set_database_name(self, name: str) -> None:
        """
        Set the database name
        """
        self.name = name
        self.conn = sqlite3.connect(name)
        self.cursor = self.conn.cursor()
        self.init_database()

    def get_database_name(self):
        """Get the database name, useful to know if test or prod"""
        return self.name

    def init_database(self):
        """Ensure that database has all the tables"""

        ### User Activity TABLES ###
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY,
            display_name TEXT NOT NULL,
            ubisoft_username_max TEXT NULL,
            ubisoft_username_active TEXT NULL,
            time_zone TEXT DEFAULT 'US/Eastern'
        )
        """
        )

        self.get_cursor().execute(
            f"""
        CREATE TABLE IF NOT EXISTS user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            event TEXT CHECK(event IN ('{EVENT_CONNECT}', '{EVENT_DISCONNECT}')) NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES user_info(id)
        )
        """
        )

        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS user_weights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_a TEXT NOT NULL,
            user_b TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            weight REAL NOT NULL
        );
        """
        )

        ### TOURNAMENT TABLES ###
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS tournament (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            registration_date DATETIME NOT NULL,
            start_date DATETIME NOT NULL,
            end_date DATETIME NOT NULL,
            best_of INTEGER NOT NULL,
            max_players INTEGER NOT NULL,
            maps TEXT NOT NULL
        );
        """
        )

        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS user_tournament (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tournament_id INTEGER NOT NULL,
            registration_date DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES user_info(id)
            FOREIGN KEY(tournament_id) REFERENCES tournament(id)
        );
        """
        )


        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS tournament_game (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            user1_id INTEGER NULL,
            user2_id INTEGER NULL,
            user_winner_id INTEGER NULL,
            timestamp DATETIME NULL,
            next_game1_id INTEGER NULL,
            next_game2_id INTEGER NULL,
            FOREIGN KEY(user1_id) REFERENCES user_info(id),
            FOREIGN KEY(user2_id) REFERENCES user_info(id),
            FOREIGN KEY(user_winner_id) REFERENCES user_info(id),
            FOREIGN KEY(tournament_id) REFERENCES tournament(id)
        );
        """
        )

    def get_conn(self):
        """Access to the database connection"""
        return self.conn

    def get_cursor(self):
        """Access to the database cursor"""
        return self.cursor


database_manager = DatabaseManager(DATABASE_NAME)
