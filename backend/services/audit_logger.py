"""
Append-only, tamper-evident, PII-masking Audit Logger.

Design decisions:
- One NDJSON file per calendar day: compliance_audit_YYYY-MM-DD.ndjson
- SHA-256 hash chain: each entry chains from the previous hash, genesis = SHA-256("")
- PII masking via regex on full JSON string before write (belt-and-suspenders)
- All I/O is async (aiofiles); file is opened in append mode per write call
- Singleton instance `audit_logger` is exported at module bottom
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiofiles
import structlog

from config import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Regex patterns for PII masking
# ---------------------------------------------------------------------------
_IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4,}\b")
_ACCOUNT_RE = re.compile(r"\b\d{8,}\b")


def _mask_pii(text: str) -> str:
    """Replace IBAN and long numeric account numbers with [MASKED]."""
    text = _IBAN_RE.sub("[MASKED]", text)
    text = _ACCOUNT_RE.sub("[MASKED]", text)
    return text


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------


class AuditLogger:
    """Append-only, hash-chained, PII-masked structured audit logger."""

    def __init__(self, audit_dir: str | None = None) -> None:
        self._dir = Path(audit_dir or settings.AUDIT_DIR)
        self._dir.mkdir(parents=True, exist_ok=True)
        # In-memory last hash (seeded at genesis); will be re-seeded from disk on first write
        self._last_hash: str = hashlib.sha256(b"").hexdigest()
        self._lock = asyncio.Lock()
        self._initialised = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _today_path(self) -> Path:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self._dir / f"compliance_audit_{today}.ndjson"

    async def _seed_last_hash(self) -> None:
        """Read the last hash from today's file (if it exists) so the chain continues correctly after restarts."""
        path = self._today_path()
        if not path.exists():
            self._last_hash = hashlib.sha256(b"").hexdigest()
            return
        last_line: str = ""
        async with aiofiles.open(path, "r", encoding="utf-8") as fh:
            async for line in fh:
                stripped = line.strip()
                if stripped:
                    last_line = stripped
        if last_line:
            try:
                entry = json.loads(last_line)
                self._last_hash = entry.get("hash", hashlib.sha256(b"").hexdigest())
            except json.JSONDecodeError:
                pass

    async def _ensure_initialised(self) -> None:
        if not self._initialised:
            await self._seed_last_hash()
            self._initialised = True

    def _compute_hash(self, previous_hash: str, entry_json: str) -> str:
        payload = (previous_hash + entry_json).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def log(
        self,
        event_type: str,
        module: str,
        status: str,
        details: Dict[str, Any],
        uetr: Optional[str] = None,
        message_type: Optional[str] = None,
    ) -> str:
        """
        Write a single audit entry.  Returns the generated audit_id (UUID4).
        """
        async with self._lock:
            await self._ensure_initialised()

            audit_id = str(uuid.uuid4())
            timestamp = datetime.now(timezone.utc).isoformat()

            # Build entry (without hash yet so we can compute it)
            entry: Dict[str, Any] = {
                "audit_id": audit_id,
                "timestamp": timestamp,
                "event_type": event_type,
                "module": module,
                "status": status,
                "uetr": uetr,
                "message_type": message_type,
                "details": details,
            }

            # Serialise, mask PII, then compute hash
            entry_json_no_hash = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            entry_json_no_hash = _mask_pii(entry_json_no_hash)

            new_hash = self._compute_hash(self._last_hash, entry_json_no_hash)
            entry["hash"] = new_hash

            # Final JSON line (re-serialise including hash, then mask again)
            final_json = json.dumps(entry, ensure_ascii=False, sort_keys=True)
            final_json = _mask_pii(final_json)

            # Append to file
            path = self._today_path()
            async with aiofiles.open(path, "a", encoding="utf-8") as fh:
                await fh.write(final_json + "\n")

            self._last_hash = new_hash

            log.info(
                "audit_entry_written",
                audit_id=audit_id,
                event_type=event_type,
                module=module,
                status=status,
            )
            return audit_id

    async def get_logs(
        self,
        page: int = 1,
        page_size: int = 50,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Read and return paginated audit log entries from all daily files.
        Supports filters: event_type, module, from_date (YYYY-MM-DD), to_date (YYYY-MM-DD).
        """
        filters = filters or {}
        all_entries: List[Dict[str, Any]] = []

        # Collect all daily files sorted chronologically
        ndjson_files = sorted(self._dir.glob("compliance_audit_*.ndjson"))

        # Date range filtering at file level
        from_date: Optional[str] = filters.get("from_date")
        to_date: Optional[str] = filters.get("to_date")

        for ndjson_path in ndjson_files:
            # Extract date from filename
            stem = ndjson_path.stem  # e.g. compliance_audit_2026-05-23
            file_date = stem.replace("compliance_audit_", "")
            if from_date and file_date < from_date:
                continue
            if to_date and file_date > to_date:
                continue

            async with aiofiles.open(ndjson_path, "r", encoding="utf-8") as fh:
                async for raw_line in fh:
                    line = raw_line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    # Apply filters
                    if filters.get("event_type") and entry.get("event_type") != filters["event_type"]:
                        continue
                    if filters.get("module") and entry.get("module") != filters["module"]:
                        continue

                    all_entries.append(entry)

        total = len(all_entries)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = all_entries[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "entries": paginated,
        }

    async def export_bundle(self) -> str:
        """
        Concatenate all daily NDJSON files into a single timestamped export bundle.
        Returns the absolute path to the created bundle file.
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        bundle_path = self._dir / f"audit_export_{timestamp}.ndjson"

        ndjson_files = sorted(self._dir.glob("compliance_audit_*.ndjson"))
        async with aiofiles.open(bundle_path, "w", encoding="utf-8") as out_fh:
            for ndjson_path in ndjson_files:
                async with aiofiles.open(ndjson_path, "r", encoding="utf-8") as in_fh:
                    async for line in in_fh:
                        await out_fh.write(line)

        log.info("audit_bundle_exported", path=str(bundle_path))
        return str(bundle_path)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

audit_logger = AuditLogger()
