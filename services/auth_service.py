import re
import time
from collections.abc import Mapping
from typing import Any

from sqlalchemy.engine import Connection, Transaction
from sqlalchemy.exc import IntegrityError

from core.config import (
    ADMIN_SETUP_TOKEN,
    ALLOWED_HEALTH_PROFILES,
    EMAIL_PATTERN,
)
from core.security import (
    constant_time_equal,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_admin_invite_token,
    verify_password,
)
from repositories import invitations, sessions, users
from schemas.auth import (
    BootstrapAdminRequest,
    ProfileUpdateRequest,
    RegisterRequest,
)
from services.errors import ServiceError


def serialize_user(row: Mapping[str, Any]) -> dict[str, str | bool]:
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


def _transaction(connection: Connection) -> Transaction:
    if connection.in_transaction():
        return connection.begin_nested()
    return connection.begin()


def register(
    connection: Connection, payload: RegisterRequest
) -> tuple[dict[str, str | bool], str]:
    fields = _normalize_registration(payload)
    invite_code = (payload.inviteCode or "").strip()
    if len(invite_code) > 128:
        raise ServiceError(403, "La invitación no es válida para este correo o ya venció.")
    password_hash = hash_password(payload.password)
    invite_hash = hash_token(invite_code) if invite_code else None

    try:
        with _transaction(connection):
            invite = (
                invitations.find_valid_invite(connection, invite_hash)
                if invite_hash
                else None
            )
            if invite_hash and (
                not invite or invite["email"].lower() != fields["email"]
            ):
                raise ServiceError(
                    403, "La invitación no es válida para este correo o ya venció."
                )
            user_id = users.create_user(
                connection,
                **fields,
                password_salt="",
                password_hash=password_hash,
                password_scheme="bcrypt",
                role="admin" if invite else "citizen",
            )
            if invite_hash:
                invitations.delete_invite(connection, invite_hash)
            token = create_access_token(user_id, "admin" if invite else "citizen")
            sessions.create_session(connection, hash_token(token), user_id)
            row = users.find_by_id(connection, user_id)
    except IntegrityError as error:
        if _is_duplicate_email_error(error):
            raise ServiceError(409, "Ya existe una cuenta con ese correo.") from error
        raise

    return serialize_user(row), token


def bootstrap_admin(
    connection: Connection, payload: BootstrapAdminRequest
) -> tuple[dict[str, str | bool], str]:
    if not ADMIN_SETUP_TOKEN:
        raise ServiceError(
            404, "La configuración inicial de administración no está habilitada."
        )
    if not constant_time_equal(payload.setupToken, ADMIN_SETUP_TOKEN):
        raise ServiceError(403, "No se pudo verificar el código de configuración.")

    fields = _normalize_registration(payload)
    password_hash = hash_password(payload.password)
    try:
        with _transaction(connection):
            if users.has_admin(connection):
                raise ServiceError(
                    409, "El administrador inicial ya fue configurado."
                )
            user_id = users.create_user(
                connection,
                **fields,
                password_salt="",
                password_hash=password_hash,
                password_scheme="bcrypt",
                role="admin",
            )
            token = create_access_token(user_id, "admin")
            sessions.create_session(connection, hash_token(token), user_id)
            row = users.find_by_id(connection, user_id)
    except IntegrityError as error:
        if _is_duplicate_email_error(error):
            raise ServiceError(409, "Ya existe una cuenta con ese correo.") from error
        raise
    return serialize_user(row), token


def login(
    connection: Connection, email: str, password: str
) -> tuple[dict[str, str | bool], str]:
    normalized_email = email.strip().lower()
    if not re.fullmatch(EMAIL_PATTERN, normalized_email) or len(password) > 256:
        raise ServiceError(400, "Correo o contraseña incorrectos.")
    row = users.find_by_email(connection, normalized_email)
    if not row or not verify_password(
        password,
        row["password_scheme"],
        row["password_salt"],
        row["password_hash"],
    ):
        raise ServiceError(401, "Correo o contraseña incorrectos.")
    token = create_access_token(row["id"], row["role"])
    with _transaction(connection):
        if row["password_scheme"] == "scrypt":
            users.update_password_hash(
                connection,
                user_id=row["id"],
                password_hash=hash_password(password),
                password_scheme="bcrypt",
            )
        sessions.create_session(connection, hash_token(token), row["id"])
    return serialize_user(row), token


def restore_session(
    connection: Connection, token: str | None
) -> dict[str, str | bool] | None:
    if not token:
        return None
    try:
        claims = decode_access_token(token)
    except ValueError:
        return None
    row = users.find_by_session_token(
        connection, hash_token(token), int(time.time() * 1000)
    )
    if not row or row["id"] != claims["sub"] or row["role"] != claims["role"]:
        return None
    return serialize_user(row) if row else None


def update_profile(
    connection: Connection, user_id: str, payload: ProfileUpdateRequest
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
    with _transaction(connection):
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


def logout(connection: Connection, token: str | None) -> None:
    if token:
        with _transaction(connection):
            sessions.delete_session(connection, hash_token(token))


def create_admin_invite(connection: Connection, email: str) -> dict[str, str | int]:
    normalized_email = email.strip().lower()
    if not re.fullmatch(EMAIL_PATTERN, normalized_email) or len(normalized_email) > 254:
        raise ServiceError(400, "Escribe un correo electrónico válido.")
    if invitations.email_has_account(connection, normalized_email):
        raise ServiceError(409, "Ya existe una cuenta con ese correo.")
    invite_code = new_admin_invite_token()
    expires_at = int((time.time() + 7 * 24 * 60 * 60) * 1000)
    with _transaction(connection):
        invitations.create_invite(
            connection, hash_token(invite_code), normalized_email, expires_at
        )
    return {
        "inviteCode": invite_code,
        "email": normalized_email,
        "expiresAt": expires_at,
    }


def _is_duplicate_email_error(error: IntegrityError) -> bool:
    original = error.orig
    constraint_name = getattr(getattr(original, "diag", None), "constraint_name", "")
    return (
        constraint_name == "users_email_key"
        or "users.email" in str(original).lower()
        or "users_email_key" in str(original).lower()
    )
