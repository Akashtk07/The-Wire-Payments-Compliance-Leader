"""
ISO 20022 XSD + CBPR+ R2025 Business-Rule Validator.

Validation pipeline:
  1. XSD schema validation (if .xsd file is found in ./data/xsd/)
  2. Structural parse verification (lxml)
  3. Post-schema SWIFT CBPR+ R2025 business rule checks

CBPR+ R2025 Rules enforced (effective Nov 22, 2025):
  - UETR (UUID4) mandatory in PmtId/UETR for every pacs message
  - ChrgBr = SHAR mandatory for interbank pacs.008 / pacs.004
  - PostalAddress: TownName and Country mandatory in structured/hybrid mode
  - pacs.009 CORE must NOT contain retail customer elements
  - pacs.009 COV must contain UndrlygCstmrCdtTrf block
  - pacs.004 must contain OrgnlUETR, OrgnlMsgId, and valid RtrRsnInf/Rsn/Cd
  - Return reason codes validated against CBPR+ R2025 extended list

Supported message types: pacs.008.001.08, pacs.009.001.08, pacs.004.001.09
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import structlog
from lxml import etree

from config import settings

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Namespace maps for XPath lookups
# ---------------------------------------------------------------------------

_NS_MAP: Dict[str, str] = {
    "pacs008": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
    "pacs009": "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08",
    "pacs004": "urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09",
}

# ---------------------------------------------------------------------------
# CBPR+ R2025 — Extended return reason code list
# ---------------------------------------------------------------------------

_VALID_RETURN_CODES = {
    # Original set
    "AM09", "AGNT", "CUST", "DUPL", "UPAY", "NARR", "FOCR", "FF01",
    # R2025 additions
    "AC04", "AC06", "BE04", "MD01", "MD07", "MS02", "MS03",
    "RC01", "RR01", "RR02", "RR03", "RR04", "SL01",
    "ARDT", "CNOR", "CNPC", "CURR",
}

# CBPR+ R2025: ChrgBr permitted in interbank context
_VALID_CHRGBR_INTERBANK = {"SHAR"}   # DEBT and CRED are not valid at interbank level

# UUID4 pattern
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# ISO 2-letter country code
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")

# ---------------------------------------------------------------------------
# XSD cache (loaded once per process)
# ---------------------------------------------------------------------------

_xsd_cache: Dict[str, Optional[etree.XMLSchema]] = {}


def _load_xsd(message_type: str) -> Optional[etree.XMLSchema]:
    """Load and cache the XSD for a given message type from ./data/xsd/."""
    if message_type in _xsd_cache:
        return _xsd_cache[message_type]

    xsd_path = Path(settings.XSD_DIR) / f"{message_type}.xsd"
    if not xsd_path.exists():
        log.warning("xsd_not_found", message_type=message_type, path=str(xsd_path))
        _xsd_cache[message_type] = None
        return None

    try:
        with open(xsd_path, "rb") as fh:
            xsd_doc = etree.parse(fh)
        schema = etree.XMLSchema(xsd_doc)
        _xsd_cache[message_type] = schema
        log.info("xsd_loaded", message_type=message_type)
        return schema
    except Exception as exc:
        log.error("xsd_load_failed", message_type=message_type, error=str(exc))
        _xsd_cache[message_type] = None
        return None


# ---------------------------------------------------------------------------
# CBPR+ R2025 helper: UETR validation
# ---------------------------------------------------------------------------

def _validate_uetr(uetr_text: str | None, context: str) -> List[str]:
    """
    Return error list if UETR is missing or not a valid UUID4.
    CBPR+ R2025: UETR is mandatory and must be UUID version 4.
    """
    errors: List[str] = []
    if not uetr_text:
        errors.append(
            f"[RULE:CBPR+R2025] {context}: <UETR> is mandatory under CBPR+ R2025 "
            "and must be present in <PmtId>."
        )
        return errors
    if not _UUID4_RE.match(uetr_text.strip()):
        errors.append(
            f"[RULE:CBPR+R2025] {context}: <UETR> value '{uetr_text}' is not a "
            "valid UUID4 format (xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx). "
            "CBPR+ R2025 mandates UUID version 4."
        )
    return errors


# ---------------------------------------------------------------------------
# CBPR+ R2025 business rule checks — pacs.008
# ---------------------------------------------------------------------------

def _check_pacs008(root: etree._Element, ns: str) -> List[str]:
    errors: List[str] = []
    ns_map = {"x": ns}

    # ── Mandatory structural elements ────────────────────────────────────────
    required_elements = {
        "Dbtr":            ".//x:Dbtr",
        "Cdtr":            ".//x:Cdtr",
        "DbtrAgt":         ".//x:DbtrAgt",
        "CdtrAgt":         ".//x:CdtrAgt",
        "IntrBkSttlmAmt":  ".//x:IntrBkSttlmAmt",
        "IntrBkSttlmDt":   ".//x:IntrBkSttlmDt",
        "PmtId":           ".//x:PmtId",
    }
    for name, xpath in required_elements.items():
        if not root.findall(xpath, ns_map):
            errors.append(
                f"[RULE:CBPR+R2025] pacs.008 must contain <{name}> — element not found."
            )

    # ── R2025: UETR mandatory ────────────────────────────────────────────────
    uetr_els = root.findall(".//x:PmtId/x:UETR", ns_map)
    if not uetr_els:
        errors.append(
            "[RULE:CBPR+R2025] pacs.008: <PmtId><UETR> is mandatory under CBPR+ R2025. "
            "Every credit transfer must carry a UUID4 UETR."
        )
    else:
        errors.extend(_validate_uetr(uetr_els[0].text, "pacs.008"))

    # ── R2025: ChrgBr must be SHAR for interbank ────────────────────────────
    chrgbr_els = root.findall(".//x:ChrgBr", ns_map)
    if not chrgbr_els:
        errors.append(
            "[RULE:CBPR+R2025] pacs.008: <ChrgBr> is mandatory. "
            "Must be 'SHAR' for CBPR+ interbank messages."
        )
    else:
        for el in chrgbr_els:
            val = (el.text or "").strip()
            if val not in _VALID_CHRGBR_INTERBANK:
                errors.append(
                    f"[RULE:CBPR+R2025] pacs.008: <ChrgBr> value '{val}' is not permitted "
                    "at the interbank level under CBPR+ R2025. "
                    "Only 'SHAR' is valid for FI-to-FI credit transfers. "
                    "DEBT (OUR) and CRED (BEN) are not permitted at interbank level."
                )

    # ── R2025: PostalAddress hybrid — TownName and Country mandatory ─────────
    # Check both Dbtr and Cdtr postal addresses
    for party in ["Dbtr", "Cdtr"]:
        for pstl_adr in root.findall(f".//x:{party}/x:PstlAdr", ns_map):
            has_town = bool(pstl_adr.findall("x:TwnNm", ns_map))
            has_country = bool(pstl_adr.findall("x:Ctry", ns_map))

            # Validate country code format if present
            country_els = pstl_adr.findall("x:Ctry", ns_map)
            for c_el in country_els:
                country_val = (c_el.text or "").strip()
                if country_val and not _COUNTRY_RE.match(country_val):
                    errors.append(
                        f"[RULE:CBPR+R2025] pacs.008: <{party}><PstlAdr><Ctry> value "
                        f"'{country_val}' must be a valid ISO 2-letter country code."
                    )

            if not has_town:
                errors.append(
                    f"[RULE:CBPR+R2025] pacs.008: <{party}><PstlAdr><TwnNm> is mandatory "
                    "in CBPR+ R2025 structured and hybrid postal addresses."
                )
            if not has_country:
                errors.append(
                    f"[RULE:CBPR+R2025] pacs.008: <{party}><PstlAdr><Ctry> is mandatory "
                    "in CBPR+ R2025 structured and hybrid postal addresses."
                )


    return errors


# ---------------------------------------------------------------------------
# CBPR+ R2025 business rule checks — pacs.009 CORE
# ---------------------------------------------------------------------------

def _check_pacs009_core(root: etree._Element, ns: str) -> List[str]:
    errors: List[str] = []
    ns_map = {"x": ns}

    # pacs.009 CORE must NOT have retail customer data at top level
    prohibited = {
        "UltmtDbtr": ".//x:UltmtDbtr",
        "UltmtCdtr": ".//x:UltmtCdtr",
    }
    for name, xpath in prohibited.items():
        if root.findall(xpath, ns_map):
            errors.append(
                f"[RULE:CBPR+R2025] pacs.009 CORE must NOT contain <{name}> — "
                "use pacs.009 COV (MT202COV) for underlying customer data."
            )

    # R2025: UETR mandatory
    uetr_els = root.findall(".//x:PmtId/x:UETR", ns_map)
    if not uetr_els:
        errors.append(
            "[RULE:CBPR+R2025] pacs.009: <PmtId><UETR> is mandatory under CBPR+ R2025."
        )
    else:
        errors.extend(_validate_uetr(uetr_els[0].text, "pacs.009 CORE"))

    # R2025: ChrgBr = SHAR
    chrgbr_els = root.findall(".//x:ChrgBr", ns_map)
    for el in chrgbr_els:
        val = (el.text or "").strip()
        if val not in _VALID_CHRGBR_INTERBANK:
            errors.append(
                f"[RULE:CBPR+R2025] pacs.009 CORE: <ChrgBr> value '{val}' is not valid "
                "for CBPR+ interbank. Must be 'SHAR'."
            )

    return errors


# ---------------------------------------------------------------------------
# CBPR+ R2025 business rule checks — pacs.009 COV
# ---------------------------------------------------------------------------

def _check_pacs009_cov(root: etree._Element, ns: str) -> List[str]:
    errors: List[str] = []
    ns_map = {"x": ns}

    undrlg = root.findall(".//x:UndrlygCstmrCdtTrf", ns_map)
    if not undrlg:
        errors.append(
            "[RULE:CBPR+R2025] pacs.009 COV must contain <UndrlygCstmrCdtTrf> block "
            "(underlying customer credit transfer). Use MT202COV as source."
        )
    else:
        # COV underlying block must have Dbtr and Cdtr
        undrlg_el = undrlg[0]
        if not undrlg_el.findall("x:Dbtr", ns_map):
            errors.append(
                "[RULE:CBPR+R2025] pacs.009 COV <UndrlygCstmrCdtTrf>: "
                "<Dbtr> (underlying debtor) is required."
            )
        if not undrlg_el.findall("x:Cdtr", ns_map):
            errors.append(
                "[RULE:CBPR+R2025] pacs.009 COV <UndrlygCstmrCdtTrf>: "
                "<Cdtr> (underlying creditor) is required."
            )

    # R2025: UETR mandatory
    uetr_els = root.findall(".//x:PmtId/x:UETR", ns_map)
    if not uetr_els:
        errors.append(
            "[RULE:CBPR+R2025] pacs.009 COV: <PmtId><UETR> is mandatory under CBPR+ R2025."
        )
    else:
        errors.extend(_validate_uetr(uetr_els[0].text, "pacs.009 COV"))

    return errors


# ---------------------------------------------------------------------------
# CBPR+ R2025 business rule checks — pacs.004
# ---------------------------------------------------------------------------

def _check_pacs004(root: etree._Element, ns: str) -> List[str]:
    errors: List[str] = []
    ns_map = {"x": ns}

    # ── OrgnlUETR — mandatory in pacs.004 ────────────────────────────────────
    orgn_uetr_els = root.findall(".//x:OrgnlUETR", ns_map)
    if not orgn_uetr_els:
        errors.append(
            "[RULE:CBPR+R2025] pacs.004 must contain <OrgnlUETR> — "
            "the UUID4 UETR of the original transaction being returned."
        )
    else:
        uetr_text = (orgn_uetr_els[0].text or "").strip()
        if not _UUID4_RE.match(uetr_text):
            errors.append(
                f"[RULE:CBPR+R2025] pacs.004: <OrgnlUETR> value '{uetr_text}' "
                "is not a valid UUID4. The original transaction's UETR must be preserved exactly."
            )

    # ── OrgnlMsgId — mandatory ────────────────────────────────────────────────
    if not root.findall(".//x:OrgnlMsgId", ns_map):
        errors.append(
            "[RULE:CBPR+R2025] pacs.004 must contain <OrgnlMsgId> — "
            "the MsgId of the original message being returned."
        )

    # ── RtrId — mandatory ─────────────────────────────────────────────────────
    if not root.findall(".//x:RtrId", ns_map):
        errors.append(
            "[RULE:CBPR+R2025] pacs.004 must contain <RtrId> — "
            "a unique identifier for this return transaction."
        )

    # ── RtrRsnInf/Rsn/Cd — return reason code ────────────────────────────────
    reason_codes = root.findall(".//x:Rsn/x:Cd", ns_map)
    if not reason_codes:
        errors.append(
            "[RULE:CBPR+R2025] pacs.004 must contain <RtrRsnInf><Rsn><Cd> with a "
            f"valid external return reason code. "
            f"CBPR+ R2025 valid codes include: "
            f"{', '.join(sorted(_VALID_RETURN_CODES)[:12])} ..."
        )
    else:
        for rc_el in reason_codes:
            code = (rc_el.text or "").strip()
            if code not in _VALID_RETURN_CODES:
                errors.append(
                    f"[RULE:CBPR+R2025] pacs.004: <Rsn><Cd> value '{code}' is not in the "
                    f"CBPR+ R2025 approved return reason code list. "
                    f"Common valid codes: AM09 (wrong amount), AGNT (agent decision), "
                    f"CUST (customer request), DUPL (duplicate), AC04 (closed account)."
                )

    # ── ChrgBr = SHAR mandatory for pacs.004 ─────────────────────────────────
    chrgbr_els = root.findall(".//x:ChrgBr", ns_map)
    if chrgbr_els:
        for el in chrgbr_els:
            val = (el.text or "").strip()
            if val not in _VALID_CHRGBR_INTERBANK:
                errors.append(
                    f"[RULE:CBPR+R2025] pacs.004: <ChrgBr> value '{val}' is not valid "
                    "for CBPR+ returns. Must be 'SHAR'."
                )

    return errors


# ---------------------------------------------------------------------------
# Validator class
# ---------------------------------------------------------------------------


class ISO20022Validator:
    """
    ISO 20022 XSD + CBPR+ R2025 SWIFT business-rule validator.

    Rules enforced per CBPR+ Release 2025 (effective Nov 22, 2025):
      - UETR mandatory and UUID4-validated
      - ChrgBr = SHAR for interbank
      - PostalAddress: TownName + Country mandatory in hybrid/structured mode
      - Extended return reason code list
      - UndrlygCstmrCdtTrf required in pacs.009 COV
    """

    async def validate(
        self,
        xml_string: str,
        message_type: str,
    ) -> Tuple[bool, List[str]]:
        """
        Validate *xml_string* against XSD (if available) and CBPR+ R2025 rules.

        Returns (is_valid, list_of_errors).
        Error strings are prefixed with:
          [XSD]            — XSD schema violation
          [RULE:CBPR+R2025]— CBPR+ R2025 business rule violation
          [WARN:CBPR+R2025]— Non-fatal recommendation (not counted as error)
        """
        errors: List[str] = []
        warnings: List[str] = []

        # ── Step 1: Parse XML ─────────────────────────────────────────────────
        try:
            xml_bytes = xml_string.encode("utf-8") if isinstance(xml_string, str) else xml_string
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError as exc:
            return False, [f"[XSD] XML parse error: {exc}"]

        # ── Step 2: XSD validation ────────────────────────────────────────────
        schema = _load_xsd(message_type)
        if schema:
            valid = schema.validate(root)
            if not valid:
                for xsd_err in schema.error_log:
                    errors.append(f"[XSD] Line {xsd_err.line}: {xsd_err.message}")
        else:
            if root is None:
                errors.append(
                    "[XSD] Document element missing — no XSD available for full validation."
                )
            else:
                log.debug("xsd_fallback_structural_only", message_type=message_type)

        # ── Step 3: CBPR+ R2025 business rules ───────────────────────────────
        ns = root.nsmap.get(None, "")

        rule_errors: List[str] = []
        if message_type.startswith("pacs.008"):
            rule_errors = _check_pacs008(root, ns)
        elif message_type.startswith("pacs.009"):
            cov_ns_map = {"x": ns}
            has_underlying = bool(root.findall(".//x:UndrlygCstmrCdtTrf", cov_ns_map))
            if has_underlying:
                rule_errors = _check_pacs009_cov(root, ns)
            else:
                rule_errors = _check_pacs009_core(root, ns)
        elif message_type.startswith("pacs.004"):
            rule_errors = _check_pacs004(root, ns)

        # Separate warnings from hard errors
        for item in rule_errors:
            if item.startswith("[WARN:"):
                warnings.append(item)
            else:
                errors.append(item)

        # Append warnings at end (not counted as errors)
        all_messages = errors + warnings

        is_valid = len(errors) == 0
        log.info(
            "cbpr_r2025_validation_complete",
            message_type=message_type,
            is_valid=is_valid,
            error_count=len(errors),
            warning_count=len(warnings),
        )
        return is_valid, all_messages


# Module-level singleton
iso20022_validator = ISO20022Validator()
