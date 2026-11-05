import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import Request
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Connection, Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from backend.airea_api.core.config import (
    IS_PRODUCTION,
    SUPABASE_DATABASE_URL,
    TEST_DATABASE_URL,
)


def _database_url() -> str | URL:
    if TEST_DATABASE_URL:
        if os.getenv("AIREA_TEST_MODE") != "1":
            raise RuntimeError(
                "AIREA_TEST_DATABASE_URL solo se permite con AIREA_TEST_MODE=1."
            )
        if not TEST_DATABASE_URL.startswith("sqlite:///"):
            raise RuntimeError(
                "AIREA_TEST_DATABASE_URL solo admite una base SQLite de pruebas."
            )
        return TEST_DATABASE_URL

    if SUPABASE_DATABASE_URL:
        url = SUPABASE_DATABASE_URL
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url.removeprefix("postgresql://")
        if not url.startswith("postgresql+psycopg://"):
            raise RuntimeError(
                "SUPABASE_DATABASE_URL debe ser una URL PostgreSQL de Supabase."
            )
        return url

    environment = "producción" if IS_PRODUCTION else "desarrollo"
    raise RuntimeError(
        f"Configura SUPABASE_DATABASE_URL para ejecutar el backend en {environment}."
    )


def _normalize_postgres_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if not url.startswith("postgresql+psycopg://"):
        raise RuntimeError(
            "SUPABASE_DATABASE_URL debe ser una URL PostgreSQL de Supabase."
        )
    return url


def create_database_engine(database_url: str | URL | None = None) -> Engine:
    database_url = _database_url() if database_url is None else database_url
    if isinstance(database_url, str) and not database_url.startswith("sqlite:"):
        database_url = _normalize_postgres_url(database_url)
    is_postgres = (
        database_url.drivername.startswith("postgresql")
        if isinstance(database_url, URL)
        else database_url.startswith("postgresql")
    )
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "prepare_threshold": None,
            "sslmode": "require",
        } if is_postgres else {},
    )
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: Any, _connection_record: Any
        ) -> None:
            dbapi_connection.execute("PRAGMA foreign_keys = ON")

    return engine


def initialize_database(engine: Engine) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    schema_statements = schema_path.read_text(encoding="utf-8").split(";")
    try:
        with engine.begin() as connection:
            for statement in schema_statements:
                if statement.strip():
                    connection.exec_driver_sql(statement)
            if engine.dialect.name == "postgresql":
                for table in (
                    "users",
                    "sessions",
                    "admin_invites",
                    "site_notices",
                    "station_overrides",
                    "site_settings",
                ):
                    connection.exec_driver_sql(
                        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"
                    )
    except SQLAlchemyError as error:
        raise RuntimeError(
            "No se pudo inicializar el esquema de la base de datos. Verifica "
            "SUPABASE_DATABASE_URL y los permisos de la base."
        ) from error


def database_dependency(request: Request) -> Iterator[Connection]:
    connection = request.app.state.database_engine.connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
