import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _project_path(name: str, default: str) -> str:
    raw = Path(os.getenv(name, default)).expanduser()
    if not raw.is_absolute():
        raw = PROJECT_ROOT / raw
    return str(raw.resolve())


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "")
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

    DATABASE = _project_path("DATABASE_PATH", "backend/instance/portfolio.db")
    UPLOAD_FOLDER = _project_path("UPLOAD_FOLDER", "backend/uploads")
    STAGING_FOLDER = _project_path("STAGING_FOLDER", "backend/instance/staging")
    SEED_DATA_PATH = str((BACKEND_DIR / "data" / "photos.json").resolve())

    MAX_UPLOAD_MB = max(1, int(os.getenv("MAX_UPLOAD_MB", "20")))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    LOGIN_MAX_ATTEMPTS = max(1, int(os.getenv("LOGIN_MAX_ATTEMPTS", "5")))
    LOGIN_WINDOW_MINUTES = max(1, int(os.getenv("LOGIN_WINDOW_MINUTES", "15")))

    SESSION_COOKIE_NAME = "bator_portfolio_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=max(1, int(os.getenv("SESSION_LIFETIME_HOURS", "8")))
    )
    TRUST_PROXY = _env_bool("TRUST_PROXY", False)
    JSON_AS_ASCII = False
