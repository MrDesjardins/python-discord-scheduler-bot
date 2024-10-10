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
        return self.name

    def init_database(self):
        """Ensure that database has all the tables"""
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY,
            display_name TEXT NOT NULL
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

    def get_conn(self):
        """Access to the database connection"""
        return self.conn

    def get_cursor(self):
        """Access to the database cursor"""
        return self.cursor


database_manager = DatabaseManager(DATABASE_NAME)
