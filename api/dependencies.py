import sqlite3
import time
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request, Response

from backend.airea_api.core.config import (
    PUBLIC_ORIGINS,
    SESSION_COOKIE,
    SESSION_LIFETIME_SECONDS,
    SECURE_COOKIES,
)
from backend.airea_api.db.database import database_dependency
from backend.airea_api.repositories import users
from backend.airea_api.core.security import hash_token


def get_database(
    connection: sqlite3.Connection = Depends(database_dependency),
) -> sqlite3.Connection:
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
    connection: sqlite3.Connection = Depends(get_database),
) -> sqlite3.Row:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Inicia sesión para continuar.")
    row = users.find_by_session_token(
        connection, hash_token(token), time.time_ns() // 1_000_000
    )
    if not row:
        clear_session_cookie(response)
        raise HTTPException(
            status_code=401,
            detail="La sesión venció. Inicia sesión de nuevo.",
            headers={"Set-Cookie": response.headers["set-cookie"]},
        )
    return row


def get_admin_user(
    user: sqlite3.Row = Depends(get_current_user),
) -> sqlite3.Row:
    if user["role"] != "admin":
        raise HTTPException(
            status_code=403,
            detail="Solo una persona administradora puede invitar a otra.",
        )
    return user
