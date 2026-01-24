"""
Common code for the gatherer and analyse
"""

import datetime
import sqlite3

from deps.log import print_error_log, print_log

EVENT_CONNECT = "connect"
EVENT_DISCONNECT = "disconnect"
DATABASE_NAME = "user_activity.db"
DATABASE_NAME_TEST = "user_activity_test.db"  # Can use DATABASE_NAME_TEST = ":memory:" to use an in-memory database


# Adapter for datetime objects
def adapt_datetime(dt):
    """Convert a datetime object to a string"""
    return dt.isoformat()


# Converter for datetime objects
def convert_datetime(s):
    """Convert a string to a datetime object"""
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
        self.conn = sqlite3.connect(name, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")  # Performance gain on write
        self.cursor = self.conn.cursor()
        self.init_database()

    def get_database_name(self):
        """Get the database name, useful to know if test or prod"""
        return self.name

    def drop_all_tables(self):
        """Drop all tables"""
        self.get_cursor().execute("DROP TABLE IF EXISTS user_following")
        self.get_cursor().execute("DROP TABLE IF EXISTS cache")
        self.get_cursor().execute("DROP TABLE IF EXISTS user_activity")
        self.get_cursor().execute("DROP TABLE IF EXISTS user_info")
        self.get_cursor().execute("DROP TABLE IF EXISTS user_weights")
        self.get_cursor().execute("DROP TABLE IF EXISTS tournament_team_members")
        self.get_cursor().execute("DROP TABLE IF EXISTS tournament")
        self.get_cursor().execute("DROP TABLE IF EXISTS user_tournament")
        self.get_cursor().execute("DROP TABLE IF EXISTS tournament_game")
        self.get_cursor().execute("DROP TABLE IF EXISTS user_full_match_info")
        self.get_cursor().execute("DROP TABLE IF EXISTS user_full_stats_info")
        self.get_cursor().execute("DROP TABLE IF EXISTS bet_user_tournament")
        self.get_cursor().execute("DROP TABLE IF EXISTS bet_game")
        self.get_cursor().execute("DROP TABLE IF EXISTS bet_user_game")
        self.get_cursor().execute("DROP TABLE IF EXISTS bet_ledger_entry")
        self.get_cursor().execute("DROP TABLE IF EXISTS custom_game_user_subscription")

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
        self.get_cursor().execute(
            """
            CREATE INDEX IF NOT EXISTS idx_expiration ON cache(expiration)
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
            time_zone TEXT DEFAULT 'US/Eastern',
            max_mmr INTEGER DEFAULT 0
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
            has_started INTEGER DEFAULT 0,
            has_finished INTEGER DEFAULT 0,
            team_size INTEGER NOT NULL DEFAULT 1
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
        self.get_cursor().execute(
            """
        CREATE TABLE IF NOT EXISTS tournament_team_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tournament_id INTEGER NOT NULL,
            user_leader_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY(user_leader_id) REFERENCES user_info(id),
            FOREIGN KEY(user_id) REFERENCES user_info(id),
            FOREIGN KEY(tournament_id) REFERENCES tournament(id)
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
            tournament_game_id INTEGER NOT NULL,
            probability_user_1_win REAL NOT NULL,
            probability_user_2_win REAL NOT NULL,
            bet_distributed BOOLEAN DEFAULT 0,
            FOREIGN KEY(tournament_id) REFERENCES tournament_game(id),
            FOREIGN KEY(tournament_game_id) REFERENCES tournament_game(id)
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
            bet_distributed BOOLEAN DEFAULT 0,
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
            tournament_game_id INTEGER NOT NULL,
            bet_game_id INTEGER NOT NULL,
            bet_user_game_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            FOREIGN KEY(tournament_id) REFERENCES tournament_game(id),
            FOREIGN KEY(tournament_game_id) REFERENCES tournament_game(id),
            FOREIGN KEY(bet_game_id) REFERENCES bet_game(id),
            FOREIGN KEY(bet_user_game_id) REFERENCES bet_user_game(id),
            FOREIGN KEY(user_id) REFERENCES user_info(id)
        );
        """
        )

        self.get_cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS user_full_stats_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                r6_tracker_user_uuid TEXT NOT NULL,
                total_matches_played INTEGER DEFAULT 0,
                total_matches_won INTEGER DEFAULT 0,
                total_matches_lost INTEGER DEFAULT 0,
                total_matches_abandoned INTEGER DEFAULT 0,
                time_played_seconds INTEGER DEFAULT 0,
                total_kills INTEGER DEFAULT 0,
                total_deaths INTEGER DEFAULT 0,
                total_attacker_round_wins INTEGER DEFAULT 0,
                total_defender_round_wins INTEGER DEFAULT 0,
                total_headshots INTEGER DEFAULT 0,
                total_headshots_missed INTEGER DEFAULT 0,
                headshot_percentage REAL DEFAULT 0.0,
                total_wall_bang INTEGER DEFAULT 0,
                total_damage INTEGER DEFAULT 0,
                total_assists INTEGER DEFAULT 0,
                total_team_kills INTEGER DEFAULT 0,
                attacked_breacher_count INTEGER DEFAULT 0,
                attacked_breacher_percentage REAL DEFAULT 0.0,
                attacked_fragger_count INTEGER DEFAULT 0,
                attacked_fragger_percentage REAL DEFAULT 0.0,
                attacked_intel_count INTEGER DEFAULT 0,
                attacked_intel_percentage REAL DEFAULT 0.0,
                attacked_roam_count INTEGER DEFAULT 0,
                attacked_roam_percentage REAL DEFAULT 0.0,
                attacked_support_count INTEGER DEFAULT 0,
                attacked_support_percentage REAL DEFAULT 0.0,
                attacked_utility_count INTEGER DEFAULT 0,
                attacked_utility_percentage REAL DEFAULT 0.0,
                defender_debuffer_count INTEGER DEFAULT 0,
                defender_debuffer_percentage REAL DEFAULT 0.0,
                defender_entry_denier_count INTEGER DEFAULT 0,
                defender_entry_denier_percentage REAL DEFAULT 0.0,
                defender_intel_count INTEGER DEFAULT 0,
                defender_intel_percentage REAL DEFAULT 0.0,
                defender_support_count INTEGER DEFAULT 0,
                defender_support_percentage REAL DEFAULT 0.0,
                defender_trapper_count INTEGER DEFAULT 0,
                defender_trapper_percentage REAL DEFAULT 0.0,
                defender_utility_denier_count INTEGER DEFAULT 0,
                defender_utility_denier_percentage REAL DEFAULT 0.0,
                kd_ratio REAL DEFAULT 0.0,
                kill_per_match REAL DEFAULT 0.0,
                kill_per_minute REAL DEFAULT 0.0,
                win_percentage REAL DEFAULT 0.0,
                rank_match_played INTEGER DEFAULT 0,
                rank_match_won INTEGER DEFAULT 0,
                rank_match_lost INTEGER DEFAULT 0,
                rank_match_abandoned INTEGER DEFAULT 0,
                rank_kills_count INTEGER DEFAULT 0,
                rank_deaths_count INTEGER DEFAULT 0,
                rank_kd_ratio REAL DEFAULT 0.0,
                rank_kill_per_match REAL DEFAULT 0.0,
                rank_win_percentage REAL DEFAULT 0.0,
                arcade_match_played INTEGER DEFAULT 0,
                arcade_match_won INTEGER DEFAULT 0,
                arcade_match_lost INTEGER DEFAULT 0,
                arcade_match_abandoned INTEGER DEFAULT 0,
                arcade_kills_count INTEGER DEFAULT 0,
                arcade_deaths_count INTEGER DEFAULT 0,
                arcade_kd_ratio REAL DEFAULT 0.0,
                arcade_kill_per_match REAL DEFAULT 0.0,
                arcade_win_percentage REAL DEFAULT 0.0,
                quickmatch_match_played INTEGER DEFAULT 0,
                quickmatch_match_won INTEGER DEFAULT 0,
                quickmatch_match_lost INTEGER DEFAULT 0,
                quickmatch_match_abandoned INTEGER DEFAULT 0,
                quickmatch_kills_count INTEGER DEFAULT 0,
                quickmatch_deaths_count INTEGER DEFAULT 0,
                quickmatch_kd_ratio REAL DEFAULT 0.0,
                quickmatch_kill_per_match REAL DEFAULT 0.0,
                quickmatch_win_percentage REAL DEFAULT 0.0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """
        )

        self.get_cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS user_following (
                user_id_who_want_follow_id INTEGER NOT NULL,
                user_to_follow_id INTEGER NOT NULL,
                follow_datetime DATETIME NOT NULL,
                PRIMARY KEY (user_id_who_want_follow_id, user_to_follow_id),
                FOREIGN KEY (user_id_who_want_follow_id) REFERENCES user_info(user_id),
                FOREIGN KEY (user_to_follow_id) REFERENCES user_info(user_id)
            );
        """
        )

        self.get_cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS custom_game_user_subscription (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                follow_datetime DATETIME NOT NULL,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (user_id) REFERENCES user_info(user_id)
            );
        """
        )

        self.get_cursor().execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_activity_event ON user_activity(user_id, channel_id, guild_id, event, timestamp);
            """
        )
        self.get_cursor().execute(
            """
             CREATE INDEX IF NOT EXISTS idx_user_activity_timestamp ON user_activity(timestamp);
            """
        )
        self.get_cursor().execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_info_id ON user_info(id);
            """
        )

        self.get_cursor().execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS unique_match_user ON user_full_match_info(match_uuid, user_id);
            """
        )

        self.get_cursor().execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_full_stats_info_user_id ON user_full_stats_info(user_id);
            """
        )
        self.get_cursor().execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_user_full_stats_info_r6_tracker_user_uuid ON user_full_stats_info(r6_tracker_user_uuid);
            """
        )

        # Add composite index for time-based match queries
        self._migrate_add_match_timestamp_index()

        # Add deduplication index for user_activity
        self._migrate_add_activity_dedup_index()

    def _migrate_add_match_timestamp_index(self):
        """Add composite index for time-based match queries (user_id, match_timestamp)."""
        print_log("Running migration: Add index on user_full_match_info(user_id, match_timestamp)")
        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_match_timestamp
            ON user_full_match_info(user_id, match_timestamp DESC)
        """
        )
        self.conn.commit()
        print_log("Migration complete: idx_user_match_timestamp created")

    def _migrate_add_activity_dedup_index(self):
        """Add index to help deduplication queries."""
        print_log("Running migration: Add deduplication index on user_activity")
        self.cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_activity_dedup
            ON user_activity(user_id, channel_id, guild_id, event, timestamp)
        """
        )
        self.conn.commit()
        print_log("Migration complete: idx_user_activity_dedup created")

    def get_conn(self):
        """Access to the database connection"""
        return self.conn

    def get_cursor(self):
        """Access to the database cursor"""
        return self.cursor

    def data_access_transaction(self):
        """Provide a context manager for transactions"""
        return self.TransactionContext(self)

    class TransactionContext:
        """Internal class to handle transaction context"""

        def __init__(self, db_manager):
            self.db_manager = db_manager

        def __enter__(self):
            """Begin a transaction"""
            self.db_manager.conn.execute("BEGIN TRANSACTION")
            return self.db_manager.get_cursor()  # Reuse the database manager's cursor

        def __exit__(self, exc_type, exc_val, exc_tb):
            """Commit or rollback the transaction"""
            if exc_type is None:
                self.db_manager.conn.commit()  # Commit if no exception
            else:
                self.db_manager.conn.rollback()  # Rollback if an exception occurred
                print_error_log(f"system_database:TransactionContext:__exit__: {exc_val}")
            return True  # Avoid the exception to bubble up

    def close(self):
        """Close the database connection and cursor."""
        try:
            if hasattr(self, "cursor") and self.cursor:
                self.cursor.close()
                self.cursor = None  # pylint: disable=attribute-defined-outside-init
            if hasattr(self, "conn") and self.conn:
                self.conn.close()
                self.conn = None  # pylint: disable=attribute-defined-outside-init
        except Exception as e:
            print_error_log(f"DatabaseManager.close: {e}")


database_manager = DatabaseManager(DATABASE_NAME)


def run_wal_checkpoint():
    """
    Consolidate all the files into a single SqlLite file
    """
    database_manager.get_conn().execute("PRAGMA wal_checkpoint(FULL);")
