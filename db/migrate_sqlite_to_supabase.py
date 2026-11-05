import argparse
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine, URL

from backend.airea_api.core.config import DATABASE_PATH, SUPABASE_DATABASE_URL
from backend.airea_api.db.database import (
    create_database_engine,
    initialize_database,
)


TABLES = {
    "users": (
        "id",
        "name",
        "email",
        "password_salt",
        "password_hash",
        "locality",
        "favorite_station_id",
        "health_profile",
        "notifications_enabled",
        "role",
        "created_at",
    ),
    "sessions": ("token_hash", "user_id", "expires_at"),
    "admin_invites": ("token_hash", "email", "expires_at"),
}


def _read_rows(connection: Connection, table: str) -> list[dict[str, Any]]:
    columns = ", ".join(TABLES[table])
    return [
        dict(row)
        for row in connection.execute(text(f"SELECT {columns} FROM {table}"))
        .mappings()
        .all()
    ]


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
            copied: dict[str, int] = {}
            for table, columns in TABLES.items():
                rows = _read_rows(source, table)
                if table == "users":
                    _normalize_user_rows(rows)
                copied[table] = _insert_rows(target, table, rows)
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
