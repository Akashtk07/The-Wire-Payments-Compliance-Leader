"""
Application configuration using pydantic-settings.

All values can be overridden via environment variables or a .env file
placed in the project root directory.

Usage:
    from config import settings
    print(settings.LLM_PROVIDER)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Explicit .env loader — runs before pydantic-settings reads the environment.
# This guarantees variables are in os.environ even if pydantic-settings
# has trouble resolving the file path on Windows.
# ---------------------------------------------------------------------------

_HERE = Path(__file__).parent          # backend/
_ROOT = _HERE.parent                   # project root
_ENV_FILE = _HERE / ".env" if (_HERE / ".env").exists() else _ROOT / ".env"

# Absolute path to the SQLite database — computed once at import time so it
# is always correct regardless of which directory uvicorn is started from.
_DB_FILE = str(_ROOT / "data" / "compliance.db")


def _load_dotenv(path: Path) -> None:
    """Minimal dotenv loader — no extra dependencies required."""
    if not path.exists():
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # Only set if not already overridden by a real environment variable
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    """Centralised application settings."""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    APP_TITLE: str = "The Compliance Leader API"
    APP_VERSION: str = "1.1.0-cbpr-r2025"   # CBPR+ R2025 compliant release
    DEBUG: bool = False

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    @property
    def allowed_origins(self) -> List[str]:
        origins = [self.FRONTEND_ORIGIN, "http://localhost:3000", "http://127.0.0.1:3000"]
        return list(dict.fromkeys(origins))  # deduplicate while preserving order

    # ------------------------------------------------------------------
    # Data directories — absolute, anchored to project root
    # ------------------------------------------------------------------
    BASE_DATA_DIR: str = str(_ROOT / "data")

    @property
    def AUDIT_DIR(self) -> str:
        return str(Path(self.BASE_DATA_DIR) / "audit")

    @property
    def UPLOAD_DIR(self) -> str:
        return str(Path(self.BASE_DATA_DIR) / "uploads")

    @property
    def XSD_DIR(self) -> str:
        return str(Path(self.BASE_DATA_DIR) / "xsd")

    @property
    def CHROMA_PERSIST_DIR(self) -> str:
        # Allow override via env var, else use absolute default
        env_val = os.environ.get("CHROMA_PERSIST_DIR")
        if env_val and not env_val.startswith("."):
            return env_val
        return str(Path(self.BASE_DATA_DIR) / "chroma")

    # ------------------------------------------------------------------
    # LLM provider
    # ------------------------------------------------------------------
    LLM_PROVIDER: str = "gemini"          # gemini | openai | groq | ollama
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.0-flash"   # Confirmed active Sep 2026
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.1-8b-instant"  # Fast, confirmed active Sep 2026
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # ------------------------------------------------------------------
    # Database (SQLite) — absolute path, works regardless of CWD
    # ------------------------------------------------------------------
    @property
    def DATABASE_URL(self) -> str:
        """Async SQLite URL (aiosqlite) using absolute path."""
        return f"sqlite+aiosqlite:///{_DB_FILE}"

    @property
    def SYNC_DATABASE_URL(self) -> str:
        """Synchronous SQLite URL for schema creation (SQLAlchemy create_all)."""
        return f"sqlite:///{_DB_FILE}"

    # ------------------------------------------------------------------
    # Security (JWT)
    # ------------------------------------------------------------------
    SECRET_KEY: str = "CHANGE_ME_IN_PRODUCTION_USE_256BIT_RANDOM_KEY"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # ------------------------------------------------------------------
    # Seed admin account
    # ------------------------------------------------------------------
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"
    ADMIN_EMAIL: str = "admin@complianceleader.io"

    # ------------------------------------------------------------------
    # Email / Gmail SMTP (OTP delivery)
    # ------------------------------------------------------------------
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None      # your@gmail.com
    SMTP_PASSWORD: Optional[str] = None      # 16-char Gmail App Password
    SMTP_FROM_NAME: str = "Compliance Leader"
    SMTP_ENABLED: bool = True                # set False to log OTP to console instead

    # ------------------------------------------------------------------
    # OTP Policy
    # ------------------------------------------------------------------
    OTP_EXPIRE_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 3
    OTP_MAX_RESENDS: int = 3

    # ------------------------------------------------------------------
    # Account Lockout Policy (banking grade)
    # ------------------------------------------------------------------
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 30
    SESSION_TIMEOUT_MINUTES: int = 120

    # ------------------------------------------------------------------
    # Uvicorn / server
    # ------------------------------------------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000


settings = Settings()
