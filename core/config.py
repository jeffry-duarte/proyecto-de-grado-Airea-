import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / "services" / ".env")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IS_PRODUCTION = os.getenv("NODE_ENV", "").lower() == "production"
HOST = os.getenv("HOST", "0.0.0.0" if IS_PRODUCTION else "127.0.0.1")
PORT = int(os.getenv("PORT", "3000" if IS_PRODUCTION else "8000"))
DATABASE_PATH = Path(
    os.getenv("AIREA_DB_PATH", str(PROJECT_ROOT / "data" / "airea.sqlite"))
).expanduser()
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = (PROJECT_ROOT / DATABASE_PATH).resolve()

PUBLIC_ORIGIN = os.getenv("AIREA_PUBLIC_ORIGIN", "").rstrip("/")
ADMIN_SETUP_TOKEN = os.getenv("AIREA_ADMIN_SETUP_TOKEN", "")
SECURE_COOKIES = os.getenv(
    "AIREA_SECURE_COOKIES", "true" if IS_PRODUCTION else "false"
).lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE = "airea_session"
SESSION_LIFETIME_SECONDS = 60 * 60 * 24
ALLOWED_HEALTH_PROFILES = {"general", "cyclist", "respiratory", "elderly"}
EMAIL_PATTERN = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
AIR_QUALITY_API = "https://air-quality-api.open-meteo.com/v1/air-quality"
FRONTEND_DIST = PROJECT_ROOT / "dist"
