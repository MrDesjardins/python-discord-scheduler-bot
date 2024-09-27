"""
Common code for the gatherer and analyse
"""

import sqlite3

EVENT_CONNECT = "connect"
EVENT_DISCONNECT = "disconnect"

# Connect to SQLite database (it will create the database file if it doesn't exist)
conn = sqlite3.connect("user_activity.db")
cursor = conn.cursor()

# Create the tables
cursor.execute(
    """
CREATE TABLE IF NOT EXISTS user_info (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL
)
"""
)

cursor.execute(
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
cursor.execute(
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