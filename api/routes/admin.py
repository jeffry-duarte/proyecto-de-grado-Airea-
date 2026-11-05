from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from backend.airea_api.api.dependencies import (
    get_admin_user,
    get_database,
    verify_same_origin,
)
from backend.airea_api.core.rate_limit import rate_limit
from backend.airea_api.schemas.admin import (
    AdminUserUpdateRequest,
    AirQualityThresholdsRequest,
    NoticeRequest,
    StationOverrideRequest,
)
from backend.airea_api.schemas.auth import AdminInviteRequest
from backend.airea_api.services import admin_service, auth_service


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
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return auth_service.create_admin_invite(connection, payload.email)


@router.get("/dashboard")
def get_dashboard(
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return admin_service.get_admin_dashboard(connection)


@router.get("/invites")
def list_invites(
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> list[dict[str, str | int]]:
    return admin_service.list_invites(connection)


@router.delete(
    "/invites",
    dependencies=[Depends(verify_same_origin)],
)
def revoke_invite(
    email: str,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict[str, bool]:
    admin_service.revoke_invite(connection, email)
    return {"ok": True}


@router.patch(
    "/users/{user_id}",
    dependencies=[Depends(verify_same_origin)],
)
def update_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return {
        "user": admin_service.update_user(
            connection, user_id, payload, admin
        )
    }


@router.post(
    "/notices",
    status_code=201,
    dependencies=[Depends(verify_same_origin)],
)
def create_notice(
    payload: NoticeRequest,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return {"notice": admin_service.save_notice(connection, None, payload)}


@router.patch(
    "/notices/{notice_id}",
    dependencies=[Depends(verify_same_origin)],
)
def update_notice(
    notice_id: str,
    payload: NoticeRequest,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return {
        "notice": admin_service.save_notice(connection, notice_id, payload)
    }


@router.delete(
    "/notices/{notice_id}",
    dependencies=[Depends(verify_same_origin)],
)
def delete_notice(
    notice_id: str,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict[str, bool]:
    admin_service.delete_notice(connection, notice_id)
    return {"ok": True}


@router.put(
    "/stations/{station_id}",
    dependencies=[Depends(verify_same_origin)],
)
def update_station(
    station_id: str,
    payload: StationOverrideRequest,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return {
        "station": admin_service.save_station(
            connection, station_id, payload
        )
    }


@router.delete(
    "/stations/{station_id}",
    dependencies=[Depends(verify_same_origin)],
)
def reset_station(
    station_id: str,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict[str, bool]:
    admin_service.reset_station(connection, station_id)
    return {"ok": True}


@router.put(
    "/thresholds",
    dependencies=[Depends(verify_same_origin)],
)
def update_thresholds(
    payload: AirQualityThresholdsRequest,
    _admin: Mapping[str, Any] = Depends(get_admin_user),
    connection: Connection = Depends(get_database),
) -> dict:
    return {"thresholds": admin_service.save_thresholds(connection, payload)}
