import sqlite3

from fastapi import APIRouter, Depends

from backend.airea_api.api.dependencies import (
    get_admin_user,
    get_database,
    verify_same_origin,
)
from backend.airea_api.core.rate_limit import rate_limit
from backend.airea_api.schemas.auth import AdminInviteRequest
from backend.airea_api.services.auth_service import create_admin_invite


router = APIRouter(prefix="/api/admin", tags=["administration"])


@router.post(
    "/invites",
    status_code=201,
    dependencies=[
        Depends(rate_limit(8, 15 * 60)),
        Depends(verify_same_origin),
    ],
)
def create_invite(
    payload: AdminInviteRequest,
    _admin: sqlite3.Row = Depends(get_admin_user),
    connection: sqlite3.Connection = Depends(get_database),
) -> dict:
    return create_admin_invite(connection, payload.email)
