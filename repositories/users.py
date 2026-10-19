import sqlite3
import uuid
from datetime import datetime, timezone


def find_by_email(connection: sqlite3.Connection, email: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM users WHERE email = ?", (email,)
    ).fetchone()


def find_by_id(connection: sqlite3.Connection, user_id: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def find_by_session_token(
    connection: sqlite3.Connection, token_hash: str, now_ms: int
) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        """,
        (token_hash, now_ms),
    ).fetchone()


def create_user(
    connection: sqlite3.Connection,
    *,
    name: str,
    email: str,
    password_salt: str,
    password_hash: str,
    locality: str,
    favorite_station_id: str,
    health_profile: str,
    notifications_enabled: bool,
    role: str,
) -> str:
    user_id = uuid.uuid4().hex
    connection.execute(
        """
        INSERT INTO users (
            id, name, email, password_salt, password_hash, locality,
            favorite_station_id, health_profile, notifications_enabled, role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            name,
            email,
            password_salt,
            password_hash,
            locality,
            favorite_station_id,
            health_profile,
            int(notifications_enabled),
            role,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    return user_id


def update_profile(
    connection: sqlite3.Connection,
    *,
    user_id: str,
    locality: str,
    favorite_station_id: str,
    health_profile: str,
    notifications_enabled: bool,
) -> None:
    connection.execute(
        """
        UPDATE users
        SET locality = ?, favorite_station_id = ?, health_profile = ?, notifications_enabled = ?
        WHERE id = ?
        """,
        (
            locality,
            favorite_station_id,
            health_profile,
            int(notifications_enabled),
            user_id,
        ),
    )


def has_admin(connection: sqlite3.Connection) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM users WHERE role = 'admin' LIMIT 1"
        ).fetchone()
        is not None
    )
