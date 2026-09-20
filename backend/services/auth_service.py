"""
Authentication & Authorization Service — Banking Grade

Provides:
  - SQLAlchemy User model with full security fields
  - Password hashing (bcrypt cost 12)
  - Password policy enforcement
  - JWT access + refresh tokens
  - OTP generation, verification, expiry
  - Account lockout (5 fails → 30 min lock)
  - FastAPI dependencies: get_current_user, require_admin
  - DB session factory
  - Admin user seeding on startup
"""

from __future__ import annotations

import random
import re
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import AsyncGenerator, Optional

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import (
    Boolean, Column, DateTime, Integer, String,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Password hashing — bcrypt cost 12 (banking standard)
# ---------------------------------------------------------------------------

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------

PASSWORD_POLICY = {
    "min_length": 8,
    "require_uppercase": True,
    "require_lowercase": True,
    "require_digit": True,
    "require_special": True,
}

SPECIAL_CHARS = set("!@#$%^&*()_+-=[]{}|;:,.<>?")


def validate_password(password: str) -> list[str]:
    """Returns a list of policy violations (empty = OK)."""
    errors: list[str] = []
    if len(password) < PASSWORD_POLICY["min_length"]:
        errors.append(f"Minimum {PASSWORD_POLICY['min_length']} characters required")
    if PASSWORD_POLICY["require_uppercase"] and not any(c.isupper() for c in password):
        errors.append("At least one uppercase letter required")
    if PASSWORD_POLICY["require_lowercase"] and not any(c.islower() for c in password):
        errors.append("At least one lowercase letter required")
    if PASSWORD_POLICY["require_digit"] and not any(c.isdigit() for c in password):
        errors.append("At least one digit required")
    if PASSWORD_POLICY["require_special"] and not any(c in SPECIAL_CHARS for c in password):
        errors.append(f"At least one special character required ({','.join(list(SPECIAL_CHARS)[:8])}...)")
    return errors


# ---------------------------------------------------------------------------
# SQLAlchemy setup
# ---------------------------------------------------------------------------

_data_dir = Path(settings.BASE_DATA_DIR)
_data_dir.mkdir(parents=True, exist_ok=True)

# Log the exact DB path so it's visible in the backend terminal on startup
_db_url = settings.DATABASE_URL
log.info("database_url_resolved", url=_db_url)

_sync_engine = create_engine(
    settings.SYNC_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

_async_engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=_async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# User model — Banking-grade security fields
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    # Core identity
    id                   = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username             = Column(String, unique=True, index=True, nullable=False)
    email                = Column(String, unique=True, index=True, nullable=False)
    full_name            = Column(String, nullable=True)
    hashed_password      = Column(String, nullable=False)

    # Role & Status
    role                 = Column(String, default="analyst")      # "admin" | "analyst"
    is_active            = Column(Boolean, default=True)
    is_verified          = Column(Boolean, default=False)          # email OTP verified

    # OTP fields
    otp_code             = Column(String, nullable=True)           # hashed OTP
    otp_expires_at       = Column(DateTime(timezone=True), nullable=True)
    otp_attempts         = Column(Integer, default=0)              # wrong OTP guesses
    otp_resend_count     = Column(Integer, default=0)              # resend requests

    # Account lockout
    failed_login_attempts = Column(Integer, default=0)
    locked_until          = Column(DateTime(timezone=True), nullable=True)

    # Password management
    must_change_password  = Column(Boolean, default=False)
    password_changed_at   = Column(DateTime(timezone=True), nullable=True)

    # Activity tracking
    created_at            = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_login            = Column(DateTime(timezone=True), nullable=True)
    last_active           = Column(DateTime(timezone=True), nullable=True)
    created_by            = Column(String, default="self")          # "self" | admin username


# ---------------------------------------------------------------------------
# DB initialisation & admin seeding
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create all tables and seed the admin user (idempotent)."""
    Base.metadata.create_all(bind=_sync_engine)
    log.info("db_tables_created")

    SyncSession = sessionmaker(bind=_sync_engine)
    with SyncSession() as session:
        existing = session.query(User).filter_by(username=settings.ADMIN_USERNAME).first()
        if not existing:
            admin = User(
                id=str(uuid.uuid4()),
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                full_name="System Administrator",
                hashed_password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
                is_active=True,
                is_verified=True,           # admin is pre-verified
                must_change_password=True,  # force password change on first login
                created_by="system",
            )
            session.add(admin)
            session.commit()
            log.info("admin_user_seeded", username=settings.ADMIN_USERNAME)
        else:
            # Ensure existing admin has is_verified=True (migration safety)
            if not existing.is_verified:
                existing.is_verified = True
                session.commit()
            log.info("admin_user_already_exists", username=settings.ADMIN_USERNAME)


# ---------------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------------

def generate_otp() -> str:
    """Generate a cryptographically secure 6-digit OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(6))


def hash_otp(otp: str) -> str:
    """Hash OTP with bcrypt so it's never stored in plaintext."""
    return pwd_context.hash(otp)


def verify_otp_hash(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": expire,
        "type": "access",
        "jti": str(uuid.uuid4()),   # JWT ID for future revocation
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and verify a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_TOKEN", "message": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Account lockout helpers
# ---------------------------------------------------------------------------

def is_account_locked(user: User) -> bool:
    """Compare against naive UTC datetime as stored by SQLite."""
    if user.locked_until and user.locked_until > datetime.utcnow():
        return True
    return False


def lockout_remaining_seconds(user: User) -> int:
    if not user.locked_until:
        return 0
    delta = user.locked_until - datetime.utcnow()
    return max(0, int(delta.total_seconds()))


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency that returns the authenticated, verified, active User."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "NOT_AUTHENTICATED", "message": "Authentication required."},
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "WRONG_TOKEN_TYPE", "message": "Access token required."},
        )

    user_id: str = payload.get("sub", "")
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "USER_NOT_FOUND", "message": "User account not found."},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "ACCOUNT_DISABLED", "message": "Your account has been deactivated. Contact an administrator."},
        )
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "EMAIL_NOT_VERIFIED", "message": "Please verify your email address before accessing the system."},
        )
    if is_account_locked(user):
        secs = lockout_remaining_seconds(user)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "ACCOUNT_LOCKED",
                "message": f"Account temporarily locked. Try again in {secs // 60}m {secs % 60}s.",
                "retry_after_seconds": secs,
            },
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that raises 403 if the user is not an admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "FORBIDDEN", "message": "Administrator privileges required."},
        )
    return current_user
