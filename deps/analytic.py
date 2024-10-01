"""
Common code for the gatherer and analyse
"""

import sqlite3
from dataclasses import dataclass

EVENT_CONNECT = "connect"
EVENT_DISCONNECT = "disconnect"
database_name = "user_activity.db"


def set_database_name(name: str) -> None:
    """
    Set the database name
    """
    global database_name
    database_name = name


# Connect to SQLite database (it will create the database file if it doesn't exist)
conn = sqlite3.connect(database_name)
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


# Define a dataclass to represent each record
@dataclass
class UserInfo:
    id: int
    display_name: str


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


# Define a dataclass to represent each record
@dataclass
class UserActivity:
    user_id: int
    channel_id: int
    event: str
    timestamp: str
    guild_id: int


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


# Define a dataclass to represent each record
@dataclass
class UserWeight:
    user_a: str
    user_b: str
    channel_id: str
    weight: float
