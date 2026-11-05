import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping


def find_by_email(connection: Connection, email: str) -> RowMapping | None:
    return connection.execute(
        text("SELECT * FROM users WHERE email = :email"), {"email": email}
    ).mappings().first()


def find_by_id(connection: Connection, user_id: str) -> RowMapping | None:
    return connection.execute(
        text("SELECT * FROM users WHERE id = :user_id"), {"user_id": user_id}
    ).mappings().first()


def find_by_session_token(
    connection: Connection, token_hash: str, now_ms: int
) -> RowMapping | None:
    return connection.execute(
        text("""
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = :token_hash AND sessions.expires_at > :now_ms
        """),
        {"token_hash": token_hash, "now_ms": now_ms},
    ).mappings().first()


def create_user(
    connection: Connection,
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
        text("""
        INSERT INTO users (
            id, name, email, password_salt, password_hash, locality,
            favorite_station_id, health_profile, notifications_enabled, role, created_at
        ) VALUES (
            :id, :name, :email, :password_salt, :password_hash, :locality,
            :favorite_station_id, :health_profile, :notifications_enabled,
            :role, :created_at
        )
        """),
        {
            "id": user_id,
            "name": name,
            "email": email,
            "password_salt": password_salt,
            "password_hash": password_hash,
            "locality": locality,
            "favorite_station_id": favorite_station_id,
            "health_profile": health_profile,
            "notifications_enabled": notifications_enabled,
            "role": role,
            "created_at": datetime.now(timezone.utc),
        },
    )
    return user_id


def update_profile(
    connection: Connection,
    *,
    user_id: str,
    locality: str,
    favorite_station_id: str,
    health_profile: str,
    notifications_enabled: bool,
) -> None:
    connection.execute(
        text("""
        UPDATE users
        SET locality = :locality, favorite_station_id = :favorite_station_id,
            health_profile = :health_profile, notifications_enabled = :notifications_enabled
        WHERE id = :user_id
        """),
        {
            "locality": locality,
            "favorite_station_id": favorite_station_id,
            "health_profile": health_profile,
            "notifications_enabled": notifications_enabled,
            "user_id": user_id,
        },
    )


def has_admin(connection: Connection) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")
        ).fetchone()
        is not None
    )


def list_for_admin(connection: Connection) -> list[RowMapping]:
    return list(
        connection.execute(
            text("""
                SELECT id, name, email, locality, favorite_station_id,
                    health_profile, notifications_enabled, role, created_at
                FROM users
                ORDER BY created_at DESC
            """)
        ).mappings()
    )


def update_for_admin(
    connection: Connection,
    *,
    user_id: str,
    name: str,
    locality: str,
    favorite_station_id: str,
    health_profile: str,
    notifications_enabled: bool,
    role: str,
) -> RowMapping | None:
    connection.execute(
        text("""
            UPDATE users
            SET name = :name, locality = :locality,
                favorite_station_id = :favorite_station_id,
                health_profile = :health_profile,
                notifications_enabled = :notifications_enabled,
                role = :role
            WHERE id = :user_id
        """),
        {
            "user_id": user_id,
            "name": name,
            "locality": locality,
            "favorite_station_id": favorite_station_id,
            "health_profile": health_profile,
            "notifications_enabled": notifications_enabled,
            "role": role,
        },
    )
    return find_by_id(connection, user_id)
