import sqlite3
import time

from backend.airea_api.core.config import SESSION_LIFETIME_SECONDS


def create_session(
    connection: sqlite3.Connection, token_hash: str, user_id: str
) -> None:
    now_ms = int(time.time() * 1000)
    connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now_ms,))
    connection.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (token_hash, user_id, now_ms + SESSION_LIFETIME_SECONDS * 1000),
    )


def delete_session(connection: sqlite3.Connection, token_hash: str) -> None:
    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
