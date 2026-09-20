"""
SWIFT MT String Builder (Reverse of mx_translator.py)

Builds raw SWIFT MT message strings from a structured dict produced
by mx_parser.MXParser.

Supported output types:
    MT103        — FI-to-FI Customer Credit Transfer (CBPR+)
    MT103STP     — MT103 Straight-Through Processing variant
    MT202        — FI-to-FI Credit Transfer CORE (CBPR+)
    MT202COV     — FI-to-FI Cover Payment (CBPR+)
    MT204        — FI Financial Debit Advice (CBPR+)
    MT205        — Canadian domestic FI-to-FI Transfer (LYNX legacy)
    MT205COV     — Canadian domestic Cover Payment (LYNX legacy)
    MT103RETURN  — Payment Return for MT103/pacs.008
    MT202RETURN  — Payment Return for MT202/pacs.009 (CBPR+)
    MT205RETURN  — Payment Return for MT205/pacs.009 (LYNX)

SWIFT block structure:
    {1:F01<SENDER_BIC>0000000000}
    {2:I<TYPE><RECEIVER_BIC>N}
    {3:{108:<REF>}{121:<UETR>}}   ← block 3 with UETR (R2025 mandatory)
    {4:\n:20:<REF>\n...-}
    {5:{CHK:ABCDEF012345}}
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Sender BIC used in block 1 when not derivable from parsed data
# ---------------------------------------------------------------------------

_DEFAULT_SENDER_BIC = "CAWIRECA0XXX"   # Canada Wire Payment System placeholder


def _sender_bic_padded(bic: str) -> str:
    """Pad or trim BIC to 12 characters for block 1."""
    bic = (bic or _DEFAULT_SENDER_BIC).upper().replace(" ", "")
    # BIC is 8 or 11 chars; block 1 needs 12 (append 'X' to 11-char BICs)
    if len(bic) == 8:
        bic += "XXXX"
    elif len(bic) == 11:
        bic += "X"
    return bic[:12]


def _receiver_bic(bic: str, fallback: str = "CAWIRECA0XXX") -> str:
    b = (bic or fallback).upper().replace(" ", "")
    if len(b) == 8:
        b += "XXXX"
    elif len(b) == 11:
        b += "X"
    return b[:12]


def _checksum(block4: str) -> str:
    """Compute a 12-char hex checksum for block 5 (SHA-256 first 6 bytes)."""
    return hashlib.sha256(block4.encode()).hexdigest()[:12].upper()


def _now_yymmdd() -> str:
    return datetime.now(timezone.utc).strftime("%y%m%d")


def _uetr(value: str) -> str:
    """Validate/return a UETR; generate a new UUID4 if invalid."""
    try:
        uuid.UUID(value, version=4)
        return value
    except (ValueError, AttributeError, TypeError):
        return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# MT Builder
# ---------------------------------------------------------------------------


class MTBuilder:
    """
    Deterministic ISO 20022 → SWIFT MT string builder.
    Each build_* method returns a complete raw MT message string.
    """

    # ── Public routing ────────────────────────────────────────────────

    def build(
        self,
        parsed: Dict[str, Any],
        target_mt: str,
    ) -> str:
        """
        Build the raw SWIFT MT string for the requested target_mt type.

        Args:
            parsed:    Structured dict from mx_parser.MXParser.parse()
            target_mt: One of MT103, MT103STP, MT202, MT202COV, MT204,
                       MT205, MT205COV, MT103RETURN, MT202RETURN, MT205RETURN

        Returns:
            Raw SWIFT MT string with block delimiters.

        Raises:
            ValueError on unsupported target_mt.
        """
        target_mt = target_mt.upper().strip()
        builders = {
            "MT103":        self.build_mt103,
            "MT103STP":     self.build_mt103stp,
            "MT202":        self.build_mt202,
            "MT202COV":     self.build_mt202cov,
            "MT204":        self.build_mt204,
            "MT205":        self.build_mt205,
            "MT205COV":     self.build_mt205cov,
            "MT103RETURN":  self.build_mt103return,
            "MT202RETURN":  self.build_mt202return,
            "MT205RETURN":  self.build_mt205return,
        }
        fn = builders.get(target_mt)
        if not fn:
            supported = sorted(builders.keys())
            raise ValueError(
                f"Unsupported target_mt '{target_mt}'. "
                f"Must be one of: {supported}"
            )
        return fn(parsed)

    # ── MT103 ─────────────────────────────────────────────────────────

    def build_mt103(self, parsed: Dict[str, Any]) -> str:
        return self._build_mt103_core(parsed, stp=False)

    def build_mt103stp(self, parsed: Dict[str, Any]) -> str:
        return self._build_mt103_core(parsed, stp=True)

    def _build_mt103_core(self, parsed: Dict[str, Any], stp: bool) -> str:
        f = parsed.get("fields", {})
        uetr_val = _uetr(parsed.get("uetr", ""))
        ref = f.get("transaction_reference", str(uuid.uuid4())[:16])
        val_ccy_amt = f.get("value_date_currency_amount", "")
        instd_amt = f.get("instructed_amount", "")
        ordering_cust = f.get("ordering_customer", "")
        ordering_inst = f.get("ordering_institution", "")
        sndr_corr = f.get("sender_correspondent", "")
        rcvr_corr = f.get("receiver_correspondent", "")
        intrmy = f.get("intermediary_institution", "")
        awi = f.get("account_with_institution", "")
        bene = f.get("beneficiary_customer", "")
        chrgbr = f.get("details_of_charges", "SHA")
        rmt = f.get("remittance_info", "")
        purpose = f.get("transaction_type_code", "")

        # Determine sender/receiver BICs
        sndr = _sender_bic_padded(ordering_inst or _DEFAULT_SENDER_BIC)
        rcvr = _receiver_bic(awi or _DEFAULT_SENDER_BIC)

        mt_type = "103"
        block3_extra = "{119:STP}" if stp else ""

        block4_lines = [
            f":20:{ref}",
            ":23B:CRED",
            f":32A:{val_ccy_amt}" if val_ccy_amt else "",
            f":33B:{instd_amt}" if instd_amt else "",
            f":50K:{ordering_cust}" if ordering_cust else "",
            f":52A:{ordering_inst}" if ordering_inst else "",
            f":53B:{sndr_corr}" if sndr_corr else "",
            f":54A:{rcvr_corr}" if rcvr_corr else "",
            f":56A:{intrmy}" if intrmy else "",
            f":57A:{awi}" if awi else "",
            f":59:{bene}" if bene else "",
            f":70:{rmt}" if rmt else "",
            f":71A:{chrgbr}",
            f":26T:{purpose}" if purpose else "",
        ]

        return self._assemble(sndr, rcvr, mt_type, ref, uetr_val, block3_extra, block4_lines)

    # ── MT202 ─────────────────────────────────────────────────────────

    def build_mt202(self, parsed: Dict[str, Any]) -> str:
        return self._build_mt202_core(parsed, mt_type="202")

    def build_mt204(self, parsed: Dict[str, Any]) -> str:
        return self._build_mt202_core(parsed, mt_type="204")

    def _build_mt202_core(self, parsed: Dict[str, Any], mt_type: str = "202") -> str:
        f = parsed.get("fields", {})
        uetr_val = _uetr(parsed.get("uetr", ""))
        ref = f.get("transaction_reference", str(uuid.uuid4())[:16])
        related = f.get("related_reference", ref)
        val_ccy_amt = f.get("value_date_currency_amount", "")
        ordering_inst = f.get("ordering_institution", "")
        sndr_corr = f.get("sender_correspondent", "")
        rcvr_corr = f.get("receiver_correspondent", "")
        intrmy = f.get("intermediary_institution", "")
        awi = f.get("account_with_institution", "")
        bene_inst = f.get("beneficiary_institution", "")

        sndr = _sender_bic_padded(ordering_inst or _DEFAULT_SENDER_BIC)
        rcvr = _receiver_bic(bene_inst or _DEFAULT_SENDER_BIC)

        block4_lines = [
            f":20:{ref}",
            f":21:{related}",
            f":32A:{val_ccy_amt}" if val_ccy_amt else "",
            f":52A:{ordering_inst}" if ordering_inst else "",
            f":53A:{sndr_corr}" if sndr_corr else "",
            f":54A:{rcvr_corr}" if rcvr_corr else "",
            f":56A:{intrmy}" if intrmy else "",
            f":57A:{awi}" if awi else "",
            f":58A:{bene_inst}" if bene_inst else "",
        ]

        return self._assemble(sndr, rcvr, mt_type, ref, uetr_val, "", block4_lines)

    # ── MT202COV ──────────────────────────────────────────────────────

    def build_mt202cov(self, parsed: Dict[str, Any]) -> str:
        return self._build_cov_core(parsed, mt_type="202")

    # ── MT205 — LYNX Domestic Interbank ───────────────────────────────

    def build_mt205(self, parsed: Dict[str, Any]) -> str:
        """
        MT205 — Canadian domestic FI-to-FI credit transfer (LYNX legacy).
        Structurally identical to MT202 but uses message type 205.
        Contains /LYNXSYS/ indicator in :72: for LYNX routing.
        """
        f = parsed.get("fields", {})
        uetr_val = _uetr(parsed.get("uetr", ""))
        ref = f.get("transaction_reference", str(uuid.uuid4())[:16])
        related = f.get("related_reference", ref)
        val_ccy_amt = f.get("value_date_currency_amount", "")
        ordering_inst = f.get("ordering_institution", "")
        sndr_corr = f.get("sender_correspondent", "")
        rcvr_corr = f.get("receiver_correspondent", "")
        intrmy = f.get("intermediary_institution", "")
        awi = f.get("account_with_institution", "")
        bene_inst = f.get("beneficiary_institution", "")

        sndr = _sender_bic_padded(ordering_inst or _DEFAULT_SENDER_BIC)
        rcvr = _receiver_bic(bene_inst or _DEFAULT_SENDER_BIC)

        block4_lines = [
            f":20:{ref}",
            f":21:{related}",
            f":32A:{val_ccy_amt}" if val_ccy_amt else "",
            f":52A:{ordering_inst}" if ordering_inst else "",
            f":53A:{sndr_corr}" if sndr_corr else "",
            f":54A:{rcvr_corr}" if rcvr_corr else "",
            f":56A:{intrmy}" if intrmy else "",
            f":57A:{awi}" if awi else "",
            f":58A:{bene_inst}" if bene_inst else "",
            # LYNX routing indicator
            ":72:/LYNXSYS/RTGS-CAD-DOMESTIC",
        ]

        return self._assemble(sndr, rcvr, "205", ref, uetr_val, "", block4_lines)

    # ── MT205COV — LYNX Domestic Cover Payment ────────────────────────

    def build_mt205cov(self, parsed: Dict[str, Any]) -> str:
        """
        MT205COV — Canadian domestic cover payment (LYNX legacy).
        Like MT202COV but with type code 205 and LYNX routing.
        UETR rule: LYNX pacs.009COV carries the SAME UETR as pacs.008.
        """
        return self._build_cov_core(parsed, mt_type="205", lynx=True)

    def _build_cov_core(
        self,
        parsed: Dict[str, Any],
        mt_type: str = "202",
        lynx: bool = False,
    ) -> str:
        f = parsed.get("fields", {})
        uetr_val = _uetr(parsed.get("uetr", ""))
        ref = f.get("transaction_reference", str(uuid.uuid4())[:16])
        related = f.get("related_reference", ref)
        val_ccy_amt = f.get("value_date_currency_amount", "")
        ordering_inst = f.get("ordering_institution", "")
        sndr_corr = f.get("sender_correspondent", "")
        rcvr_corr = f.get("receiver_correspondent", "")
        intrmy = f.get("intermediary_institution", "")
        awi = f.get("account_with_institution", "")
        bene_inst = f.get("beneficiary_institution", "")

        # Underlying customer data (COV-specific)
        oc = f.get("underlying_ordering_customer", "")
        ub = f.get("underlying_beneficiary", "")

        sndr = _sender_bic_padded(ordering_inst or _DEFAULT_SENDER_BIC)
        rcvr = _receiver_bic(bene_inst or _DEFAULT_SENDER_BIC)

        # Block 3 COV indicator
        block3_extra = "{119:COV}"

        block4_lines = [
            f":20:{ref}",
            f":21:{related}",
            f":32A:{val_ccy_amt}" if val_ccy_amt else "",
            f":52A:{ordering_inst}" if ordering_inst else "",
            f":53A:{sndr_corr}" if sndr_corr else "",
            f":54A:{rcvr_corr}" if rcvr_corr else "",
            f":56A:{intrmy}" if intrmy else "",
            f":57A:{awi}" if awi else "",
            f":58A:{bene_inst}" if bene_inst else "",
            # Underlying customer fields (mandatory in COV)
            f":50K:{oc}" if oc else "",
            f":59:{ub}" if ub else "",
        ]

        if lynx:
            block4_lines.append(":72:/LYNXSYS/RTGS-CAD-COV")

        return self._assemble(sndr, rcvr, mt_type, ref, uetr_val, block3_extra, block4_lines)

    # ── MT103RETURN ───────────────────────────────────────────────────

    def build_mt103return(self, parsed: Dict[str, Any]) -> str:
        return self._build_return_core(parsed, mt_type="103")

    # ── MT202RETURN ───────────────────────────────────────────────────

    def build_mt202return(self, parsed: Dict[str, Any]) -> str:
        return self._build_return_core(parsed, mt_type="202")

    # ── MT205RETURN — LYNX Domestic Return ───────────────────────────

    def build_mt205return(self, parsed: Dict[str, Any]) -> str:
        """
        MT205RETURN — Return of a LYNX MT205 domestic interbank transfer.
        Structurally identical to MT202RETURN with LYNX routing in :72:.
        """
        return self._build_return_core(parsed, mt_type="205", lynx=True)

    def _build_return_core(
        self,
        parsed: Dict[str, Any],
        mt_type: str = "103",
        lynx: bool = False,
    ) -> str:
        f = parsed.get("fields", {})
        uetr_val = _uetr(parsed.get("uetr", ""))
        original_uetr = parsed.get("original_uetr", "")
        ref = f.get("transaction_reference", str(uuid.uuid4())[:16])
        related = f.get("related_reference", ref)
        val_ccy_amt = f.get("value_date_currency_amount", "")
        ordering_inst = f.get("ordering_institution", "")
        awi = f.get("account_with_institution", "")
        bene_inst = f.get("beneficiary_institution", "")
        s2r_info = f.get("sender_to_receiver_info", "/RETN/AGNT")

        sndr = _sender_bic_padded(ordering_inst or _DEFAULT_SENDER_BIC)
        rcvr = _receiver_bic(bene_inst or ordering_inst or _DEFAULT_SENDER_BIC)

        block4_lines = [
            f":20:{ref}",
            f":21:{related}",
            f":32A:{val_ccy_amt}" if val_ccy_amt else "",
            f":52A:{ordering_inst}" if ordering_inst else "",
            f":57A:{awi}" if awi else "",
            f":58A:{bene_inst}" if bene_inst else "",
            f":72:{s2r_info}" if s2r_info else "",
        ]

        if lynx:
            block4_lines.append(":72:/LYNXSYS/RTGS-CAD-RETURN")

        # Include original UETR reference in :72: if available
        if original_uetr and "/RETN/" in s2r_info.upper():
            block4_lines.append(f"/ORGNLUETR/{original_uetr}")

        return self._assemble(sndr, rcvr, mt_type, ref, uetr_val, "", block4_lines)

    # ── Block assembler ───────────────────────────────────────────────

    def _assemble(
        self,
        sender_bic: str,
        receiver_bic: str,
        mt_type: str,
        ref: str,
        uetr_val: str,
        block3_extra: str,
        block4_lines: list[str],
    ) -> str:
        """
        Assemble a complete SWIFT MT message string from components.

        Block 1: F01 + sender_bic + 0000000000
        Block 2: I + mt_type + receiver_bic + N
        Block 3: {108:<ref>}{121:<uetr>} + optional extra (e.g. {119:STP})
        Block 4: tag fields
        Block 5: CHK checksum
        """
        # Clean block4 lines — remove blanks
        lines = [ln for ln in block4_lines if ln and ln.strip()]
        block4_body = "\n".join(lines)

        block1 = f"{{1:F01{sender_bic}0000000000}}"
        block2 = f"{{2:I{mt_type}{receiver_bic}N}}"
        block3 = f"{{3:{{108:{ref[:16]}}}{{121:{uetr_val}}}{block3_extra}}}"
        block4 = f"{{4:\n{block4_body}\n-}}"
        block5 = f"{{5:{{CHK:{_checksum(block4_body)}}}}}"

        return f"{block1}{block2}{block3}{block4}{block5}"


# ---------------------------------------------------------------------------
# Auto-detect target MT from parsed dict
# ---------------------------------------------------------------------------


def auto_detect_target_mt(parsed: Dict[str, Any]) -> str:
    """
    Given a parsed dict from mx_parser, determine the correct target MT type.

    CBPR+ rules:
        pacs.008 STANDARD → MT103
        pacs.008 STP      → MT103STP
        pacs.009 CORE     → MT202
        pacs.009 COV      → MT202COV
        pacs.004 (pacs.008 return) → MT103RETURN
        pacs.004 (pacs.009 return) → MT202RETURN

    LYNX rules:
        pacs.008          → MT103   (same as CBPR+)
        pacs.009 CORE     → MT205   ← LYNX domestic equivalent
        pacs.009 COV      → MT205COV
        pacs.004 (any)    → MT205RETURN
    """
    src = parsed.get("source_type", "")
    variant = parsed.get("variant", "STANDARD")
    scheme = parsed.get("scheme", "CBPR+").upper()

    if "pacs.008" in src:
        return "MT103STP" if variant == "STP" else "MT103"

    elif "pacs.009" in src:
        if scheme == "LYNX":
            return "MT205COV" if variant == "COV" else "MT205"
        else:
            return "MT202COV" if variant == "COV" else "MT202"

    elif "pacs.004" in src:
        if scheme == "LYNX":
            return "MT205RETURN"
        # CBPR+: depends on what was originally returned
        return "MT202RETURN" if variant == "PACS009_RETURN" else "MT103RETURN"

    raise ValueError(f"Cannot auto-detect MT for source_type='{src}' variant='{variant}'")


# Module-level singleton
mt_builder = MTBuilder()
