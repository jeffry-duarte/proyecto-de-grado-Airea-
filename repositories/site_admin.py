import json
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.engine.row import RowMapping


def list_notices(connection: Connection, *, published_only: bool = False) -> list[RowMapping]:
    where_clause = "WHERE published = TRUE" if published_only else ""
    return list(
        connection.execute(
            text(f"""
                SELECT id, title, body, severity, published, created_at, updated_at
                FROM site_notices
                {where_clause}
                ORDER BY updated_at DESC
            """)
        ).mappings()
    )


def save_notice(
    connection: Connection,
    *,
    notice_id: str | None,
    title: str,
    body: str,
    severity: str,
    published: bool,
) -> RowMapping:
    now = datetime.now(timezone.utc)
    if notice_id:
        connection.execute(
            text("""
                UPDATE site_notices
                SET title = :title, body = :body, severity = :severity,
                    published = :published, updated_at = :updated_at
                WHERE id = :id
            """),
            {
                "id": notice_id,
                "title": title,
                "body": body,
                "severity": severity,
                "published": published,
                "updated_at": now,
            },
        )
        return connection.execute(
            text("SELECT * FROM site_notices WHERE id = :id"),
            {"id": notice_id},
        ).mappings().one()

    new_id = uuid4().hex
    connection.execute(
        text("""
            INSERT INTO site_notices (
                id, title, body, severity, published, created_at, updated_at
            ) VALUES (
                :id, :title, :body, :severity, :published, :created_at, :updated_at
            )
        """),
        {
            "id": new_id,
            "title": title,
            "body": body,
            "severity": severity,
            "published": published,
            "created_at": now,
            "updated_at": now,
        },
    )
    return connection.execute(
        text("SELECT * FROM site_notices WHERE id = :id"),
        {"id": new_id},
    ).mappings().one()


def delete_notice(connection: Connection, notice_id: str) -> bool:
    result = connection.execute(
        text("DELETE FROM site_notices WHERE id = :id"),
        {"id": notice_id},
    )
    return result.rowcount > 0


def list_station_overrides(connection: Connection) -> list[RowMapping]:
    return list(
        connection.execute(
            text("""
                SELECT station_id, name, zone, active, updated_at
                FROM station_overrides ORDER BY station_id
            """)
        ).mappings()
    )


def save_station_override(
    connection: Connection,
    *,
    station_id: str,
    name: str,
    zone: str,
    active: bool,
) -> RowMapping:
    now = datetime.now(timezone.utc)
    connection.execute(
        text("""
            INSERT INTO station_overrides (station_id, name, zone, active, updated_at)
            VALUES (:station_id, :name, :zone, :active, :updated_at)
            ON CONFLICT (station_id) DO UPDATE SET
                name = excluded.name, zone = excluded.zone,
                active = excluded.active, updated_at = excluded.updated_at
        """),
        {
            "station_id": station_id,
            "name": name,
            "zone": zone,
            "active": active,
            "updated_at": now,
        },
    )
    return connection.execute(
        text("SELECT * FROM station_overrides WHERE station_id = :station_id"),
        {"station_id": station_id},
    ).mappings().one()


def delete_station_override(connection: Connection, station_id: str) -> bool:
    result = connection.execute(
        text("DELETE FROM station_overrides WHERE station_id = :station_id"),
        {"station_id": station_id},
    )
    return result.rowcount > 0


def get_setting(connection: Connection, setting_key: str) -> dict | None:
    row = connection.execute(
        text("SELECT setting_value FROM site_settings WHERE setting_key = :key"),
        {"key": setting_key},
    ).mappings().first()
    return json.loads(row["setting_value"]) if row else None


def save_setting(connection: Connection, setting_key: str, value: dict) -> None:
    connection.execute(
        text("""
            INSERT INTO site_settings (setting_key, setting_value, updated_at)
            VALUES (:key, :value, :updated_at)
            ON CONFLICT (setting_key) DO UPDATE SET
                setting_value = excluded.setting_value,
                updated_at = excluded.updated_at
        """),
        {
            "key": setting_key,
            "value": json.dumps(value, separators=(",", ":"), sort_keys=True),
            "updated_at": datetime.now(timezone.utc),
        },
    )
