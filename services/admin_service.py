import re
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from backend.airea_api.core.config import ALLOWED_HEALTH_PROFILES, EMAIL_PATTERN
from backend.airea_api.repositories import invitations, site_admin, users
from backend.airea_api.schemas.admin import (
    AdminUserUpdateRequest,
    AirQualityThresholdsRequest,
    NoticeRequest,
    StationOverrideRequest,
)
from backend.airea_api.services import auth_service
from backend.airea_api.services.errors import ServiceError


DEFAULT_THRESHOLDS = {"moderate": 50, "sensitive": 100, "high": 150}
STATION_IDS = {
    "RMCAB-BOG-16",
    "CAR-SOA-02",
    "RMCAB-BOG-09",
    "RMCAB-BOG-04",
    "RMCAB-BOG-11",
    "RMCAB-BOG-08",
    "RMCAB-BOG-01",
    "CAR-CHI-05",
    "CAR-ZIP-01",
    "CAR-CAJ-03",
    "RMCAB-BOG-03",
    "RMCAB-BOG-07",
    "RMCAB-BOG-12",
    "CAR-MOS-04",
}


def _iso_timestamp(value: Any) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _serialize_notice(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "severity": row["severity"],
        "published": bool(row["published"]),
        "createdAt": _iso_timestamp(row["created_at"]),
        "updatedAt": _iso_timestamp(row["updated_at"]),
    }


def _serialize_station(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "stationId": row["station_id"],
        "name": row["name"],
        "zone": row["zone"],
        "active": bool(row["active"]),
        "updatedAt": _iso_timestamp(row["updated_at"]),
    }


def get_admin_dashboard(connection: Connection) -> dict[str, Any]:
    pending_invites = invitations.list_pending_invites(connection)
    return {
        "users": [auth_service.serialize_user(row) | {
            "createdAt": _iso_timestamp(row["created_at"])
        } for row in users.list_for_admin(connection)],
        "invites": [
            {"email": row["email"], "expiresAt": row["expires_at"]}
            for row in pending_invites
        ],
        "notices": [
            _serialize_notice(row) for row in site_admin.list_notices(connection)
        ],
        "stationOverrides": [
            _serialize_station(row)
            for row in site_admin.list_station_overrides(connection)
        ],
        "thresholds": site_admin.get_setting(connection, "air_quality_thresholds")
        or DEFAULT_THRESHOLDS,
    }


def update_user(
    connection: Connection,
    user_id: str,
    payload: AdminUserUpdateRequest,
    admin: Mapping[str, Any],
) -> dict[str, str | bool]:
    name = payload.name.strip()
    locality = payload.locality.strip()
    station_id = payload.favoriteStationId.strip()
    if not 2 <= len(name) <= 100:
        raise ServiceError(400, "El nombre debe tener entre 2 y 100 caracteres.")
    if not locality or len(locality) > 100 or not station_id or len(station_id) > 80:
        raise ServiceError(400, "Revisa la localidad y la estación favorita.")
    if payload.healthProfile not in ALLOWED_HEALTH_PROFILES:
        raise ServiceError(400, "Selecciona un perfil de salud válido.")

    with connection.begin_nested() if connection.in_transaction() else connection.begin():
        target = users.find_by_id(connection, user_id)
        if not target:
            raise ServiceError(404, "No se encontró esa cuenta.")
        if target["id"] == admin["id"] and payload.role != "admin":
            raise ServiceError(409, "No puedes quitarte tu propio rol de administrador.")
        if target["role"] == "admin" and payload.role != "admin":
            admin_count = connection.execute(
                text("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            ).scalar_one()
            if admin_count <= 1:
                raise ServiceError(
                    409, "Debe permanecer al menos una cuenta administradora."
                )
        updated = users.update_for_admin(
            connection,
            user_id=user_id,
            name=name,
            locality=locality,
            favorite_station_id=station_id,
            health_profile=payload.healthProfile,
            notifications_enabled=payload.notificationsEnabled,
            role=payload.role,
        )
    return auth_service.serialize_user(updated)


def list_invites(connection: Connection) -> list[dict[str, str | int]]:
    return [
        {"email": row["email"], "expiresAt": row["expires_at"]}
        for row in invitations.list_pending_invites(connection)
    ]


def revoke_invite(connection: Connection, email: str) -> None:
    normalized_email = email.strip().lower()
    if not re.fullmatch(EMAIL_PATTERN, normalized_email) or len(normalized_email) > 254:
        raise ServiceError(400, "Escribe un correo electrónico válido.")
    invitations.delete_invites_for_email(connection, normalized_email)


def save_notice(
    connection: Connection, notice_id: str | None, payload: NoticeRequest
) -> dict[str, Any]:
    if notice_id and not any(
        row["id"] == notice_id for row in site_admin.list_notices(connection)
    ):
        raise ServiceError(404, "No se encontró ese aviso.")
    row = site_admin.save_notice(
        connection,
        notice_id=notice_id,
        title=payload.title.strip(),
        body=payload.body.strip(),
        severity=payload.severity,
        published=payload.published,
    )
    return _serialize_notice(row)


def delete_notice(connection: Connection, notice_id: str) -> None:
    if not site_admin.delete_notice(connection, notice_id):
        raise ServiceError(404, "No se encontró ese aviso.")


def save_station(
    connection: Connection,
    station_id: str,
    payload: StationOverrideRequest,
) -> dict[str, Any]:
    if station_id not in STATION_IDS:
        raise ServiceError(404, "No se encontró esa estación.")
    if not payload.active:
        inactive_overrides = {
            row["station_id"]
            for row in site_admin.list_station_overrides(connection)
            if not row["active"]
        }
        active_count = len(STATION_IDS - inactive_overrides)
        if station_id not in inactive_overrides and active_count <= 1:
            raise ServiceError(409, "Debe permanecer al menos una estación activa.")
    row = site_admin.save_station_override(
        connection,
        station_id=station_id,
        name=payload.name.strip(),
        zone=payload.zone.strip(),
        active=payload.active,
    )
    return _serialize_station(row)


def reset_station(
    connection: Connection, station_id: str
) -> None:
    if station_id not in STATION_IDS:
        raise ServiceError(404, "No se encontró esa estación.")
    site_admin.delete_station_override(connection, station_id)


def save_thresholds(
    connection: Connection, payload: AirQualityThresholdsRequest
) -> dict[str, int]:
    thresholds = payload.model_dump()
    site_admin.save_setting(connection, "air_quality_thresholds", thresholds)
    return thresholds


def get_public_config(connection: Connection) -> dict[str, Any]:
    return {
        "stationOverrides": [
            _serialize_station(row)
            for row in site_admin.list_station_overrides(connection)
        ],
        "thresholds": site_admin.get_setting(connection, "air_quality_thresholds")
        or DEFAULT_THRESHOLDS,
        "notices": get_public_notices(connection),
    }


def get_public_notices(connection: Connection) -> list[dict[str, Any]]:
    return [
        _serialize_notice(row)
        for row in site_admin.list_notices(connection, published_only=True)
    ]
