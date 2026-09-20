"""
Admin Router — Full Platform Administration

All endpoints require admin role.

User Management:
  GET  /api/v1/admin/users                  — list all users (rich data)
  POST /api/v1/admin/users                  — create user (admin bypasses OTP)
  GET  /api/v1/admin/users/{id}             — user detail
  PUT  /api/v1/admin/users/{id}/role        — promote / demote role
  PUT  /api/v1/admin/users/{id}/lock        — lock / unlock account
  PUT  /api/v1/admin/users/{id}/activate    — activate / deactivate account
  POST /api/v1/admin/users/{id}/force-reset — force password reset on next login
  POST /api/v1/admin/users/{id}/verify      — manually verify email (bypass OTP)
  DELETE /api/v1/admin/users/{id}           — hard delete user

Platform:
  GET  /api/v1/admin/stats                  — platform statistics
  GET  /api/v1/admin/system                 — system info
"""

from __future__ import annotations

import os
import platform
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from services.audit_logger import audit_logger
from services.auth_service import (
    User, get_db, hash_password, require_admin, validate_password,
    is_account_locked, lockout_remaining_seconds,
)
from services.guideline_registry import GuidelineVersion
from services.email_service import email_service

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["Administration"])


# ---------------------------------------------------------------------------
# Serialiser
# ---------------------------------------------------------------------------

def _user_to_dict(u: User) -> Dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "is_verified": u.is_verified,
        "must_change_password": u.must_change_password,
        "failed_login_attempts": u.failed_login_attempts,
        "is_locked": is_account_locked(u),
        "locked_until": u.locked_until.isoformat() if u.locked_until else None,
        "lockout_remaining_seconds": lockout_remaining_seconds(u) if is_account_locked(u) else 0,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "last_login": u.last_login.isoformat() if u.last_login else None,
        "last_active": u.last_active.isoformat() if u.last_active else None,
        "password_changed_at": u.password_changed_at.isoformat() if u.password_changed_at else None,
        "created_by": u.created_by,
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(default=None, max_length=80)
    role: str = Field(default="analyst", pattern="^(admin|analyst)$")
    must_change_password: bool = True


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|analyst)$")


class LockRequest(BaseModel):
    lock: bool                                   # True = lock, False = unlock
    reason: Optional[str] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1, le=43200)  # max 30 days


class ActivateRequest(BaseModel):
    is_active: bool


