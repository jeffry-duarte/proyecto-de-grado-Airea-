import sqlite3
import time


def find_valid_invite(
    connection: sqlite3.Connection, token_hash: str
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT email FROM admin_invites WHERE token_hash = ? AND expires_at > ?",
        (token_hash, int(time.time() * 1000)),
    ).fetchone()


def create_invite(
    connection: sqlite3.Connection,
    token_hash: str,
    email: str,
    expires_at: int,
) -> None:
    now_ms = int(time.time() * 1000)
    connection.execute(
        "DELETE FROM admin_invites WHERE email = ? OR expires_at <= ?",
        (email, now_ms),
    )
    connection.execute(
        "INSERT INTO admin_invites (token_hash, email, expires_at) VALUES (?, ?, ?)",
        (token_hash, email, expires_at),
    )


def delete_invite(connection: sqlite3.Connection, token_hash: str) -> None:
    connection.execute("DELETE FROM admin_invites WHERE token_hash = ?", (token_hash,))


def email_has_account(connection: sqlite3.Connection, email: str) -> bool:
    return (
        connection.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        is not None
    )
