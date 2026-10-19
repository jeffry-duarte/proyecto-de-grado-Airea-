import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from backend.airea_api.api.routes import admin, air_quality, auth, health
from backend.airea_api.core.config import DATABASE_PATH, FRONTEND_DIST, IS_PRODUCTION
from backend.airea_api.core.request_size_limit import RequestSizeLimitMiddleware
from backend.airea_api.db.database import initialize_database
from backend.airea_api.services.errors import ServiceError


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.database_path = DATABASE_PATH
    initialize_database()
    yield


app = FastAPI(
    title="AIREA API",
    version="1.0.0",
    docs_url=None if IS_PRODUCTION else "/api/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/api/openapi.json",
    lifespan=lifespan,
)
app.add_middleware(RequestSizeLimitMiddleware)
logger = logging.getLogger(__name__)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    response.headers["Cache-Control"] = "no-store"
    if IS_PRODUCTION and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.exception_handler(HTTPException)
async def http_error_handler(
    _request: Request, error: HTTPException
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": error.detail},
        headers=error.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    _request: Request, _error: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "Revisa los datos enviados."},
    )


@app.exception_handler(ServiceError)
async def service_error_handler(
    _request: Request, error: ServiceError
) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={"error": error.message},
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(
    _request: Request, error: Exception
) -> JSONResponse:
    logger.error(
        "Request failed",
        exc_info=(type(error), error, error.__traceback__),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Ocurrió un error interno. Inténtalo de nuevo."},
    )


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(air_quality.router)
app.include_router(health.router)


def api_not_found() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "Servicio no encontrado."},
    )


@app.api_route(
    "/api",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
def unknown_api_root() -> JSONResponse:
    return api_not_found()


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    include_in_schema=False,
)
def unknown_api_route(path: str) -> JSONResponse:
    return api_not_found()


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=503, detail="Frontend no disponible.")
    return FileResponse(index_path)


@app.get("/{path:path}", include_in_schema=False)
def frontend_route(path: str) -> FileResponse:
    root = FRONTEND_DIST.resolve()
    requested_file = (root / path).resolve()
    if requested_file.is_relative_to(root) and requested_file.is_file():
        return FileResponse(requested_file)
    if Path(path).suffix:
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    index_path = root / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=503, detail="Frontend no disponible.")
    return FileResponse(index_path)
