import re
import sqlite3
import time

from backend.airea_api.core.config import (
    ADMIN_SETUP_TOKEN,
    ALLOWED_HEALTH_PROFILES,
    EMAIL_PATTERN,
)
from backend.airea_api.core.security import (
    constant_time_equal,
    hash_password,
    hash_token,
    new_admin_invite_token,
    new_session_token,
    verify_password,
)
from backend.airea_api.repositories import invitations, sessions, users
from backend.airea_api.schemas.auth import (
    BootstrapAdminRequest,
    ProfileUpdateRequest,
    RegisterRequest,
)
from backend.airea_api.services.errors import ServiceError


def serialize_user(row: sqlite3.Row) -> dict[str, str | bool]:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "locality": row["locality"],
        "favoriteStationId": row["favorite_station_id"],
        "healthProfile": row["health_profile"],
        "notificationsEnabled": bool(row["notifications_enabled"]),
        "role": row["role"],
        "avatarColor": "#14532d" if row["role"] == "admin" else "#0F172A",
    }


def _normalize_registration(payload: RegisterRequest) -> dict:
    name = payload.name.strip()
    email = payload.email.strip().lower()
    locality = payload.locality.strip()
    station_id = payload.favoriteStationId.strip()
    if not 2 <= len(name) <= 100 or not re.fullmatch(EMAIL_PATTERN, email) or len(email) > 254:
        raise ServiceError(400, "Revisa tu nombre y correo electrónico.")
    if not 12 <= len(payload.password) <= 256:
        raise ServiceError(400, "La contraseña debe tener entre 12 y 256 caracteres.")
    if not locality or len(locality) > 100 or not station_id or len(station_id) > 80:
        raise ServiceError(400, "Selecciona una localidad y una estación favorita.")
    if payload.healthProfile not in ALLOWED_HEALTH_PROFILES:
        raise ServiceError(400, "Selecciona un perfil de salud válido.")
    return {
        "name": name,
        "email": email,
        "locality": locality,
        "favorite_station_id": station_id,
        "health_profile": payload.healthProfile,
        "notifications_enabled": payload.notificationsEnabled,
    }


def register(
    connection: sqlite3.Connection, payload: RegisterRequest
) -> tuple[dict[str, str | bool], str]:
    fields = _normalize_registration(payload)
    invite_code = (payload.inviteCode or "").strip()
    if len(invite_code) > 128:
        raise ServiceError(403, "La invitación no es válida para este correo o ya venció.")
    password_salt, password_hash = hash_password(payload.password)
    invite_hash = hash_token(invite_code) if invite_code else None

    try:
        connection.execute("BEGIN IMMEDIATE")
        invite = invitations.find_valid_invite(connection, invite_hash) if invite_hash else None
        if invite_hash and (
            not invite or invite["email"].lower() != fields["email"]
        ):
            raise ServiceError(403, "La invitación no es válida para este correo o ya venció.")
        user_id = users.create_user(
            connection,
            **fields,
            password_salt=password_salt,
            password_hash=password_hash,
            role="admin" if invite else "citizen",
        )
        if invite_hash:
            invitations.delete_invite(connection, invite_hash)
        token = new_session_token()
        sessions.create_session(connection, hash_token(token), user_id)
        row = users.find_by_id(connection, user_id)
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        if "users.email" in str(error).lower() or "unique" in str(error).lower():
            raise ServiceError(409, "Ya existe una cuenta con ese correo.") from error
        raise
    except Exception:
        connection.rollback()
        raise

    return serialize_user(row), token


def bootstrap_admin(
    connection: sqlite3.Connection, payload: BootstrapAdminRequest
) -> tuple[dict[str, str | bool], str]:
    if not ADMIN_SETUP_TOKEN:
        raise ServiceError(
            404, "La configuración inicial de administración no está habilitada."
        )
    if not constant_time_equal(payload.setupToken, ADMIN_SETUP_TOKEN):
        raise ServiceError(403, "No se pudo verificar el código de configuración.")

    fields = _normalize_registration(payload)
    password_salt, password_hash = hash_password(payload.password)
    try:
        connection.execute("BEGIN IMMEDIATE")
        if users.has_admin(connection):
            raise ServiceError(409, "El administrador inicial ya fue configurado.")
        user_id = users.create_user(
            connection,
            **fields,
            password_salt=password_salt,
            password_hash=password_hash,
            role="admin",
        )
        token = new_session_token()
        sessions.create_session(connection, hash_token(token), user_id)
        row = users.find_by_id(connection, user_id)
        connection.commit()
    except sqlite3.IntegrityError as error:
        connection.rollback()
        if "unique" in str(error).lower():
            raise ServiceError(409, "Ya existe una cuenta con ese correo.") from error
        raise
    except Exception:
        connection.rollback()
        raise
    return serialize_user(row), token


def login(
    connection: sqlite3.Connection, email: str, password: str
) -> tuple[dict[str, str | bool], str]:
    normalized_email = email.strip().lower()
    if not re.fullmatch(EMAIL_PATTERN, normalized_email) or len(password) > 256:
        raise ServiceError(400, "Correo o contraseña incorrectos.")
    row = users.find_by_email(connection, normalized_email)
    if not row or not verify_password(
        password, row["password_salt"], row["password_hash"]
    ):
        raise ServiceError(401, "Correo o contraseña incorrectos.")
    token = new_session_token()
    with connection:
        sessions.create_session(connection, hash_token(token), row["id"])
    return serialize_user(row), token


def restore_session(
    connection: sqlite3.Connection, token: str | None
) -> dict[str, str | bool] | None:
    if not token:
        return None
    row = users.find_by_session_token(
        connection, hash_token(token), int(time.time() * 1000)
    )
    return serialize_user(row) if row else None


def update_profile(
    connection: sqlite3.Connection, user_id: str, payload: ProfileUpdateRequest
) -> dict[str, str | bool]:
    locality = payload.locality.strip()
    station_id = payload.favoriteStationId.strip()
    if (
        not locality
        or len(locality) > 100
        or not station_id
        or len(station_id) > 80
        or payload.healthProfile not in ALLOWED_HEALTH_PROFILES
    ):
        raise ServiceError(400, "Revisa los datos del perfil.")
    with connection:
        users.update_profile(
            connection,
            user_id=user_id,
            locality=locality,
            favorite_station_id=station_id,
            health_profile=payload.healthProfile,
            notifications_enabled=payload.notificationsEnabled,
        )
        row = users.find_by_id(connection, user_id)
    return serialize_user(row)


def logout(connection: sqlite3.Connection, token: str | None) -> None:
    if token:
        with connection:
            sessions.delete_session(connection, hash_token(token))


def create_admin_invite(connection: sqlite3.Connection, email: str) -> dict[str, str | int]:
    normalized_email = email.strip().lower()
    if not re.fullmatch(EMAIL_PATTERN, normalized_email) or len(normalized_email) > 254:
        raise ServiceError(400, "Escribe un correo electrónico válido.")
    if invitations.email_has_account(connection, normalized_email):
        raise ServiceError(409, "Ya existe una cuenta con ese correo.")
    invite_code = new_admin_invite_token()
    expires_at = int((time.time() + 7 * 24 * 60 * 60) * 1000)
    with connection:
        invitations.create_invite(
            connection, hash_token(invite_code), normalized_email, expires_at
        )
    return {
        "inviteCode": invite_code,
        "email": normalized_email,
        "expiresAt": expires_at,
    }
