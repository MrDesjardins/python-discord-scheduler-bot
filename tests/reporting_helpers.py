"""Small SQLite fixture for the reporting tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def create_reporting_db(tmp_path: Path) -> Path:
    path = tmp_path / "reporting_test.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE user_info (
            id INTEGER PRIMARY KEY,
            display_name TEXT,
            ubisoft_username_max TEXT,
            ubisoft_username_active TEXT,
            time_zone TEXT,
            r6_tracker_active_id TEXT,
            max_mmr INTEGER
        );
        CREATE TABLE user_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            channel_id INTEGER,
            guild_id INTEGER,
            event TEXT,
            timestamp TEXT
        );
        CREATE TABLE user_full_match_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_uuid TEXT,
            user_id INTEGER,
            match_timestamp TEXT,
            match_duration_ms INTEGER,
            data_center TEXT,
            session_type TEXT,
            map_name TEXT,
            is_surrender INTEGER,
            is_forfeit INTEGER,
            is_rollback INTEGER,
            r6_tracker_user_uuid TEXT,
            ubisoft_username TEXT,
            operators TEXT,
            round_played_count INTEGER,
            round_won_count INTEGER,
            round_lost_count INTEGER,
            round_disconnected_count INTEGER,
            kill_count INTEGER,
            death_count INTEGER,
            assist_count INTEGER,
            head_shot_count INTEGER,
            points_gained INTEGER,
            rank_name TEXT,
            rank_previous INTEGER,
            has_win INTEGER
        );
        CREATE TABLE archived_message (
            message_id INTEGER PRIMARY KEY,
            author_id INTEGER,
            author_is_bot INTEGER,
            channel_name TEXT,
            created_at TEXT
        );
        """
    )
    users = [
        (1, "Alice", "alice", "alice", "US/Eastern", None, 4000),
        (2, "Bob", "bob", "bob", "US/Central", None, 3500),
        (3, "Carol", "carol", "carol", "US/Pacific", None, 3000),
        (4, "Mallory <script>alert(1)</script>", "mallory", "mallory", "US/Eastern", None, 2000),
    ]
    conn.executemany(
        "INSERT INTO user_info VALUES (?, ?, ?, ?, ?, ?, ?)",
        users,
    )
    events = [
        (1, 10, 1, "connect", "2026-10-01T20:00:00+00:00"),
        (1, 10, 1, "disconnect", "2026-10-01T22:00:00+00:00"),
        (2, 10, 1, "connect", "2026-10-01T20:30:00+00:00"),
        (2, 10, 1, "disconnect", "2026-10-01T21:30:00+00:00"),
        (4, 11, 1, "connect", "2026-10-02T19:00:00+00:00"),
        (4, 11, 1, "disconnect", "2026-10-02T20:00:00+00:00"),
        (1, 10, 1, "connect", "2026-10-10T20:00:00+00:00"),
        (1, 10, 1, "disconnect", "2026-10-10T22:00:00+00:00"),
    ]
    conn.executemany(
        "INSERT INTO user_activity (user_id, channel_id, guild_id, event, timestamp) VALUES (?, ?, ?, ?, ?)",
        events,
    )
    matches = [
        (
            "m1",
            1,
            "2026-10-01T21:00:00+00:00",
            1_800_000,
            "US East",
            "Ranked",
            "Bank",
            0,
            0,
            0,
            "u1",
            "alice",
            "Doc,Valkyrie",
            9,
            5,
            4,
            0,
            8,
            5,
            2,
            3,
            25,
            "Gold",
            0,
            1,
        ),
        (
            "m1",
            2,
            "2026-10-01T21:00:00+00:00",
            1_800_000,
            "US East",
            "Ranked",
            "Bank",
            0,
            0,
            0,
            "u2",
            "bob",
            "Buck,Alibi",
            9,
            5,
            4,
            0,
            6,
            4,
            3,
            2,
            25,
            "Silver",
            0,
            1,
        ),
        (
            "m2",
            1,
            "2026-10-05T21:00:00+00:00",
            1_800_000,
            "US East",
            "Ranked",
            "Clubhouse",
            0,
            0,
            0,
            "u1",
            "alice",
            "Doc",
            9,
            3,
            6,
            0,
            4,
            6,
            1,
            1,
            -20,
            "Gold",
            0,
            0,
        ),
        (
            "m3",
            3,
            "2026-10-10T21:00:00+00:00",
            1_800_000,
            "US West",
            "Ranked",
            "Kafe",
            0,
            0,
            0,
            "u3",
            "carol",
            "Ash",
            9,
            5,
            4,
            0,
            7,
            5,
            0,
            4,
            30,
            "Bronze",
            0,
            1,
        ),
    ]
    conn.executemany(
        """
        INSERT INTO user_full_match_info (
            match_uuid, user_id, match_timestamp, match_duration_ms, data_center, session_type,
            map_name, is_surrender, is_forfeit, is_rollback, r6_tracker_user_uuid, ubisoft_username,
            operators, round_played_count, round_won_count, round_lost_count, round_disconnected_count,
            kill_count, death_count, assist_count, head_shot_count, points_gained, rank_name,
            rank_previous, has_win
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        matches,
    )
    conn.execute(
        "INSERT INTO archived_message (message_id, author_id, author_is_bot, channel_name, created_at) "
        "VALUES (1, 1, 0, 'general', '2026-10-02T12:00:00+00:00')"
    )
    conn.commit()
    conn.close()
    return path
