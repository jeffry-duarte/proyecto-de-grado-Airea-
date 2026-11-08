import logging
import math
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from core.config import AIR_QUALITY_API
from core.rate_limit import rate_limit


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["air quality"])
AIR_QUALITY_FIELDS = (
    "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,us_aqi"
)


def validate_coordinates(value: str, minimum: float, maximum: float) -> list[str]:
    coordinates = value.split(",")
    if not 1 <= len(coordinates) <= 50:
        raise HTTPException(status_code=400, detail="Ubicaciones no válidas.")
    for coordinate in coordinates:
        if not coordinate or len(coordinate) > 20:
            raise HTTPException(status_code=400, detail="Ubicaciones no válidas.")
        try:
            number = float(coordinate)
        except ValueError as error:
            raise HTTPException(
                status_code=400, detail="Ubicaciones no válidas."
            ) from error
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise HTTPException(status_code=400, detail="Ubicaciones no válidas.")
    return coordinates


@router.get(
    "/air-quality",
    dependencies=[Depends(rate_limit(60, 60))],
)
async def get_air_quality(
    latitude: str = Query(),
    longitude: str = Query(),
) -> Any:
    latitudes = validate_coordinates(latitude, -90, 90)
    longitudes = validate_coordinates(longitude, -180, 180)
    if len(latitudes) != len(longitudes):
        raise HTTPException(status_code=400, detail="Ubicaciones no válidas.")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": AIR_QUALITY_FIELDS,
        "timezone": "America/Bogota",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            upstream = await client.get(AIR_QUALITY_API, params=params)
    except httpx.HTTPError as error:
        logger.warning("La fuente Open-Meteo no respondió: %s", error)
        raise HTTPException(
            status_code=502,
            detail="La fuente de calidad del aire no está disponible.",
        ) from error
    if not upstream.is_success:
        raise HTTPException(
            status_code=502,
            detail="La fuente de calidad del aire no está disponible.",
        )
    try:
        return upstream.json()
    except ValueError as error:
        logger.warning("Open-Meteo devolvió una respuesta JSON no válida.")
        raise HTTPException(
            status_code=502,
            detail="La fuente de calidad del aire no está disponible.",
        ) from error


@router.get(
    "/air-quality/forecast",
    dependencies=[Depends(rate_limit(30, 60))],
)
async def get_air_quality_forecast(
    latitude: str = Query(),
    longitude: str = Query(),
) -> Any:
    latitudes = validate_coordinates(latitude, -90, 90)
    longitudes = validate_coordinates(longitude, -180, 180)
    if len(latitudes) != 1 or len(longitudes) != 1:
        raise HTTPException(status_code=400, detail="Ubicación no válida.")

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "pm2_5,us_aqi",
        "forecast_days": 5,
        "timezone": "America/Bogota",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            upstream = await client.get(AIR_QUALITY_API, params=params)
    except httpx.HTTPError as error:
        logger.warning("El pronóstico Open-Meteo no respondió: %s", error)
        raise HTTPException(
            status_code=502,
            detail="El pronóstico de calidad del aire no está disponible.",
        ) from error
    if not upstream.is_success:
        raise HTTPException(
            status_code=502,
            detail="El pronóstico de calidad del aire no está disponible.",
        )
    try:
        return upstream.json()
    except ValueError as error:
        logger.warning("Open-Meteo devolvió un pronóstico JSON no válido.")
        raise HTTPException(
            status_code=502,
            detail="El pronóstico de calidad del aire no está disponible.",
        ) from error
