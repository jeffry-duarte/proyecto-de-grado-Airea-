import time

from backend.airea_api.core.config import SESSION_LIFETIME_SECONDS
from sqlalchemy import text
from sqlalchemy.engine import Connection


def create_session(
    connection: Connection, token_hash: str, user_id: str
) -> None:
    now_ms = int(time.time() * 1000)
    connection.execute(
        text("DELETE FROM sessions WHERE expires_at <= :now_ms"),
        {"now_ms": now_ms},
    )
    connection.execute(
        text("""
            INSERT INTO sessions (token_hash, user_id, expires_at)
            VALUES (:token_hash, :user_id, :expires_at)
        """),
        {
            "token_hash": token_hash,
            "user_id": user_id,
            "expires_at": now_ms + SESSION_LIFETIME_SECONDS * 1000,
        },
    )


def delete_session(connection: Connection, token_hash: str) -> None:
    connection.execute(
        text("DELETE FROM sessions WHERE token_hash = :token_hash"),
        {"token_hash": token_hash},
    )
