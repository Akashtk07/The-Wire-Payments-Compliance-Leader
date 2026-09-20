"""
Guideline Version Registry.

Manages the known guideline versions in SQLite.
Pre-seeded with standard CBPR+, ISO 20022 versions on startup.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import Boolean, Column, DateTime, String, create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from config import settings
from services.auth_service import Base, _sync_engine, AsyncSessionLocal

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Guideline Version model
# ---------------------------------------------------------------------------

PRESET_VERSIONS = [
    {
        "label": "CBPR+ R2023",
        "year": 2023,
        "category": "CBPR+",
        "is_draft": False,
        "description": "SWIFT CBPR+ Release 2023 — Cross-Border Payments and Reporting Plus",
    },
    {
        "label": "CBPR+ R2024",
        "year": 2024,
        "category": "CBPR+",
        "is_draft": False,
        "description": "SWIFT CBPR+ Release 2024 — Previous production standard (superseded by R2025 from Nov 22, 2025)",
    },
    {
        "label": "CBPR+ R2025",
        "year": 2025,
        "category": "CBPR+",
        "is_draft": False,
        "description": "SWIFT CBPR+ Release 2025 — CURRENT MANDATORY STANDARD. Coexistence period ended Nov 22, 2025. Hybrid postal address (TownName + Country mandatory), structured address required by Nov 2026. MT103/MT202 retired from SWIFT FINplus.",
    },
    {
        "label": "CBPR+ R2026 (Draft)",
        "year": 2026,
        "category": "CBPR+",
        "is_draft": True,
        "description": "SWIFT CBPR+ Release 2026 — Draft / under development",
    },
    {
        "label": "ISO 20022 Unscheduled",
        "year": 0,
        "category": "ISO 20022",
        "is_draft": False,
        "description": "Generic ISO 20022 documents not tied to a specific CBPR+ release",
    },
    {
        "label": "BIS CPMI Guidelines",
        "year": 2025,
        "category": "Regulatory",
        "is_draft": False,
        "description": "Bank for International Settlements - CPMI cross-border payment standards",
    },
    {
        "label": "FATF Recommendations",
        "year": 2025,
        "category": "Regulatory",
        "is_draft": False,
        "description": "Financial Action Task Force AML/CFT recommendations",
    },
    {
        "label": "Custom / Internal",
        "year": 0,
        "category": "Custom",
        "is_draft": False,
        "description": "Custom or internal guidelines uploaded by your organization",
    },
]


class GuidelineVersion(Base):
    __tablename__ = "guideline_versions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    label = Column(String, unique=True, nullable=False, index=True)
    year = Column(String, default="0")
    category = Column(String, default="CBPR+")
    is_draft = Column(Boolean, default=False)
    description = Column(String, default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    created_by = Column(String, default="system")


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def seed_guideline_versions() -> None:
    """Seed preset guideline versions into the DB (idempotent)."""
    from sqlalchemy.orm import Session as SyncSession

    SyncSessionLocal = sessionmaker(bind=_sync_engine)
    with SyncSessionLocal() as session:
        for preset in PRESET_VERSIONS:
            existing = session.query(GuidelineVersion).filter_by(label=preset["label"]).first()
            if not existing:
                gv = GuidelineVersion(
                    id=str(uuid.uuid4()),
                    label=preset["label"],
                    year=str(preset["year"]),
                    category=preset["category"],
                    is_draft=preset["is_draft"],
                    description=preset["description"],
                    is_active=True,
                    created_by="system",
                )
                session.add(gv)
        session.commit()
    log.info("guideline_versions_seeded")


# ---------------------------------------------------------------------------
# Async DB helpers
# ---------------------------------------------------------------------------


async def get_all_versions(db: AsyncSession) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(GuidelineVersion).where(GuidelineVersion.is_active == True).order_by(
            GuidelineVersion.year.desc(), GuidelineVersion.label
        )
    )
    versions = result.scalars().all()
    return [_version_to_dict(v) for v in versions]


async def get_version_by_id(db: AsyncSession, version_id: str) -> Optional[GuidelineVersion]:
    result = await db.execute(select(GuidelineVersion).where(GuidelineVersion.id == version_id))
    return result.scalar_one_or_none()


async def create_version(
    db: AsyncSession,
    label: str,
    year: int,
    category: str,
    is_draft: bool,
    description: str,
    created_by: str,
) -> GuidelineVersion:
    gv = GuidelineVersion(
        id=str(uuid.uuid4()),
        label=label,
        year=str(year),
        category=category,
        is_draft=is_draft,
        description=description,
        is_active=True,
        created_by=created_by,
    )
    db.add(gv)
    await db.commit()
    await db.refresh(gv)
    return gv


async def delete_version(db: AsyncSession, version_id: str) -> bool:
    from sqlalchemy import update
    result = await db.execute(
        update(GuidelineVersion)
        .where(GuidelineVersion.id == version_id)
        .values(is_active=False)
    )
    await db.commit()
    return result.rowcount > 0


def _version_to_dict(v: GuidelineVersion) -> Dict[str, Any]:
    return {
        "id": v.id,
        "label": v.label,
        "year": int(v.year) if v.year and v.year.isdigit() else 0,
        "category": v.category,
        "is_draft": v.is_draft,
        "description": v.description,
        "created_at": v.created_at.isoformat() if v.created_at else None,
        "created_by": v.created_by,
    }
