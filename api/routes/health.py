from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from api.dependencies import get_database


router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health_check(
    connection: Connection = Depends(get_database),
) -> dict[str, str]:
    connection.execute(text("SELECT 1")).fetchone()
    return {"status": "ok"}
