"""
Guidelines router — manage guideline version registry.

Endpoints:
  GET    /api/v1/guidelines/versions         — list all active versions (authenticated)
  POST   /api/v1/guidelines/versions         — add new version (admin only)
  DELETE /api/v1/guidelines/versions/{id}    — soft-delete a version (admin only)
"""

from __future__ import annotations

from typing import Any, Dict, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth_service import User, get_current_user, get_db, require_admin
from services.guideline_registry import (
    create_version,
    delete_version,
    get_all_versions,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/guidelines", tags=["Guideline Versions"])


class CreateVersionRequest(BaseModel):
    label: str = Field(..., min_length=2, max_length=100)
    year: int = Field(default=0, ge=0, le=2100)
    category: str = Field(default="CBPR+", max_length=50)
    is_draft: bool = Field(default=False)
    description: str = Field(default="", max_length=500)


@router.get("/versions")
async def list_versions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """List all active guideline versions."""
    return await get_all_versions(db)


@router.post("/versions", status_code=status.HTTP_201_CREATED)
async def add_version(
    body: CreateVersionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Admin only: add a new guideline version to the registry."""
    from services.guideline_registry import _version_to_dict
    try:
        gv = await create_version(
            db=db,
            label=body.label,
            year=body.year,
            category=body.category,
            is_draft=body.is_draft,
            description=body.description,
            created_by=admin.username,
        )
        log.info("guideline_version_created", label=body.label, by=admin.username)
        return _version_to_dict(gv)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error": "VERSION_EXISTS", "message": str(exc)},
        )


@router.delete("/versions/{version_id}")
async def remove_version(
    version_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Admin only: soft-delete a guideline version."""
    deleted = await delete_version(db, version_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "NOT_FOUND", "message": f"Version {version_id} not found."},
        )
    log.info("guideline_version_deleted", version_id=version_id, by=admin.username)
    return {"status": "DELETED", "version_id": version_id}
