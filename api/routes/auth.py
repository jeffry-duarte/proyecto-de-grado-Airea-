import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from backend.airea_api.api.dependencies import (
    clear_session_cookie,
    get_current_user,
    get_database,
    set_session_cookie,
    verify_same_origin,
)
from backend.airea_api.core.config import SESSION_COOKIE
from backend.airea_api.core.rate_limit import rate_limit
from backend.airea_api.repositories import users
from backend.airea_api.schemas.auth import (
    BootstrapAdminRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
)
from backend.airea_api.services import auth_service


router = APIRouter(prefix="/api/auth", tags=["authentication"])
auth_rate_limit = Depends(rate_limit(8, 15 * 60))


@router.get("/me")
def get_current_session(
    request: Request,
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    user = auth_service.restore_session(
        connection, request.cookies.get(SESSION_COOKIE)
    )
    return {"user": user}


@router.post(
    "/register",
    status_code=201,
    dependencies=[auth_rate_limit, Depends(verify_same_origin)],
)
def register(
    payload: RegisterRequest,
    response: Response,
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    user, token = auth_service.register(connection, payload)
    set_session_cookie(response, token)
    return {"user": user}


@router.post(
    "/bootstrap-admin",
    status_code=201,
    dependencies=[auth_rate_limit, Depends(verify_same_origin)],
)
def bootstrap_admin(
    payload: BootstrapAdminRequest,
    response: Response,
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    user, token = auth_service.bootstrap_admin(connection, payload)
    set_session_cookie(response, token)
    return {"user": user}


@router.post(
    "/login",
    dependencies=[auth_rate_limit, Depends(verify_same_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    user, token = auth_service.login(connection, payload.email, payload.password)
    set_session_cookie(response, token)
    return {"user": user}


@router.post("/logout", dependencies=[Depends(verify_same_origin)])
def logout(
    request: Request,
    response: Response,
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    auth_service.logout(connection, request.cookies.get(SESSION_COOKIE))
    clear_session_cookie(response)
    return {"ok": True}


@router.patch(
    "/profile",
    dependencies=[Depends(verify_same_origin)],
)
def update_profile(
    payload: ProfileUpdateRequest,
    current_user: sqlite3.Row = Depends(get_current_user),
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    return {
        "user": auth_service.update_profile(
            connection, current_user["id"], payload
        )
    }
