from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from api.dependencies import get_database
from services import admin_service


router = APIRouter(prefix="/api/site", tags=["site configuration"])


@router.get("/config")
def get_site_config(
    connection: Connection = Depends(get_database),
) -> dict:
    return admin_service.get_public_config(connection)


@router.get("/notices")
def get_site_notices(
    connection: Connection = Depends(get_database),
) -> list[dict]:
    return admin_service.get_public_notices(connection)
