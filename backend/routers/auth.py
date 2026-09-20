"""
Auth Router — Banking-Grade Authentication

Endpoints:
  POST /auth/register           — Self-registration, sends OTP
  POST /auth/verify-otp         — Verify registration OTP
  POST /auth/resend-otp         — Resend OTP (rate-limited)
  POST /auth/login              — Login (username + password)
  POST /auth/refresh            — Refresh access token
  POST /auth/logout             — Logout (client-side token clear)
  GET  /auth/me                 — Current user profile
  POST /auth/change-password    — Change own password
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.audit_logger import audit_logger
from services.auth_service import (
    AsyncSessionLocal,
    User,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    get_current_user,
    get_db,
    hash_otp,
    hash_password,
    is_account_locked,
    lockout_remaining_seconds,
    validate_password,
    verify_otp_hash,
    verify_password,
)
from services.email_service import email_service

import uuid

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(default=None, max_length=80)

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        return v.lower()


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendOtpRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    refresh_token: str


# ---------------------------------------------------------------------------
# POST /auth/register
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Register a new user. Sends a 6-digit OTP to the provided email.
    Account is inactive until OTP is verified.
    """
    # Password policy check
    errors = validate_password(body.password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "PASSWORD_POLICY_VIOLATION", "violations": errors},
        )

    # Check for existing username
    existing_user = await db.execute(select(User).where(User.username == body.username))
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "USERNAME_TAKEN", "message": "This username is already registered."},
        )

    # Check for existing email
    existing_email = await db.execute(select(User).where(User.email == str(body.email)))
    existing_email_user = existing_email.scalar_one_or_none()

    if existing_email_user:
        if existing_email_user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "EMAIL_TAKEN", "message": "This email is already registered."},
            )
        # Re-send OTP to existing unverified account
        otp = generate_otp()
        existing_email_user.otp_code = hash_otp(otp)
        existing_email_user.otp_expires_at = datetime.utcnow() + timedelta(
            minutes=settings.OTP_EXPIRE_MINUTES
        )
        existing_email_user.otp_attempts = 0
        await db.commit()
        email_service.send_otp(str(body.email), existing_email_user.username, otp)
        return {"message": "OTP resent to your email. Please verify to activate your account."}

    # Generate OTP
    otp = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

    new_user = User(
        id=str(uuid.uuid4()),
        username=body.username,
        email=str(body.email),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role="analyst",
        is_active=True,
        is_verified=False,
        otp_code=hash_otp(otp),
        otp_expires_at=otp_expires,
        otp_attempts=0,
        otp_resend_count=0,
        created_by="self",
    )
    db.add(new_user)
    await db.commit()

    # Send OTP email
    sent = email_service.send_otp(str(body.email), body.username, otp)

    await audit_logger.log(
        event_type="USER_REGISTERED",
        module="auth",
        status="SUCCESS",
        details={"username": body.username, "email": str(body.email), "email_sent": sent},
    )

    log.info("user_registered", username=body.username, email=str(body.email))

    return {
        "message": "Registration successful. Please check your email for the 6-digit OTP.",
        "email": str(body.email),
        "expires_in_minutes": settings.OTP_EXPIRE_MINUTES,
    }


# ---------------------------------------------------------------------------
# POST /auth/verify-otp
# ---------------------------------------------------------------------------

@router.post("/verify-otp")
async def verify_otp(body: VerifyOtpRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """Verify the registration OTP to activate the account."""
    result = await db.execute(select(User).where(User.email == str(body.email)))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "USER_NOT_FOUND", "message": "No account found for this email."},
        )

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "ALREADY_VERIFIED", "message": "Email is already verified. Please log in."},
        )

    # Check OTP expiry — use utcnow() (naive) to match SQLite stored naive datetimes
    if not user.otp_expires_at or datetime.utcnow() > user.otp_expires_at:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={"error": "OTP_EXPIRED", "message": "Your verification code has expired. Please request a new one."},
        )

    # Check too many wrong attempts
    if user.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "OTP_MAX_ATTEMPTS", "message": "Too many incorrect attempts. Please request a new code."},
        )

    # Verify OTP
    if not user.otp_code or not verify_otp_hash(body.otp, user.otp_code):
        user.otp_attempts += 1
        await db.commit()
        attempts_left = settings.OTP_MAX_ATTEMPTS - user.otp_attempts
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "INVALID_OTP",
                "message": f"Incorrect code. {max(0, attempts_left)} attempt(s) remaining.",
                "attempts_remaining": max(0, attempts_left),
            },
        )

    # Success — activate account
    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    await db.commit()

    await audit_logger.log(
        event_type="EMAIL_VERIFIED",
        module="auth",
        status="SUCCESS",
        details={"username": user.username, "email": user.email},
    )
    log.info("email_verified", username=user.username)

    return {"message": "Email verified successfully. You can now log in.", "username": user.username}


# ---------------------------------------------------------------------------
# POST /auth/resend-otp
# ---------------------------------------------------------------------------

