"""
Common code for the gatherer and analyse
"""

import datetime
import sqlite3

EVENT_CONNECT = "connect"
EVENT_DISCONNECT = "disconnect"
DATABASE_NAME = "user_activity.db"
DATABASE_NAME_TEST = "user_activity_test.db"  # Can use DATABASE_NAME_TEST = ":memory:" to use an in-memory database


# Adapter for datetime objects
def adapt_datetime(dt):
    return dt.isoformat()


# Converter for datetime objects
def convert_datetime(s):
    return datetime.datetime.fromisoformat(s)


class DatabaseManager:
    """Handle the database connection to the right file"""

    def __init__(self, name):
        """Initialize the database manager name which correspond to the file name"""
        # Register the adapters and converters with sqlite3
        sqlite3.register_adapter(datetime.datetime, adapt_datetime)
        sqlite3.register_converter("datetime", convert_datetime)
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

        ### CACHE TABLES ###
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value BLOB NOT NULL,
            expiration DATETIME DEFAULT NULL
        )
        """
        )

        ### User Activity TABLES ###
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS user_info (
            id INTEGER PRIMARY KEY,
            display_name TEXT NOT NULL,
            ubisoft_username_max TEXT NULL,
            ubisoft_username_active TEXT NULL,
            r6_tracker_active_id TEXT NULL,
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
            maps TEXT NOT NULL,
            has_started INTEGER DEFAULT 0
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
            FOREIGN KEY(user_id) REFERENCES user_info(id),
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
            score TEXT NULL,
            map TEXT NULL,
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
        ###  Game Play Stats Tables ###
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS user_full_match_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_uuid TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            match_timestamp DATETIME NOT NULL,
            match_duration_ms INTEGER NOT NULL,
            data_center TEXT NOT NULL,
            session_type TEXT NOT NULL,
            map_name TEXT NOT NULL,
            is_surrender BOOLEAN NOT NULL,
            is_forfeit BOOLEAN NOT NULL,
            is_rollback BOOLEAN NOT NULL,
            r6_tracker_user_uuid TEXT NOT NULL,
            ubisoft_username TEXT NOT NULL,
            operators TEXT NOT NULL,
            round_played_count INTEGER NOT NULL,
            round_won_count INTEGER NOT NULL,
            round_lost_count INTEGER NOT NULL,
            round_disconnected_count INTEGER NOT NULL,
            kill_count INTEGER NOT NULL,
            death_count INTEGER NOT NULL,
            assist_count INTEGER NOT NULL,
            head_shot_count INTEGER NOT NULL,
            tk_count INTEGER NOT NULL,
            ace_count INTEGER NOT NULL,
            first_kill_count INTEGER NOT NULL,
            first_death_count INTEGER NOT NULL,
            clutches_win_count INTEGER NOT NULL,
            clutches_loss_count INTEGER NOT NULL,
            clutches_win_count_1v1 INTEGER NOT NULL,
            clutches_win_count_1v2 INTEGER NOT NULL,
            clutches_win_count_1v3 INTEGER NOT NULL,
            clutches_win_count_1v4 INTEGER NOT NULL,
            clutches_win_count_1v5 INTEGER NOT NULL,
            clutches_lost_count_1v1 INTEGER NOT NULL,
            clutches_lost_count_1v2 INTEGER NOT NULL,
            clutches_lost_count_1v3 INTEGER NOT NULL,
            clutches_lost_count_1v4 INTEGER NOT NULL,
            clutches_lost_count_1v5 INTEGER NOT NULL,
            kill_1_count INTEGER NOT NULL,
            kill_2_count INTEGER NOT NULL,
            kill_3_count INTEGER NOT NULL,
            kill_4_count INTEGER NOT NULL,
            kill_5_count INTEGER NOT NULL,
            rank_points INTEGER NOT NULL,
            rank_name TEXT NOT NULL,
            points_gained INTEGER NOT NULL,
            rank_previous INTEGER NOT NULL,
            kd_ratio INTEGER NOT NULL,
            head_shot_percentage INTEGER NOT NULL,
            kills_per_round INTEGER NOT NULL,
            deaths_per_round INTEGER NOT NULL,
            assists_per_round INTEGER NOT NULL,
            has_win BOOLEAN NOT NULL,
            FOREIGN KEY(user_id) REFERENCES user_info(id)
        );
        """
        )
        ### Betting
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS bet_user_tournament (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournament_game(id),
            FOREIGN KEY(user_id) REFERENCES user_info(id)
        );
        """
        )
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS bet_game (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            probability_user_1_win REAL NOT NULL,
            probability_user_2_win REAL NOT NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournament_game(id),
            FOREIGN KEY(game_id) REFERENCES tournament_game(id)
        );
        """
        )
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS bet_user_game (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            bet_game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            user_id_bet_placed INTEGER NOT NULL,
            time_bet_placed DATETIME NOT NULL,
            probability_user_win_when_bet_placed REAL NOT NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournament_game(id),
            FOREIGN KEY(bet_game_id) REFERENCES bet_game(id),
            FOREIGN KEY(user_id) REFERENCES user_info(id),
            FOREIGN KEY(user_id_bet_placed) REFERENCES user_info(id)
        );
        """
        )

        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS bet_ledger_entry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            game_id INTEGER NOT NULL,
            bet_game_id INTEGER NOT NULL,
            bet_user_game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournament_game(id),
            FOREIGN KEY(game_id) REFERENCES tournament_game(id),
            FOREIGN KEY(bet_game_id) REFERENCES bet_game(id),
            FOREIGN KEY(bet_user_game_id) REFERENCES bet_user_game(id),
            FOREIGN KEY(user_id) REFERENCES user_info(id)
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
