import time
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.engine import Connection

from core.config import (
    PUBLIC_ORIGINS,
    SESSION_COOKIE,
    SESSION_LIFETIME_SECONDS,
    SECURE_COOKIES,
)
from db.database import database_dependency
from repositories import users
from core.security import decode_access_token, hash_token


def get_database(
    connection: Connection = Depends(database_dependency),
) -> Connection:
    return connection


def verify_same_origin(request: Request) -> None:
    if not request.headers.get("content-type", "").lower().startswith(
        "application/json"
    ):
        raise HTTPException(status_code=415, detail="Se requiere una solicitud JSON.")

    origin = request.headers.get("origin")
    if not origin:
        raise HTTPException(
            status_code=403,
            detail="No se pudo verificar el origen de la solicitud.",
        )
    try:
        parsed_origin = urlsplit(origin)
        expected_origins = PUBLIC_ORIGINS or (
            str(request.base_url).rstrip("/"),
        )
        valid_origin = parsed_origin.scheme in {"http", "https"} and bool(
            parsed_origin.netloc
        ) and not parsed_origin.path and not parsed_origin.query and not parsed_origin.fragment
        if valid_origin:
            valid_origin = any(
                parsed_origin.scheme.lower() == parsed_expected.scheme.lower()
                and parsed_origin.netloc.lower() == parsed_expected.netloc.lower()
                for parsed_expected in map(urlsplit, expected_origins)
            )
    except ValueError:
        valid_origin = False
    if not valid_origin:
        raise HTTPException(status_code=403, detail="Origen no permitido.")


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=SESSION_LIFETIME_SECONDS,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="strict",
        path="/",
    )


def get_current_user(
    request: Request,
    response: Response,
    connection: Connection = Depends(get_database),
) -> Mapping[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    try:
        claims = decode_access_token(token)
    except ValueError:
        clear_session_cookie(response)
        raise HTTPException(
            status_code=401,
            detail="La sesión no es válida. Inicia sesión de nuevo.",
            headers={"Set-Cookie": response.headers["set-cookie"]},
        ) from None
    row = users.find_by_session_token(
        connection, hash_token(token), time.time_ns() // 1_000_000
    )
    if not row or row["id"] != claims["sub"] or row["role"] != claims["role"]:
        clear_session_cookie(response)
        raise HTTPException(
            status_code=401,
            detail="La sesión venció. Inicia sesión de nuevo.",
            headers={"Set-Cookie": response.headers["set-cookie"]},
        )
    return row


def get_admin_user(
    user: Mapping[str, Any] = Depends(get_current_user),
) -> Mapping[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Solo una persona administradora puede invitar a otra.",
        )
    return user
