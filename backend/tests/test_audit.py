"""
Pytest tests for the AuditLogger service.

Tests cover:
  - PII masking: IBAN is replaced with [MASKED] in written log files
  - SHA-256 chain integrity: 3 consecutive entries form an unbroken chain
  - Export bundle: export_bundle() creates a file on disk
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

# Ensure the backend root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.audit_logger import AuditLogger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_test_logger(tmp_dir: str) -> AuditLogger:
    """Create an isolated AuditLogger that writes to a temp directory."""
    return AuditLogger(audit_dir=tmp_dir)


# ---------------------------------------------------------------------------
# Test 1: PII masking — IBAN must not appear in log files
# ---------------------------------------------------------------------------


def test_pii_not_in_logs():
    """
    Write an audit entry containing a real-looking IBAN.
    Read back the NDJSON file and assert the IBAN is replaced with [MASKED].
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        logger = _make_test_logger(tmp_dir)

        fake_iban = "GB29NWBK60161331926819"
        run(
            logger.log(
                event_type="TEST_PII",
                module="test",
                status="SUCCESS",
                details={
                    "ordering_customer_iban": fake_iban,
                    "note": f"Customer IBAN is {fake_iban}",
                },
            )
        )

        # Find the written file
        ndjson_files = list(Path(tmp_dir).glob("compliance_audit_*.ndjson"))
        assert len(ndjson_files) == 1, "Expected exactly one audit file"

        content = ndjson_files[0].read_text(encoding="utf-8")

        # The original IBAN must NOT appear anywhere in the file
        assert fake_iban not in content, (
            f"IBAN '{fake_iban}' found in audit log — PII masking failed!\n"
            f"File content: {content}"
        )

        # [MASKED] must appear (demonstrating replacement occurred)
        assert "[MASKED]" in content, (
            "Expected [MASKED] token in log file but it was not found."
        )


# ---------------------------------------------------------------------------
# Test 2: SHA-256 hash chain integrity
# ---------------------------------------------------------------------------


def test_sha256_chain_integrity():
    """
    Write 3 audit entries and verify the hash chain:
      hash[n] == SHA-256(hash[n-1] + entry_json_without_hash[n])
    Genesis hash == SHA-256(b"").
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        logger = _make_test_logger(tmp_dir)

        for i in range(3):
            run(
                logger.log(
                    event_type="CHAIN_TEST",
                    module="test",
                    status="SUCCESS",
                    details={"sequence": i},
                )
            )

        ndjson_files = list(Path(tmp_dir).glob("compliance_audit_*.ndjson"))
        assert len(ndjson_files) == 1

        entries = []
        with open(ndjson_files[0], "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))

        assert len(entries) == 3, f"Expected 3 entries, found {len(entries)}"

        # Verify chain starting from genesis
        previous_hash = hashlib.sha256(b"").hexdigest()

        for idx, entry in enumerate(entries):
            recorded_hash = entry["hash"]

            # Re-compute: remove 'hash' key, serialise sorted, mask PII, compute
            entry_copy = {k: v for k, v in entry.items() if k != "hash"}
            entry_json = json.dumps(entry_copy, ensure_ascii=False, sort_keys=True)

            # Apply same PII masking as the logger does
            import re
            entry_json = re.sub(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4,}\b", "[MASKED]", entry_json)
            entry_json = re.sub(r"\b\d{8,}\b", "[MASKED]", entry_json)

            expected_hash = hashlib.sha256(
                (previous_hash + entry_json).encode("utf-8")
            ).hexdigest()

            assert recorded_hash == expected_hash, (
                f"Hash chain broken at entry {idx}!\n"
                f"  Expected: {expected_hash}\n"
                f"  Recorded: {recorded_hash}"
            )

            previous_hash = recorded_hash


# ---------------------------------------------------------------------------
# Test 3: Export bundle creates a file on disk
# ---------------------------------------------------------------------------


def test_audit_log_export():
    """
    After writing some entries, export_bundle() should create a .ndjson file
    on disk containing all the entries.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        logger = _make_test_logger(tmp_dir)

        # Write a few entries
        for i in range(5):
            run(
                logger.log(
                    event_type="EXPORT_TEST",
                    module="test",
                    status="SUCCESS",
                    details={"idx": i},
                )
            )

        # Export
        bundle_path = run(logger.export_bundle())

        # Assert bundle file exists and is non-empty
        assert Path(bundle_path).exists(), f"Bundle file not found: {bundle_path}"
        assert Path(bundle_path).stat().st_size > 0, "Bundle file is empty"

        # Assert bundle contains valid NDJSON entries
        with open(bundle_path, "r", encoding="utf-8") as fh:
            lines = [line.strip() for line in fh if line.strip()]

        assert len(lines) == 5, (
            f"Expected 5 entries in bundle, found {len(lines)}"
        )

        for i, line in enumerate(lines):
            entry = json.loads(line)  # Should not raise
            assert "audit_id" in entry
            assert "hash" in entry
            assert "event_type" in entry
            assert entry["event_type"] == "EXPORT_TEST"
