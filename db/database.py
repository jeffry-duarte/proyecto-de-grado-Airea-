import sqlite3
from collections.abc import Iterator

from fastapi import Request

from backend.airea_api.core.config import DATABASE_PATH


def connect_database() -> sqlite3.Connection:
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(DATABASE_PATH), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize_database() -> None:
    connection = connect_database()
    try:
        connection.executescript(
            """
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                locality TEXT NOT NULL,
                favorite_station_id TEXT NOT NULL,
                health_profile TEXT NOT NULL,
                notifications_enabled INTEGER NOT NULL DEFAULT 1,
                role TEXT NOT NULL DEFAULT 'citizen',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                expires_at INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS admin_invites (
                token_hash TEXT PRIMARY KEY,
                email TEXT NOT NULL COLLATE NOCASE,
                expires_at INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS sessions_expiry_idx ON sessions(expires_at);
            CREATE INDEX IF NOT EXISTS admin_invites_expiry_idx ON admin_invites(expires_at);
            """
        )
    finally:
        connection.close()


def database_dependency(request: Request) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(str(request.app.state.database_path), timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        yield connection
    finally:
        connection.close()
