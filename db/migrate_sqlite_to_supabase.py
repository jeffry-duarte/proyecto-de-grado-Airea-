import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection, Engine, URL

from core.config import DATABASE_PATH, SUPABASE_DATABASE_URL
from db.database import (
    create_database_engine,
    initialize_database,
)


TABLES = {
    "roles": ("id", "name"),
    "users": (
        "id",
        "name",
        "email",
        "password_salt",
        "password_hash",
        "password_scheme",
        "locality",
        "favorite_station_id",
        "health_profile",
        "notifications_enabled",
        "role",
        "role_id",
        "created_at",
    ),
    "sessions": ("token_hash", "user_id", "expires_at"),
    "admin_invites": ("token_hash", "email", "expires_at"),
}


def _read_rows(connection: Connection, table: str) -> list[dict[str, Any]]:
    available = {column["name"] for column in inspect(connection).get_columns(table)}
    columns = [column for column in TABLES[table] if column in available]
    rows = [
        dict(row)
        for row in connection.execute(
            text(f"SELECT {', '.join(columns)} FROM {table}")
        )
        .mappings()
        .all()
    ]
    if table == "users":
        for row in rows:
            row.setdefault("password_scheme", "scrypt")
            row.setdefault("role_id", row.get("role") or "citizen")
    return rows


def _normalize_user_rows(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        row["notifications_enabled"] = bool(row["notifications_enabled"])
        created_at = row["created_at"]
        if isinstance(created_at, str):
            row["created_at"] = datetime.fromisoformat(created_at)


def _insert_rows(
    connection: Connection, table: str, rows: list[dict[str, Any]]
) -> int:
    if not rows:
        return 0
    columns = TABLES[table]
    column_sql = ", ".join(columns)
    values_sql = ", ".join(f":{column}" for column in columns)
    result = connection.execute(
        text(
            f"INSERT INTO {table} ({column_sql}) "
            f"VALUES ({values_sql}) ON CONFLICT DO NOTHING"
        ),
        rows,
    )
    return result.rowcount


def migrate(source_path: Path, target_engine: Engine) -> dict[str, int]:
    if not source_path.is_file():
        raise FileNotFoundError(f"No existe la base SQLite: {source_path}")

    source_engine = create_engine(URL.create("sqlite", database=str(source_path)))
    try:
        with source_engine.connect() as source, target_engine.begin() as target:
            user_rows = _read_rows(source, "users")
            _normalize_user_rows(user_rows)
            role_names = {
                row["role_id"] or row.get("role") or "citizen"
                for row in user_rows
            }
            copied = {
                "roles": _insert_rows(
                    target,
                    "roles",
                    [{"id": name, "name": name} for name in sorted(role_names)],
                )
            }
            copied["users"] = _insert_rows(target, "users", user_rows)
            for table in ("sessions", "admin_invites"):
                copied[table] = _insert_rows(target, table, _read_rows(source, table))
            return copied
    finally:
        source_engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Copia cuentas, perfiles, sesiones e invitaciones de SQLite a Supabase."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DATABASE_PATH,
        help="Ruta del archivo SQLite de origen.",
    )
    args = parser.parse_args()
    if not SUPABASE_DATABASE_URL:
        parser.error("Configura SUPABASE_DATABASE_URL en el entorno del backend.")

    target_engine = create_database_engine(SUPABASE_DATABASE_URL)
    try:
        initialize_database(target_engine)
        copied = migrate(args.source, target_engine)
    finally:
        target_engine.dispose()

    for table, count in copied.items():
        print(f"{table}: {count} registros insertados o ya existentes")


if __name__ == "__main__":
    main()
