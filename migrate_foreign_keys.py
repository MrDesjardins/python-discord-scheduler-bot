#!/usr/bin/env python3
"""
Migration script to fix foreign key constraints in the database.

This script migrates the following tables to correct their foreign key references:
- bet_user_tournament: tournament_id -> tournament(id) instead of tournament_game(id)
- bet_game: tournament_id -> tournament(id) instead of tournament_game(id)
- bet_user_game: tournament_id -> tournament(id) instead of tournament_game(id)
- bet_ledger_entry: tournament_id -> tournament(id) instead of tournament_game(id)
- user_full_stats_info: user_id -> user_info(id) instead of users(id)
- user_following: both FKs -> user_info(id) instead of user_info(user_id)
- custom_game_user_subscription: user_id -> user_info(id) instead of user_info(user_id)

IMPORTANT: Backup your database before running this script!
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

# Database path
DB_PATH = "user_activity.db"
BACKUP_SUFFIX = f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"


def create_backup(db_path: str) -> str:
    """Create a backup of the database before migration."""
    import shutil
    backup_path = db_path.replace('.db', BACKUP_SUFFIX)
    shutil.copy2(db_path, backup_path)
    print(f"✓ Created backup: {backup_path}")
    return backup_path


def check_table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def get_table_row_count(cursor: sqlite3.Cursor, table_name: str) -> int:
    """Get the number of rows in a table."""
    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    return cursor.fetchone()[0]


def migrate_table(
    conn: sqlite3.Connection,
    table_name: str,
    create_table_sql: str,
    copy_columns: List[str]
) -> Tuple[bool, str]:
    """
    Migrate a single table to new schema with correct foreign keys.

    Returns:
        Tuple of (success: bool, message: str)
    """
    cursor = conn.cursor()

    try:
        # Check if table exists
        if not check_table_exists(cursor, table_name):
            return (True, f"Table {table_name} does not exist, skipping")

        # Get row count before migration
        row_count_before = get_table_row_count(cursor, table_name)
        print(f"  Migrating {table_name} ({row_count_before} rows)...")

        # Create new table with correct foreign keys
        temp_table_name = f"{table_name}_new"
        cursor.execute(f"DROP TABLE IF EXISTS {temp_table_name}")
        cursor.execute(create_table_sql.replace(table_name, temp_table_name))

        # Copy data from old table to new table
        columns_str = ", ".join(copy_columns)
        cursor.execute(f"""
            INSERT INTO {temp_table_name} ({columns_str})
            SELECT {columns_str} FROM {table_name}
        """)

        # Verify row count
        row_count_after = get_table_row_count(cursor, temp_table_name)
        if row_count_before != row_count_after:
            raise Exception(
                f"Row count mismatch! Before: {row_count_before}, After: {row_count_after}"
            )

        # Drop old table and rename new table
        cursor.execute(f"DROP TABLE {table_name}")
        cursor.execute(f"ALTER TABLE {temp_table_name} RENAME TO {table_name}")

        return (True, f"✓ Migrated {table_name} ({row_count_after} rows)")

    except Exception as e:
        return (False, f"✗ Failed to migrate {table_name}: {e}")


def run_migration():
    """Run the complete migration process."""

    print("="*70)
    print("Foreign Key Migration Script")
    print("="*70)
    print()

    # Check if database exists
    if not Path(DB_PATH).exists():
        print(f"✗ Database not found: {DB_PATH}")
        print("  If you're using a different database name, update DB_PATH in this script.")
        sys.exit(1)

    # Create backup
    print("Step 1: Creating backup...")
    backup_path = create_backup(DB_PATH)
    print()

    # Connect to database
    print("Step 2: Connecting to database...")
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")  # Disable FK checks during migration
    print("✓ Connected")
    print()

    # Track migration results
    results = []
    all_success = True

    try:
        print("Step 3: Migrating tables...")
        print()

        # Migration 1: bet_user_tournament
        success, msg = migrate_table(
            conn,
            "bet_user_tournament",
            """
            CREATE TABLE bet_user_tournament (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY(tournament_id) REFERENCES tournament(id),
                FOREIGN KEY(user_id) REFERENCES user_info(id)
            )
            """,
            ["id", "tournament_id", "user_id", "amount"]
        )
        results.append(msg)
        all_success = all_success and success

        # Migration 2: bet_game
        success, msg = migrate_table(
            conn,
            "bet_game",
            """
            CREATE TABLE bet_game (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                tournament_game_id INTEGER NOT NULL,
                probability_user_1_win REAL NOT NULL,
                probability_user_2_win REAL NOT NULL,
                bet_distributed BOOLEAN DEFAULT 0,
                FOREIGN KEY(tournament_id) REFERENCES tournament(id),
                FOREIGN KEY(tournament_game_id) REFERENCES tournament_game(id)
            )
            """,
            ["id", "tournament_id", "tournament_game_id", "probability_user_1_win",
             "probability_user_2_win", "bet_distributed"]
        )
        results.append(msg)
        all_success = all_success and success

        # Migration 3: bet_user_game
        success, msg = migrate_table(
            conn,
            "bet_user_game",
            """
            CREATE TABLE bet_user_game (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                bet_game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                user_id_bet_placed INTEGER NOT NULL,
                time_bet_placed DATETIME NOT NULL,
                probability_user_win_when_bet_placed REAL NOT NULL,
                bet_distributed BOOLEAN DEFAULT 0,
                FOREIGN KEY(tournament_id) REFERENCES tournament(id),
                FOREIGN KEY(bet_game_id) REFERENCES bet_game(id),
                FOREIGN KEY(user_id) REFERENCES user_info(id),
                FOREIGN KEY(user_id_bet_placed) REFERENCES user_info(id)
            )
            """,
            ["id", "tournament_id", "bet_game_id", "user_id", "amount",
             "user_id_bet_placed", "time_bet_placed", "probability_user_win_when_bet_placed",
             "bet_distributed"]
        )
        results.append(msg)
        all_success = all_success and success

        # Migration 4: bet_ledger_entry
        success, msg = migrate_table(
            conn,
            "bet_ledger_entry",
            """
            CREATE TABLE bet_ledger_entry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                tournament_game_id INTEGER NOT NULL,
                bet_game_id INTEGER NOT NULL,
                bet_user_game_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                FOREIGN KEY(tournament_id) REFERENCES tournament(id),
                FOREIGN KEY(tournament_game_id) REFERENCES tournament_game(id),
                FOREIGN KEY(bet_game_id) REFERENCES bet_game(id),
                FOREIGN KEY(bet_user_game_id) REFERENCES bet_user_game(id),
                FOREIGN KEY(user_id) REFERENCES user_info(id)
            )
            """,
            ["id", "tournament_id", "tournament_game_id", "bet_game_id",
             "bet_user_game_id", "user_id", "amount"]
        )
        results.append(msg)
        all_success = all_success and success

        # Migration 5: user_full_stats_info
        # Note: This table has many columns, listing the essential ones
        success, msg = migrate_table(
            conn,
            "user_full_stats_info",
            """
            CREATE TABLE user_full_stats_info (
                user_id INTEGER PRIMARY KEY,
                r6_tracker_user_uuid TEXT,
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
                FOREIGN KEY (user_id) REFERENCES user_info(id)
            )
            """,
            [
                "user_id", "r6_tracker_user_uuid", "total_matches_played", "total_matches_won",
                "total_matches_lost", "total_matches_abandoned", "time_played_seconds",
                "total_kills", "total_deaths", "total_attacker_round_wins", "total_defender_round_wins",
                "total_headshots", "total_headshots_missed", "headshot_percentage",
                "total_wall_bang", "total_damage", "total_assists", "total_team_kills",
                "attacked_breacher_count", "attacked_breacher_percentage",
                "attacked_fragger_count", "attacked_fragger_percentage",
                "attacked_intel_count", "attacked_intel_percentage",
                "attacked_roam_count", "attacked_roam_percentage",
                "attacked_support_count", "attacked_support_percentage",
                "attacked_utility_count", "attacked_utility_percentage",
                "defender_debuffer_count", "defender_debuffer_percentage",
                "defender_entry_denier_count", "defender_entry_denier_percentage",
                "defender_intel_count", "defender_intel_percentage",
                "defender_support_count", "defender_support_percentage",
                "defender_trapper_count", "defender_trapper_percentage",
                "defender_utility_denier_count", "defender_utility_denier_percentage",
                "kd_ratio", "kill_per_match", "kill_per_minute", "win_percentage",
                "rank_match_played", "rank_match_won", "rank_match_lost", "rank_match_abandoned",
                "rank_kills_count", "rank_deaths_count", "rank_kd_ratio",
                "rank_kill_per_match", "rank_win_percentage",
                "arcade_match_played", "arcade_match_won", "arcade_match_lost", "arcade_match_abandoned",
                "arcade_kills_count", "arcade_deaths_count", "arcade_kd_ratio",
                "arcade_kill_per_match", "arcade_win_percentage",
                "quickmatch_match_played", "quickmatch_match_won", "quickmatch_match_lost",
                "quickmatch_match_abandoned", "quickmatch_kills_count", "quickmatch_deaths_count",
                "quickmatch_kd_ratio", "quickmatch_kill_per_match", "quickmatch_win_percentage"
            ]
        )
        results.append(msg)
        all_success = all_success and success

        # Migration 6: user_following
        success, msg = migrate_table(
            conn,
            "user_following",
            """
            CREATE TABLE user_following (
                user_id_who_want_follow_id INTEGER NOT NULL,
                user_to_follow_id INTEGER NOT NULL,
                follow_datetime DATETIME NOT NULL,
                PRIMARY KEY (user_id_who_want_follow_id, user_to_follow_id),
                FOREIGN KEY (user_id_who_want_follow_id) REFERENCES user_info(id),
                FOREIGN KEY (user_to_follow_id) REFERENCES user_info(id)
            )
            """,
            ["user_id_who_want_follow_id", "user_to_follow_id", "follow_datetime"]
        )
        results.append(msg)
        all_success = all_success and success

        # Migration 7: custom_game_user_subscription
        success, msg = migrate_table(
            conn,
            "custom_game_user_subscription",
            """
            CREATE TABLE custom_game_user_subscription (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                follow_datetime DATETIME NOT NULL,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (user_id) REFERENCES user_info(id)
            )
            """,
            ["user_id", "guild_id", "follow_datetime"]
        )
        results.append(msg)
        all_success = all_success and success

        print()

        if all_success:
            # Commit the transaction
            conn.commit()
            print("Step 4: Committing changes...")
            print("✓ All migrations completed successfully!")
            print()

            # Re-enable foreign keys and verify
            conn.execute("PRAGMA foreign_keys = ON")
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_key_check")
            fk_violations = cursor.fetchall()

            if fk_violations:
                print("⚠ Warning: Foreign key violations detected:")
                for violation in fk_violations:
                    print(f"  {violation}")
                print()
                print("You may need to clean up orphaned records manually.")
            else:
                print("✓ Foreign key integrity verified!")

        else:
            # Rollback on any failure
            conn.rollback()
            print("✗ Migration failed! Rolling back changes...")
            print()
            print("Database restored from backup. No changes were made.")
            print(f"Backup location: {backup_path}")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Unexpected error during migration: {e}")
        print("Rolling back all changes...")
        all_success = False

    finally:
        conn.close()

    # Print summary
    print()
    print("="*70)
    print("Migration Summary")
    print("="*70)
    for result in results:
        print(result)
    print()

    if all_success:
        print("🎉 Migration completed successfully!")
        print(f"📦 Backup saved at: {backup_path}")
        print()
        print("You can now delete the backup if everything works correctly.")
    else:
        print("❌ Migration failed!")
        print(f"📦 Database restored from backup: {backup_path}")
        print()
        print("Please review the error messages above and contact support if needed.")
        sys.exit(1)


if __name__ == "__main__":
    print()
    print("⚠️  WARNING: This will modify your database!")
    print()
    response = input("Do you want to proceed with the migration? (yes/no): ").strip().lower()

    if response in ['yes', 'y']:
        print()
        run_migration()
    else:
        print("Migration cancelled.")
        sys.exit(0)
