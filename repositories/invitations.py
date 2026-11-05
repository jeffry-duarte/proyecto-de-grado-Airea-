import time
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping


def find_valid_invite(
    connection: Connection, token_hash: str
) -> RowMapping | None:
    return connection.execute(
        text("""
            SELECT email FROM admin_invites
            WHERE token_hash = :token_hash AND expires_at > :now_ms
        """),
        {"token_hash": token_hash, "now_ms": int(time.time() * 1000)},
    ).mappings().first()


def create_invite(
    connection: Connection,
    token_hash: str,
    email: str,
    expires_at: int,
) -> None:
    now_ms = int(time.time() * 1000)
    connection.execute(
        text("DELETE FROM admin_invites WHERE email = :email OR expires_at <= :now_ms"),
        {"email": email, "now_ms": now_ms},
    )
    connection.execute(
        text("""
            INSERT INTO admin_invites (token_hash, email, expires_at)
            VALUES (:token_hash, :email, :expires_at)
        """),
        {"token_hash": token_hash, "email": email, "expires_at": expires_at},
    )


def delete_invite(connection: Connection, token_hash: str) -> None:
    connection.execute(
        text("DELETE FROM admin_invites WHERE token_hash = :token_hash"),
        {"token_hash": token_hash},
    )


def list_pending_invites(connection: Connection) -> list[RowMapping]:
    return list(
        connection.execute(
            text("""
                SELECT email, expires_at FROM admin_invites
                WHERE expires_at > :now_ms
                ORDER BY expires_at
            """),
            {"now_ms": int(time.time() * 1000)},
        ).mappings()
    )


def delete_invites_for_email(connection: Connection, email: str) -> None:
    connection.execute(
        text("DELETE FROM admin_invites WHERE email = :email"),
        {"email": email},
    )


def email_has_account(connection: Connection, email: str) -> bool:
    return (
        connection.execute(
            text("SELECT 1 FROM users WHERE email = :email"), {"email": email}
        ).fetchone()
        is not None
    )