class AdminUpdateUserRequest(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(default=None, max_length=80)
    new_password: Optional[str] = Field(default=None, min_length=8)
    must_change_password: Optional[bool] = None


# ---------------------------------------------------------------------------
# GET /admin/users — List all users
# ---------------------------------------------------------------------------

@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Return all users with full detail. Admin-only."""
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [_user_to_dict(u) for u in users]


# ---------------------------------------------------------------------------
# GET /admin/users/{id}
# ---------------------------------------------------------------------------

@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# POST /admin/users — Create user (admin, bypasses OTP)
# ---------------------------------------------------------------------------

@router.post("/users", status_code=status.HTTP_201_CREATED)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Admin creates a user — account is pre-verified, no OTP needed."""
    # Validate password
    errors = validate_password(body.password)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={"error": "PASSWORD_POLICY_VIOLATION", "violations": errors},
        )

    # Duplicate check
    dup = await db.execute(
        select(User).where((User.username == body.username) | (User.email == str(body.email)))
    )
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": "USER_EXISTS", "message": "Username or email already in use."},
        )

    user = User(
        id=str(uuid.uuid4()),
        username=body.username.lower(),
        email=str(body.email),
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        role=body.role,
        is_active=True,
        is_verified=True,              # Admin-created users are pre-verified
        must_change_password=body.must_change_password,
        created_by=admin.username,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await audit_logger.log(
        event_type="ADMIN_CREATED_USER",
        module="admin",
        status="SUCCESS",
        details={"username": body.username, "role": body.role, "by": admin.username},
    )
    log.info("admin_created_user", username=body.username, role=body.role, by=admin.username)
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# PUT /admin/users/{id}/role — Promote / Demote
# ---------------------------------------------------------------------------

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    body: UpdateRoleRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Promote analyst to admin or demote admin to analyst. Cannot change own role."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail={"error": "SELF_ROLE_CHANGE", "message": "Cannot change your own role."},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    old_role = user.role
    user.role = body.role
    await db.commit()

    action = "ADMIN_GRANTED" if body.role == "admin" else "ADMIN_REVOKED"
    await audit_logger.log(
        event_type=action,
        module="admin",
        status="SUCCESS",
        details={"user": user.username, "old_role": old_role, "new_role": body.role, "by": admin.username},
    )
    log.info(action.lower(), username=user.username, old_role=old_role, new_role=body.role, by=admin.username)
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# PUT /admin/users/{id}/lock — Lock / Unlock
# ---------------------------------------------------------------------------

@router.put("/users/{user_id}/lock")
async def lock_user(
    user_id: str,
    body: LockRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Lock (or unlock) a user account with optional reason and duration."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail={"error": "SELF_LOCK", "message": "Cannot lock your own account."},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    if body.lock:
        duration = body.duration_minutes or settings.LOCKOUT_MINUTES
        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=duration)
        user.failed_login_attempts = settings.MAX_LOGIN_ATTEMPTS
        event = "ACCOUNT_LOCKED_BY_ADMIN"
    else:
        user.locked_until = None
        user.failed_login_attempts = 0
        event = "ACCOUNT_UNLOCKED_BY_ADMIN"

    await db.commit()
    await audit_logger.log(
        event_type=event,
        module="admin",
        status="SUCCESS",
        details={"user": user.username, "reason": body.reason, "by": admin.username},
    )
    log.info(event.lower(), username=user.username, by=admin.username)
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# PUT /admin/users/{id}/activate — Activate / Deactivate
# ---------------------------------------------------------------------------

@router.put("/users/{user_id}/activate")
async def set_user_active(
    user_id: str,
    body: ActivateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Enable or disable a user account."""
    if user_id == admin.id and not body.is_active:
        raise HTTPException(
            status_code=400,
            detail={"error": "SELF_DEACTIVATE", "message": "Cannot deactivate your own account."},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    user.is_active = body.is_active
    await db.commit()

    event = "USER_ACTIVATED" if body.is_active else "USER_DEACTIVATED"
    await audit_logger.log(
        event_type=event,
        module="admin",
        status="SUCCESS",
        details={"user": user.username, "by": admin.username},
    )
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# POST /admin/users/{id}/force-reset — Force password reset
# ---------------------------------------------------------------------------

@router.post("/users/{user_id}/force-reset")
async def force_password_reset(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Mark user as must_change_password=True and optionally notify by email."""
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    user.must_change_password = True
    await db.commit()

    # Send email notification
    email_service.send_password_reset_notification(user.email, user.username)

    await audit_logger.log(
        event_type="FORCE_PASSWORD_RESET",
        module="admin",
        status="SUCCESS",
        details={"user": user.username, "by": admin.username},
    )
    log.info("force_password_reset", username=user.username, by=admin.username)
    return {"message": f"Password reset forced for {user.username}. They will be prompted on next login."}


# ---------------------------------------------------------------------------
# POST /admin/users/{id}/verify — Manually verify email
# ---------------------------------------------------------------------------

@router.post("/users/{user_id}/verify")
async def admin_verify_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Manually verify a user's email (bypasses OTP flow)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    user.is_verified = True
    user.otp_code = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    await db.commit()

    await audit_logger.log(
        event_type="USER_MANUALLY_VERIFIED",
        module="admin",
        status="SUCCESS",
        details={"user": user.username, "by": admin.username},
    )
    return {"message": f"User {user.username} has been manually verified."}


# ---------------------------------------------------------------------------
# PUT /admin/users/{id} — General update (email, full_name, new_password)
# ---------------------------------------------------------------------------

@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    body: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Update user email, full name, or force a new password."""
    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    if body.email:
        user.email = str(body.email)
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.must_change_password is not None:
        user.must_change_password = body.must_change_password
    if body.new_password:
        errors = validate_password(body.new_password)
        if errors:
            raise HTTPException(
                status_code=422,
                detail={"error": "PASSWORD_POLICY_VIOLATION", "violations": errors},
            )
        user.hashed_password = hash_password(body.new_password)
        user.must_change_password = True
        user.password_changed_at = datetime.now(timezone.utc)

    await db.commit()
    await audit_logger.log(
        event_type="ADMIN_UPDATED_USER",
        module="admin",
        status="SUCCESS",
        details={"user": user.username, "by": admin.username},
    )
    return _user_to_dict(user)


# ---------------------------------------------------------------------------
# DELETE /admin/users/{id} — Hard delete
# ---------------------------------------------------------------------------

@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Permanently delete a user. Cannot delete yourself."""
    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail={"error": "SELF_DELETE", "message": "Cannot delete your own account."},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user: Optional[User] = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail={"error": "NOT_FOUND"})

    username = user.username
    await db.delete(user)
    await db.commit()

    await audit_logger.log(
        event_type="USER_DELETED",
        module="admin",
        status="SUCCESS",
        details={"deleted_user": username, "by": admin.username},
    )
    log.info("user_deleted", username=username, by=admin.username)
    return {"status": "DELETED", "username": username}


# ---------------------------------------------------------------------------
# GET /admin/stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Platform-wide statistics."""
    total_r  = await db.execute(select(func.count()).select_from(User))
    active_r = await db.execute(select(func.count()).select_from(User).where(User.is_active == True))
    admin_r  = await db.execute(select(func.count()).select_from(User).where(User.role == "admin"))
    verified_r = await db.execute(select(func.count()).select_from(User).where(User.is_verified == True))

    total   = total_r.scalar() or 0
    active  = active_r.scalar() or 0
    admins  = admin_r.scalar() or 0
    verified = verified_r.scalar() or 0

    gv_r = await db.execute(
        select(func.count()).select_from(GuidelineVersion).where(GuidelineVersion.is_active == True)
    )
    guideline_versions = gv_r.scalar() or 0

    doc_count = chunk_count = 0
    try:
        from services.rag_pipeline import _get_collection
        col = _get_collection()
        chunk_count = col.count()
        all_meta = col.get(include=["metadatas"])
        metas = all_meta.get("metadatas") or []
        doc_ids = {m.get("doc_id") for m in metas if m.get("doc_id")}
        doc_count = len(doc_ids)
    except Exception:
        pass

    return {
        "users": {
            "total": total,
            "active": active,
            "admin": admins,
            "analyst": active - admins,
            "verified": verified,
            "unverified": total - verified,
        },
        "documents": {"total_docs": doc_count, "total_chunks": chunk_count},
        "guideline_versions": guideline_versions,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /admin/system
# ---------------------------------------------------------------------------

@router.get("/system")
async def get_system_info(admin: User = Depends(require_admin)) -> Dict[str, Any]:
    """System information."""
    chroma_size_mb = upload_size_mb = upload_count = 0.0
    try:
        cp = Path(settings.CHROMA_PERSIST_DIR)
        if cp.exists():
            chroma_size_mb = round(sum(f.stat().st_size for f in cp.rglob("*") if f.is_file()) / 1024 / 1024, 2)
    except Exception:
        pass
    try:
        up = Path(settings.UPLOAD_DIR)
        if up.exists():
            files = list(up.rglob("*"))
            upload_count = sum(1 for f in files if f.is_file())
            upload_size_mb = round(sum(f.stat().st_size for f in files if f.is_file()) / 1024 / 1024, 2)
    except Exception:
        pass

    return {
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "app_version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "smtp_configured": bool(settings.SMTP_USERNAME and settings.SMTP_PASSWORD),
        "smtp_enabled": settings.SMTP_ENABLED,
        "otp_expire_minutes": settings.OTP_EXPIRE_MINUTES,
        "max_login_attempts": settings.MAX_LOGIN_ATTEMPTS,
        "lockout_minutes": settings.LOCKOUT_MINUTES,
        "storage": {
            "chroma_db_mb": chroma_size_mb,
            "uploads_mb": upload_size_mb,
            "uploads_count": upload_count,
        },
        "paths": {
            "upload_dir": settings.UPLOAD_DIR,
            "chroma_dir": settings.CHROMA_PERSIST_DIR,
            "audit_dir": settings.AUDIT_DIR,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
