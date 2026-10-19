import sqlite3

from fastapi import APIRouter, Depends

from backend.airea_api.api.dependencies import get_database


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check(
    connection: sqlite3.Connection = Depends(get_database),
) -> dict[str, str]:
    connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}