@router.post("/resend-otp")
async def resend_otp(body: ResendOtpRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """Resend OTP to the registered email. Max 3 times."""
    result = await db.execute(select(User).where(User.email == str(body.email)))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        # Don't leak user existence
        return {"message": "If this email is registered, a new code will be sent."}

    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "ALREADY_VERIFIED", "message": "Account is already verified."},
        )

    if user.otp_resend_count >= settings.OTP_MAX_RESENDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "RESEND_LIMIT", "message": "Maximum resend limit reached. Please contact support."},
        )

    otp = generate_otp()
    user.otp_code = hash_otp(otp)
    user.otp_expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    user.otp_attempts = 0
    user.otp_resend_count += 1
    await db.commit()

    email_service.send_otp(str(body.email), user.username, otp)
    log.info("otp_resent", email=str(body.email), resend_count=user.otp_resend_count)

    return {
        "message": "New verification code sent to your email.",
        "resends_remaining": settings.OTP_MAX_RESENDS - user.otp_resend_count,
    }


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """
    Authenticate with username + password.
    Returns JWT access + refresh tokens on success.
    Enforces account lockout after 5 failed attempts.
    """
    # Find user (try username first, then email)
    result = await db.execute(select(User).where(User.username == body.username.lower()))
    user: Optional[User] = result.scalar_one_or_none()

    if not user:
        # Try email lookup
        result = await db.execute(select(User).where(User.email == body.username))
        user = result.scalar_one_or_none()

    def _fail_generic():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_CREDENTIALS", "message": "Invalid username or password."},
        )

    if not user:
        _fail_generic()

    # Account lockout check
    if is_account_locked(user):
        secs = lockout_remaining_seconds(user)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail={
                "error": "ACCOUNT_LOCKED",
                "message": f"Account locked. Try again in {secs // 60}m {secs % 60}s.",
                "retry_after_seconds": secs,
            },
        )

    # Active check
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "ACCOUNT_DISABLED", "message": "Account disabled. Contact an administrator."},
        )

    # Email verification check
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "EMAIL_NOT_VERIFIED",
                "message": "Email not verified. Please check your inbox for the verification code.",
                "email": user.email,
            },
        )

    # Password check
    if not verify_password(body.password, user.hashed_password):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=settings.LOCKOUT_MINUTES)
            await db.commit()
            await audit_logger.log(
                event_type="ACCOUNT_LOCKED",
                module="auth",
                status="WARN",
                details={"username": user.username, "failed_attempts": user.failed_login_attempts},
            )
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail={
                    "error": "ACCOUNT_LOCKED",
                    "message": f"Too many failed attempts. Account locked for {settings.LOCKOUT_MINUTES} minutes.",
                    "retry_after_seconds": settings.LOCKOUT_MINUTES * 60,
                },
            )
        await db.commit()
        _fail_generic()

    # Successful login — reset counters
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    user.last_active = datetime.utcnow()
    await db.commit()

    access_token = create_access_token(user.id, user.username, user.role)
    refresh_token = create_refresh_token(user.id)

    await audit_logger.log(
        event_type="USER_LOGIN",
        module="auth",
        status="SUCCESS",
        details={"username": user.username, "role": user.role},
    )
    log.info("user_login_success", username=user.username, role=user.role)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "must_change_password": user.must_change_password,
        },
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------

@router.post("/refresh")
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)) -> Any:
    """Exchange a refresh token for a new access token."""
    payload = decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "WRONG_TOKEN_TYPE", "message": "Refresh token required."},
        )
    user_id = payload.get("sub", "")
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()

    if not user or not user.is_active or not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "INVALID_USER", "message": "User not found or account not active."},
        )

    return {
        "access_token": create_access_token(user.id, user.username, user.role),
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)) -> Any:
    """Logout — client should discard tokens. Logged to audit trail."""
    await audit_logger.log(
        event_type="USER_LOGOUT",
        module="auth",
        status="SUCCESS",
        details={"username": current_user.username},
    )
    return {"message": "Logged out successfully."}


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------

@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> Any:
    """Return the current authenticated user's profile."""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "is_verified": current_user.is_verified,
        "must_change_password": current_user.must_change_password,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "password_changed_at": current_user.password_changed_at.isoformat() if current_user.password_changed_at else None,
    }


# ---------------------------------------------------------------------------
# POST /auth/change-password
# ---------------------------------------------------------------------------

@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Change the authenticated user's password."""
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "WRONG_PASSWORD", "message": "Current password is incorrect."},
        )

    errors = validate_password(body.new_password)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "PASSWORD_POLICY_VIOLATION", "violations": errors},
        )

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = datetime.now(timezone.utc)
    await db.commit()

    await audit_logger.log(
        event_type="PASSWORD_CHANGED",
        module="auth",
        status="SUCCESS",
        details={"username": current_user.username},
    )

    return {"message": "Password changed successfully."}
