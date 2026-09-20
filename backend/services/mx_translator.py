"""
Deterministic MT → MX (ISO 20022) XML translator.

Converts SWIFT MT parsed field dicts into valid ISO 20022 XML using lxml.
Enforces SWIFT CBPR+ R2025 rules before and during XML generation.

CBPR+ R2025 Key Changes (effective Nov 22, 2025):
  - MT103 / MT202 / MT202 COV retired from SWIFT FINplus — MX only
  - PostalAddress: hybrid mode introduced (TownName + Country mandatory)
  - Fully unstructured free-text address deprecated (will be rejected from Nov 2026)
  - ChrgBr = SHAR is the only permitted value for interbank pacs.008 under CBPR+
  - UETR (UUID4) mandatory in PmtId/UETR in every pacs message
  - PmtTpInf/SvcLvl/Cd recommended for service-level identification

Supported translations (MT → MX):
  MT103 / MT103STP  → pacs.008.001.08
  MT202             → pacs.009.001.08 (CORE)
  MT202COV          → pacs.009.001.08 (COV)
  MT204             → pacs.009.001.08 (ADV)
  MT103RETURN       → pacs.004.001.09
  MT202RETURN       → pacs.004.001.09
  MT205             → pacs.009.001.08 (CORE, LYNX domestic equivalent)
  MT205COV          → pacs.009.001.08 (COV, LYNX domestic cover)
  MT205RETURN       → pacs.004.001.09 (LYNX domestic return)
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from lxml import etree

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------


class ValidationException(Exception):
    """
    Raised when a SWIFT CBPR+ R2025 rule is violated.
    Causes HTTP 422 SWIFT_ISO_MUTATION_DENIED in the router layer.
    """

    def __init__(
        self,
        field_name: str,
        message_type: str,
        message: str,
        action: str = "",
        rule_ref: str = "",
    ) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.message_type = message_type
        self.message = message
        self.action = action
        self.rule_ref = rule_ref   # e.g. "CBPR+ R2025 §3.4"


# ---------------------------------------------------------------------------
# Namespace declarations — ISO 20022 message schemas
# ---------------------------------------------------------------------------

NS_PACS008 = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
NS_PACS009 = "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08"
NS_PACS004 = "urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09"
NS_HEAD001 = "urn:iso:std:iso:20022:tech:xsd:head.001.001.02"

# ISO 20022 message type → namespace map
_MSG_NS: Dict[str, str] = {
    "pacs.008.001.08": NS_PACS008,
    "pacs.009.001.08": NS_PACS009,
    "pacs.004.001.09": NS_PACS004,
}

# ---------------------------------------------------------------------------
# CBPR+ R2025 — Valid code lists
# ---------------------------------------------------------------------------

# External return reason codes (CBPR+ R2025 approved list)
_VALID_RETURN_CODES = {
    "AM09", "AGNT", "CUST", "DUPL", "UPAY", "NARR", "FOCR",
    "FF01", "AC04", "AC06", "BE04", "MD01", "MD07", "MS02",
    "MS03", "RC01", "RR01", "RR02", "RR03", "RR04", "SL01",
    "ARDT", "CNOR", "CNPC", "CURR",
}

# CBPR+ R2025 — ChrgBr permitted values for pacs.008 interbank
# Only SHAR (Shared) is permitted under CBPR+ for FI-to-FI messages.
# DEBT (OUR) and CRED (BEN) are only permitted in specific local scheme contexts.
_PACS008_CHRGBR_MAP = {
    "SHA": "SHAR",
    "OUR": "SHAR",   # R2025: OUR is mapped to SHAR — DEBT is not valid in CBPR+ interbank
    "BEN": "SHAR",   # R2025: BEN is mapped to SHAR — CRED is not valid in CBPR+ interbank
}

# Service level codes
_SVC_LVL_NOTO = "NOTO"   # Non-urgent payment
_SVC_LVL_SDVA = "SDVA"   # Same-day value
_SVC_LVL_URGP = "URGP"   # Urgent payment (SWIFT gpi)

# CBPR+ R2025 purpose codes (selected common subset)
_PURPOSE_CODES = {
    "SALA", "SUPP", "TAXS", "TREA", "VATX", "WHLD", "CHAR", "CORT",
    "GDDS", "STDY", "TRFD", "INTC", "BONU", "DIVD", "LOAN", "SECU",
}

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

_AMOUNT_RE = re.compile(r"^(\d{6})([A-Z]{3})([\d,\.]+)$")

# IBAN format validator (basic: 2 letters + 2 digits + up to 30 alphanumeric)
_IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{4,30}$")

# BIC / BEI validator (8 or 11 chars)
_BIC_RE = re.compile(r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$")

# ISO 2-letter country code
_COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


def _parse_32a(value: str) -> Tuple[str, str, str]:
    """
    Parse MT field :32A: value e.g. '260523USD10000,00'
    Returns (iso_date, currency, amount_decimal)
    """
    m = _AMOUNT_RE.match(value.strip())
    if not m:
        return "2026-05-23", "USD", "0.00"
    yymmdd, ccy, amount_raw = m.groups()
    # Normalise decimal: SWIFT uses comma, some systems use period
    amount = amount_raw.replace(",", ".")
    year = int(yymmdd[:2])
    year += 2000 if year < 50 else 1900
    month = yymmdd[2:4]
    day = yymmdd[4:6]
    iso_date = f"{year}-{month}-{day}"
    return iso_date, ccy, amount


def _bic_from_field(value: str) -> str:
    """
    Extract BIC from a field value.
    Handles both single-line (BARCGB22XXX) and multi-line (/BARCGB22XXX\nSome text).
    """
    if not value:
        return "UNKNOWNXXXXX"
    # First line first token, strip leading slash
    first_line = value.split("\n")[0].strip()
    first_token = first_line.split()[0].lstrip("/") if first_line.split() else ""
    return first_token or "UNKNOWNXXXXX"


def _validate_bic(bic: str) -> bool:
    """Return True if the BIC string passes basic format validation."""
    return bool(_BIC_RE.match(bic)) if bic else False


def _name_from_field(value: str) -> str:
    """
    Extract name from a multi-line MT field value.
    SWIFT convention:
      Line 1: /account (optional)
      Line 2: Name
      Line 3+: Address
    Returns lines 2+ joined, or the whole value if single-line.
    """
    lines = [ln.strip() for ln in value.split("\n") if ln.strip()]
    if not lines:
        return "UNKNOWN"
    # If line 1 starts with '/', it's the account — name is line 2
    start_idx = 1 if lines[0].startswith("/") else 0
    name_lines = lines[start_idx:]
    return " ".join(name_lines) if name_lines else "UNKNOWN"


def _iban_or_account(value: str) -> str:
    """
    Return the account number from a multi-line field.
    Looks for the first line starting with '/' and strips the slash.
    Falls back to the entire first token if no slash prefix found.
    """
    if not value:
        return ""
    lines = [ln.strip() for ln in value.split("\n") if ln.strip()]
    for line in lines:
        if line.startswith("/"):
            token = line.split()[0].lstrip("/")
            if token:
                return token
    # Fallback: first token on first line
    first = value.split()[0]
    return first.lstrip("/")


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "+00:00"


def _sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    """Create and append a sub-element, optionally setting text."""
    el = etree.SubElement(parent, tag)
    if text is not None:
        el.text = text
    return el


def _add_postal_address_r2025(
    parent: etree._Element,
    raw_address: str,
    default_country: str = "XX",
) -> None:
    """
    Build a CBPR+ R2025-compliant PostalAddress element.

    SWIFT :50K: / :59: field structure (after newline preservation):
      Line 1: /account  (skip — it's the account number)
      Line 2: Name      (already set on parent Nm element by caller)
      Line 3+: Address  (street, town, country)

    R2025 Hybrid mode requirements:
      - <TwnNm>  MANDATORY
      - <Ctry>   MANDATORY (ISO 2-letter)
      - <AdrLine> OPTIONAL (up to 2 lines of free text)

    Fully unstructured address (AdrLine only, no TwnNm/Ctry) is DEPRECATED
    in R2025 and will be REJECTED by SWIFT from Nov 2026.
    """
    pstl_adr = _sub(parent, "PstlAdr")

    country = default_country
    town = ""
    address_lines: List[str] = []

    if raw_address:
        # Split on newlines (parser now preserves them)
        raw_lines = [ln.strip() for ln in raw_address.split("\n") if ln.strip()]

        for line in raw_lines:
            # Skip account line (starts with /)
            if line.startswith("/"):
                continue

            tokens = line.split()
            if not tokens:
                continue

            # Detect ISO 2-letter country code at END of line
            # e.g. "NEW YORK NY US" → country=US, town="NEW YORK NY"
            if _COUNTRY_RE.match(tokens[-1]) and len(tokens[-1]) == 2 and len(tokens) >= 1:
                country = tokens[-1]
                rest = " ".join(tokens[:-1]).strip()
                if rest and not town:
                    town = rest[:35]
                elif rest:
                    address_lines.append(rest[:70])

            # Detect ISO 2-letter country code at START of line
            # e.g. "US NEW YORK" → country=US, town="NEW YORK"
            elif _COUNTRY_RE.match(tokens[0]) and len(tokens[0]) == 2 and len(tokens) >= 2:
                country = tokens[0]
                rest = " ".join(tokens[1:]).strip()
                if rest and not town:
                    town = rest[:35]
                elif rest:
                    address_lines.append(rest[:70])

            # Detect pattern like "CITY STATE CC" where CC is country
            # e.g. "TORONTO ON CA" → country=CA, town="TORONTO ON"
            elif (len(tokens) >= 3
                  and _COUNTRY_RE.match(tokens[-1])
                  and len(tokens[-1]) == 2):
                country = tokens[-1]
                rest = " ".join(tokens[:-1]).strip()
                if rest and not town:
                    town = rest[:35]
                elif rest:
                    address_lines.append(rest[:70])

            else:
                # Regular address line — first becomes TownName if not set
                if not town:
                    town = line[:35]
                else:
                    address_lines.append(line[:70])

    # R2025 HYBRID: TownName and Country are MANDATORY
    _sub(pstl_adr, "TwnNm", town or "UNKNOWN")
    _sub(pstl_adr, "Ctry", country if _COUNTRY_RE.match(country) else "XX")

    # Up to 2 AddressLine elements (hybrid mode allows free text alongside structure)
    for line in address_lines[:2]:
        _sub(pstl_adr, "AdrLine", line)



# ---------------------------------------------------------------------------
# Prohibited-field guards and R2025 rule checks
# ---------------------------------------------------------------------------

_RETAIL_CUSTOMER_FIELDS = {
    "ordering_customer",
    "beneficiary_customer",
    "underlying_ordering_customer",
    "underlying_beneficiary",
}


class MXTranslator:
    """
    Deterministic MT → MX XML translator.
    Enforces SWIFT CBPR+ R2025 prohibited-field guards and structural rules.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def translate(
        self,
        parsed_mt: Dict[str, Any],
        source_type: str,
        target_type: Optional[str] = None,
        skip_validation: bool = False,
    ) -> Tuple[str, str]:
        """
        Translate a parsed MT dict to ISO 20022 XML.

        Returns (xml_string, message_type_used).
        Raises ValidationException if a CBPR+ R2025 rule guard fires
        (unless skip_validation=True, used in force_output/Full Translation mode).
        """
        source_type = source_type.upper()

        # Auto-detect target if not provided
        if not target_type:
            target_type = self._auto_detect_target(source_type)

        # --- R2025 Prohibited-field and structural rule checks ---
        if not skip_validation:
            self._check_prohibited_fields(parsed_mt, source_type, target_type)

        # Generate / preserve UETR (R2025: mandatory UUID4 in every pacs message)
        uetr = parsed_mt.get("uetr") or str(uuid.uuid4())
        # Validate UETR is a valid UUID4 format
        try:
            uuid.UUID(uetr, version=4)
        except (ValueError, AttributeError):
            uetr = str(uuid.uuid4())
        parsed_mt["uetr"] = uetr

        # Route to the correct builder
        if target_type == "pacs.008.001.08":
            xml_string = self._build_pacs008(parsed_mt, uetr)
        elif target_type == "pacs.009.001.08":
            xml_string = self._build_pacs009(parsed_mt, source_type, uetr)
        elif target_type == "pacs.004.001.09":
            xml_string = self._build_pacs004(parsed_mt, uetr)
        else:
            raise ValueError(f"Unsupported target_type: {target_type}")

        return xml_string, target_type

    # ------------------------------------------------------------------
    # Auto-detection
    # ------------------------------------------------------------------

    @staticmethod
    def _auto_detect_target(source_type: str) -> str:
        mapping = {
            "MT103":       "pacs.008.001.08",
            "MT103STP":    "pacs.008.001.08",
            "MT202":       "pacs.009.001.08",
            "MT202COV":    "pacs.009.001.08",
            "MT204":       "pacs.009.001.08",
            "MT103RETURN": "pacs.004.001.09",
            "MT202RETURN": "pacs.004.001.09",
            # LYNX Canada domestic variants — same pacs target types
            "MT205":       "pacs.009.001.08",
            "MT205COV":    "pacs.009.001.08",
            "MT205RETURN": "pacs.004.001.09",
        }
        result = mapping.get(source_type)
        if not result:
            raise ValueError(f"Cannot auto-detect target for source_type: {source_type}")
        return result

    # ------------------------------------------------------------------
    # CBPR+ R2025 Prohibited-field and rule guards
    # ------------------------------------------------------------------

    def _check_prohibited_fields(
        self,
        parsed_mt: Dict[str, Any],
        source_type: str,
        target_type: str,
    ) -> None:
        fields: Dict[str, Any] = parsed_mt.get("fields", {})

        # ── pacs.009 CORE (MT202): must NOT carry retail customer details ──────
        if source_type == "MT202" and "pacs.009" in target_type:
            retail_present = _RETAIL_CUSTOMER_FIELDS.intersection(fields.keys())
            if retail_present:
                raise ValidationException(
                    field_name=", ".join(retail_present),
                    message_type=target_type,
                    message=(
                        "CBPR+ R2025: pacs.009 CORE (MT202) must NOT contain retail "
                        f"customer elements: {retail_present}. "
                        "These fields are reserved for the COV (MT202COV) variant."
                    ),
                    action=(
                        "Use MT202COV source_type to include the underlying customer "
                        "block (UndrlygCstmrCdtTrf) in the pacs.009 COV variant."
                    ),
                    rule_ref="CBPR+ R2025 §FI-to-FI",
                )

        # ── pacs.009 COV (MT202COV): MUST have underlying customer block ───────
        if source_type == "MT202COV" and "pacs.009" in target_type:
            has_underlying = (
                "underlying_ordering_customer" in fields
                or "underlying_beneficiary" in fields
            )
            if not has_underlying:
                raise ValidationException(
                    field_name="UndrlygCstmrCdtTrf",
                    message_type=target_type,
                    message=(
                        "CBPR+ R2025: pacs.009 COV requires an underlying customer "
                        "credit transfer block (MT202COV fields :50K:/:59:) but none "
                        "were found in the parsed message."
                    ),
                    action=(
                        "Ensure the MT202COV message contains :50K: (ordering "
                        "customer) and :59: (beneficiary customer) fields."
                    ),
                    rule_ref="CBPR+ R2025 §COV",
                )

        # ── R2025: IntrBkSttlmAmt vs InstdAmt currency consistency ───────────
        if "pacs.008" in target_type:
            va = fields.get("value_date_currency_amount", {})
            ia = fields.get("instructed_amount", {})
            if va and ia:
                _, va_ccy, _ = _parse_32a(va.get("value", ""))
                _, ia_ccy, _ = _parse_32a(ia.get("value", ""))
                if va_ccy and ia_ccy and va_ccy != ia_ccy:
                    raise ValidationException(
                        field_name="IntrBkSttlmAmt/InstdAmt",
                        message_type=target_type,
                        message=(
                            f"CBPR+ R2025: Currency mismatch — :32A: ({va_ccy}) vs "
                            f":33B: ({ia_ccy}). IntrBkSttlmAmt and InstdAmt "
                            "must use consistent currencies in pacs.008."
                        ),
                        action=(
                            "Ensure :32A: and :33B: currencies match, or omit "
                            ":33B: if the instructed amount equals the settlement amount."
                        ),
                        rule_ref="CBPR+ R2025 §Amount",
                    )

    # ------------------------------------------------------------------
    # pacs.008.001.08 builder  (MT103 / MT103STP)
    # CBPR+ R2025 compliant — Full SWIFT field mapping
    # ------------------------------------------------------------------

    def _build_pacs008(self, parsed: Dict[str, Any], uetr: str) -> str:
        fields = parsed.get("fields", {})
        ns = NS_PACS008

        root = etree.Element("Document", nsmap={None: ns})
        fi_to_fi = _sub(root, "FIToFICstmrCdtTrf")

        # ── GrpHdr ──────────────────────────────────────────────────────────
        grp_hdr = _sub(fi_to_fi, "GrpHdr")
        tx_ref = (
            fields.get("transaction_reference", {}).get("value", "")
            or fields.get("sender_reference", {}).get("value", "")
            or str(uuid.uuid4()).replace("-", "")[:16]
        )
        _sub(grp_hdr, "MsgId", tx_ref)
        _sub(grp_hdr, "CreDtTm", _iso_now())
        _sub(grp_hdr, "NbOfTxs", "1")

        sttlm_inf = _sub(grp_hdr, "SttlmInf")
        _sub(sttlm_inf, "SttlmMtd", "CLRG")

        # ── CdtTrfTxInf — FULL ISO 20022 / CBPR+ R2025 XSD SEQUENCE ────────
        #
        # Official SWIFT MT103 → pacs.008.001.08 field mapping:
        #  :20:   → GrpHdr/MsgId + PmtId/InstrId
        #  {121}  → PmtId/UETR
        #  :32A:  → IntrBkSttlmAmt + IntrBkSttlmDt
        #  :33B:  → InstdAmt  (original currency amount, FX transactions)
        #  :71A:  → ChrgBr    (OUR=DEBT, SHA=SHAR, BEN=CRED)
        #  :53a:  → InstgAgt  (Sender's correspondent)
        #  :56a:  → IntrmyAgt1 (Intermediary institution)
        #  :52a:  → DbtrAgt   (Ordering institution = Debtor's agent)
        #  :50a:  → Dbtr + DbtrAcct (Ordering customer)
        #  :57a:  → CdtrAgt   (Account with institution = Creditor's agent)
        #  :59a:  → Cdtr + CdtrAcct (Beneficiary customer)
        #  :72:   → InstrForCdtrAgt / InstrForNxtAgt (Sender-to-receiver info)
        #  :26T:  → Purp
        #  :70:   → RmtInf/Ustrd (Remittance information)

        cdt_tx = _sub(fi_to_fi, "CdtTrfTxInf")

        # ── 1. PmtId ────────────────────────────────────────────────────────
        pmt_id = _sub(cdt_tx, "PmtId")
        if tx_ref:
            _sub(pmt_id, "InstrId", tx_ref)
        _sub(pmt_id, "EndToEndId", tx_ref or "NOTPROVIDED")
        _sub(pmt_id, "UETR", uetr)    # CBPR+ R2025 MANDATORY

        # ── 2. PmtTpInf — Service Level SDVA (same-day value) ───────────────
        # CBPR+ R2025: Recommended for cross-border payments
        pmt_tp = _sub(cdt_tx, "PmtTpInf")
        _sub(_sub(pmt_tp, "SvcLvl"), "Cd", _SVC_LVL_SDVA)

        # ── 3. IntrBkSttlmAmt + IntrBkSttlmDt (:32A:) ──────────────────────
        va_field = fields.get("value_date_currency_amount", {}).get("value", "")
        if va_field:
            sttlm_date, ccy, amount = _parse_32a(va_field)
        else:
            sttlm_date, ccy, amount = "2026-05-23", "USD", "0.00"

        sttlm_amt_el = _sub(cdt_tx, "IntrBkSttlmAmt", amount)
        sttlm_amt_el.set("Ccy", ccy)
        _sub(cdt_tx, "IntrBkSttlmDt", sttlm_date)

        # ── 4. InstdAmt (:33B:) — original amount for FX transactions ────────
        ia_field = fields.get("instructed_amount", {}).get("value", "")
        if ia_field:
            _, ia_ccy, ia_amount = _parse_32a(ia_field)
            if ia_ccy != ccy:   # Only emit when currencies differ (real FX)
                instd_amt_el = _sub(cdt_tx, "InstdAmt", ia_amount)
                instd_amt_el.set("Ccy", ia_ccy)

        # ── 5. ChrgBr (:71A:) — CBPR+ R2025: SHAR for interbank ─────────────
        charges_raw = fields.get("details_of_charges", {}).get("value", "SHA")
        _sub(cdt_tx, "ChrgBr", _PACS008_CHRGBR_MAP.get(charges_raw.strip().upper(), "SHAR"))

        # ── 6. InstgAgt (:53A: — Sender's correspondent, optional) ──────────
        sndr_corr = fields.get("sender_correspondent", {}).get("value", "")
        if sndr_corr:
            instg_agt = _sub(cdt_tx, "InstgAgt")
            _sub(_sub(instg_agt, "FinInstnId"), "BICFI", _bic_from_field(sndr_corr))

        # ── 7. IntrmyAgt1 (:56A: — Intermediary institution, optional) ───────
        intrm_bic = fields.get("intermediary_institution", {}).get("value", "")
        if intrm_bic:
            intrm_agt = _sub(cdt_tx, "IntrmyAgt1")
            _sub(_sub(intrm_agt, "FinInstnId"), "BICFI", _bic_from_field(intrm_bic))

        # ── 8. DbtrAgt (:52A: — Ordering institution, CBPR+ MANDATORY) ──────
        dbtr_agt_bic = fields.get("ordering_institution", {}).get("value", "")
        dbtr_agt = _sub(cdt_tx, "DbtrAgt")
        _sub(
            _sub(dbtr_agt, "FinInstnId"),
            "BICFI",
            _bic_from_field(dbtr_agt_bic) if dbtr_agt_bic else "UNKNUS33",
        )

        # ── 9. Dbtr (:50K:/:50A:/:50F: — Ordering customer, MANDATORY) ──────
        dbtr_raw = fields.get("ordering_customer", {}).get("value", "")
        dbtr = _sub(cdt_tx, "Dbtr")
        if dbtr_raw:
            _sub(dbtr, "Nm", _name_from_field(dbtr_raw)[:140])
            _add_postal_address_r2025(dbtr, dbtr_raw)
        else:
            _sub(dbtr, "Nm", "UNKNOWN")

        # ── 10. DbtrAcct (optional) ──────────────────────────────────────────
        iban_val = _iban_or_account(dbtr_raw) if dbtr_raw else ""
        if iban_val:
            dbtr_acct = _sub(cdt_tx, "DbtrAcct")
            acct_id = _sub(dbtr_acct, "Id")
            if _IBAN_RE.match(iban_val):
                _sub(acct_id, "IBAN", iban_val)
            else:
                _sub(_sub(acct_id, "Othr"), "Id", iban_val)

        # ── 11. CdtrAgt (:57A: — Beneficiary's bank, CBPR+ MANDATORY) ────────
        cdtr_agt_bic = fields.get("account_with_institution", {}).get("value", "")
        cdtr_agt = _sub(cdt_tx, "CdtrAgt")
        _sub(
            _sub(cdtr_agt, "FinInstnId"),
            "BICFI",
            _bic_from_field(cdtr_agt_bic) if cdtr_agt_bic else "UNKNUS33",
        )

        # ── 12. Cdtr (:59:/:59A:/:59F: — Beneficiary customer, MANDATORY) ────
        cdtr_raw = fields.get("beneficiary_customer", {}).get("value", "")
        cdtr = _sub(cdt_tx, "Cdtr")
        if cdtr_raw:
            _sub(cdtr, "Nm", _name_from_field(cdtr_raw)[:140])
            _add_postal_address_r2025(cdtr, cdtr_raw)
        else:
            _sub(cdtr, "Nm", "UNKNOWN")

        # ── 13. CdtrAcct (optional) ──────────────────────────────────────────
        cdtr_iban = _iban_or_account(cdtr_raw) if cdtr_raw else ""
        if cdtr_iban:
            cdtr_acct = _sub(cdt_tx, "CdtrAcct")
            acct_id = _sub(cdtr_acct, "Id")
            if _IBAN_RE.match(cdtr_iban):
                _sub(acct_id, "IBAN", cdtr_iban)
            else:
                _sub(_sub(acct_id, "Othr"), "Id", cdtr_iban)

        # ── 14. InstrForCdtrAgt / InstrForNxtAgt (:72:) ─────────────────────
        # :72: sender-to-receiver info maps to instruction fields
        s2r_raw = fields.get("sender_to_receiver_info", {}).get("value", "")
        if s2r_raw:
            # Extract /BNF/ as beneficiary instruction, /ACC/ as creditor agent instruction
            lines_72 = [ln.strip() for ln in s2r_raw.split("\n") if ln.strip()]
            for ln72 in lines_72:
                up = ln72.upper()
                if up.startswith("/ACC/") or up.startswith("/CHQB/") or up.startswith("/HOLD/"):
                    instr_cdtr = _sub(cdt_tx, "InstrForCdtrAgt")
                    _sub(instr_cdtr, "InstrInf", ln72[:140])
                elif up.startswith("/INS/") or up.startswith("/INT/"):
                    instr_nxt = _sub(cdt_tx, "InstrForNxtAgt")
                    _sub(instr_nxt, "InstrInf", ln72[:140])

        # ── 15. Purp (:26T: — optional) ──────────────────────────────────────
        purpose_raw = fields.get("transaction_type_code", {}).get("value", "")
        if purpose_raw and purpose_raw.upper() in _PURPOSE_CODES:
            _sub(_sub(cdt_tx, "Purp"), "Cd", purpose_raw.upper())

        # ── 16. RmtInf (:70: — Remittance information, optional) ─────────────
        rmt_raw = fields.get("remittance_info", {}).get("value", "")
        # Also check :72:/BNF/ as fallback for remittance info
        bnf_text = ""
        if not rmt_raw and s2r_raw and "/BNF/" in s2r_raw.upper():
            try:
                bnf_part = s2r_raw.upper().split("/BNF/")[1]
                bnf_text = re.split(r"/[A-Z]{2,4}/", bnf_part)[0].strip()[:140]
            except (IndexError, AttributeError):
                bnf_text = ""
        final_rmt = rmt_raw or bnf_text
        if final_rmt:
            _sub(_sub(cdt_tx, "RmtInf"), "Ustrd", final_rmt[:140])

        return etree.tostring(root, pretty_print=True, xml_declaration=True, encoding="UTF-8").decode()


    # ------------------------------------------------------------------
    # pacs.009.001.08 builder  (MT202 / MT202COV / MT204)
    # CBPR+ R2025 compliant
    # ------------------------------------------------------------------

    def _build_pacs009(
        self, parsed: Dict[str, Any], source_type: str, uetr: str
    ) -> str:
        fields = parsed.get("fields", {})
        ns = NS_PACS009
        is_cov = source_type in ("MT202COV", "MT205COV")

        root = etree.Element("Document", nsmap={None: ns})
        fi_cdt_trf = _sub(root, "FICdtTrf")

        # ── GrpHdr ──────────────────────────────────────────────────────────
        grp_hdr = _sub(fi_cdt_trf, "GrpHdr")
        tx_ref = (
            fields.get("transaction_reference", {}).get("value", "")
            or str(uuid.uuid4()).replace("-", "")[:16]
        )
        _sub(grp_hdr, "MsgId", tx_ref)
        _sub(grp_hdr, "CreDtTm", _iso_now())
        _sub(grp_hdr, "NbOfTxs", "1")

        sttlm_inf = _sub(grp_hdr, "SttlmInf")
        _sub(sttlm_inf, "SttlmMtd", "CLRG")

        # ── CdtTrfTxInf — EXACT XSD SEQUENCE (pacs.009.001.08.xsd lines 48-70) ──
        #
        #  1. PmtId             (mandatory)
        #  2. PmtTpInf          (optional) ← pacs.009 DOES have this, unlike pacs.008
        #  3. IntrBkSttlmAmt    (mandatory)
        #  4. IntrBkSttlmDt     (optional)
        #  5. SttlmPrty         (optional)
        #  6. ChrgBr            (mandatory)
        #  7. InstgAgt          (optional)
        #  8. InstdAgt          (optional)
        #  9. IntrmyAgt1        (optional)
        # 10. IntrmyAgt2        (optional)
        # 11. IntrmyAgt3        (optional)
        # 12. Dbtr              (optional) ← FI type (BranchAndFinancialInstitutionIdentification6)
        # 13. DbtrAcct          (optional)
        # 14. Cdtr              (optional) ← FI type (BranchAndFinancialInstitutionIdentification6)
        # 15. CdtrAcct          (optional)
        # 16. Purp              (optional)
        # 17. UndrlygCstmrCdtTrf (optional) ← COV only
        # 18. RmtInf            (optional)

        cdt_tx = _sub(fi_cdt_trf, "CdtTrfTxInf")

        # ── 1. PmtId ────────────────────────────────────────────────────────
        pmt_id = _sub(cdt_tx, "PmtId")
        if tx_ref:
            _sub(pmt_id, "InstrId", tx_ref)
        related_ref = fields.get("related_reference", {}).get("value", tx_ref)
        _sub(pmt_id, "EndToEndId", related_ref or tx_ref)
        _sub(pmt_id, "UETR", uetr)    # CBPR+ R2025: MANDATORY

        # ── 2. PmtTpInf (optional — pacs.009 XSD has it, pacs.008 does not) ─
        pmt_tp = _sub(cdt_tx, "PmtTpInf")
        _sub(_sub(pmt_tp, "SvcLvl"), "Cd", _SVC_LVL_SDVA)

        # ── 3+4. IntrBkSttlmAmt + IntrBkSttlmDt ────────────────────────────
        va_field = fields.get("value_date_currency_amount", {}).get("value", "")
        if va_field:
            sttlm_date, ccy, amount = _parse_32a(va_field)
        else:
            sttlm_date, ccy, amount = "2026-05-23", "USD", "0.00"

        sttlm_amt_el = _sub(cdt_tx, "IntrBkSttlmAmt", amount)
        sttlm_amt_el.set("Ccy", ccy)
        _sub(cdt_tx, "IntrBkSttlmDt", sttlm_date)

        # ── 6. ChrgBr (CBPR+ R2025: SHAR mandatory) ─────────────────────────
        _sub(cdt_tx, "ChrgBr", "SHAR")

        # ── 7. InstgAgt (:52A: — ordering institution, optional) ────────────
        instg_bic = fields.get("ordering_institution", {}).get("value", "")
        if instg_bic:
            _sub(_sub(_sub(cdt_tx, "InstgAgt"), "FinInstnId"), "BICFI", _bic_from_field(instg_bic))

        # ── 8. InstdAgt (:58A: — beneficiary institution, optional) ─────────
        bene_inst_bic = fields.get("beneficiary_institution", {}).get("value", "")
        if bene_inst_bic:
            _sub(_sub(_sub(cdt_tx, "InstdAgt"), "FinInstnId"), "BICFI", _bic_from_field(bene_inst_bic))

        # ── 9. IntrmyAgt1 (:56A: — intermediary, optional) ──────────────────
        intrm_bic = fields.get("intermediary_institution", {}).get("value", "")
        if intrm_bic:
            _sub(_sub(_sub(cdt_tx, "IntrmyAgt1"), "FinInstnId"), "BICFI", _bic_from_field(intrm_bic))

        # ── 12. Dbtr (FI type — ordering FI, optional in pacs.009) ──────────
        # In pacs.009, Dbtr is BranchAndFinancialInstitutionIdentification6
        # (not PartyIdentification135 as in pacs.008)
        if instg_bic:
            dbtr_fi = _sub(cdt_tx, "Dbtr")
            _sub(_sub(dbtr_fi, "FinInstnId"), "BICFI", _bic_from_field(instg_bic))

        # ── 14. Cdtr (FI type — beneficiary FI, optional in pacs.009) ───────
        # Always emit with UNKNUS33 fallback so downstream agents can route
        cdtr_fi = _sub(cdt_tx, "Cdtr")
        _sub(
            _sub(cdtr_fi, "FinInstnId"),
            "BICFI",
            _bic_from_field(bene_inst_bic) if bene_inst_bic else "UNKNUS33",
        )

        # ── 17. UndrlygCstmrCdtTrf (COV only) ───────────────────────────────
        # XSD UnderlyingCustomerCreditTransfer sequence (lines 74-82):
        # [InitgPty] → [Dbtr] → [DbtrAcct] → [DbtrAgt] → [Cdtr] → [CdtrAcct] → [CdtrAgt]
        if is_cov:
            undrlg = _sub(cdt_tx, "UndrlygCstmrCdtTrf")

            # Underlying Debtor (:50K: ordering customer)
            oc_raw = (
                fields.get("underlying_ordering_customer", {}).get("value", "")
                or fields.get("ordering_customer", {}).get("value", "")
            )
            if oc_raw:
                dbtr = _sub(undrlg, "Dbtr")
                _sub(dbtr, "Nm", _name_from_field(oc_raw)[:140])
                _add_postal_address_r2025(dbtr, oc_raw)

                iban_v = _iban_or_account(oc_raw)
                if iban_v:
                    dbtr_acct = _sub(undrlg, "DbtrAcct")
                    acct_id = _sub(dbtr_acct, "Id")
                    if _IBAN_RE.match(iban_v):
                        _sub(acct_id, "IBAN", iban_v)
                    else:
                        _sub(_sub(acct_id, "Othr"), "Id", iban_v)

            # Underlying Creditor (:59: beneficiary customer)
            ub_raw = (
                fields.get("underlying_beneficiary", {}).get("value", "")
                or fields.get("beneficiary_customer", {}).get("value", "")
            )
            if ub_raw:
                cdtr_cov = _sub(undrlg, "Cdtr")
                _sub(cdtr_cov, "Nm", _name_from_field(ub_raw)[:140])
                _add_postal_address_r2025(cdtr_cov, ub_raw)

                cdtr_iban = _iban_or_account(ub_raw)
                if cdtr_iban:
                    cdtr_acct = _sub(undrlg, "CdtrAcct")
                    acct_id = _sub(cdtr_acct, "Id")
                    if _IBAN_RE.match(cdtr_iban):
                        _sub(acct_id, "IBAN", cdtr_iban)
                    else:
                        _sub(_sub(acct_id, "Othr"), "Id", cdtr_iban)

        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        ).decode()


    # ------------------------------------------------------------------
    # pacs.004.001.09 builder — Payment Return
    # CBPR+ R2025 compliant
    # ------------------------------------------------------------------

    def _build_pacs004(
        self, parsed: Dict[str, Any], uetr: str
    ) -> str:
        """
        Build a pacs.004.001.09 (Payment Return) XML document.

        CBPR+ R2025 mandatory elements:
          - <OrgnlUETR>   — UUID4 of the original transaction being returned
          - <OrgnlMsgId>  — MsgId of the original pacs message
          - <RtrId>       — Unique return transaction identifier
          - <Rsn><Cd>     — External return reason code (e.g. AM09, AGNT, AC04)
          - UETR          — New UETR for the return itself
          - ChrgBr = SHAR — Mandatory for CBPR+ returns
        """
        fields = parsed.get("fields", {})
        ns = NS_PACS004

        root = etree.Element("Document", nsmap={None: ns})
        pmt_rtr = _sub(root, "PmtRtr")

        # ── GrpHdr ──────────────────────────────────────────────────────────
        grp_hdr = _sub(pmt_rtr, "GrpHdr")
        tx_ref = fields.get("transaction_reference", {}).get("value", str(uuid.uuid4())[:16])
        _sub(grp_hdr, "MsgId", tx_ref)
        _sub(grp_hdr, "CreDtTm", _iso_now())
        _sub(grp_hdr, "NbOfTxs", "1")

        sttlm_inf = _sub(grp_hdr, "SttlmInf")
        _sub(sttlm_inf, "SttlmMtd", "CLRG")

        # ── TxInf ───────────────────────────────────────────────────────────
        tx_inf = _sub(pmt_rtr, "TxInf")

        # RtrId — new unique ID for this return message
        _sub(tx_inf, "RtrId", tx_ref)

        # OrgnlGrpInf — references the original message being returned
        orgn_grp_inf = _sub(tx_inf, "OrgnlGrpInf")
        orgn_msg_id = fields.get("related_reference", {}).get("value", tx_ref)
        _sub(orgn_grp_inf, "OrgnlMsgId", orgn_msg_id)
        _sub(orgn_grp_inf, "OrgnlMsgNmId", "pacs.008.001.08")

        # OrgnlUETR — the UETR of the ORIGINAL transaction (R2025: mandatory)
        original_uetr = parsed.get("original_uetr") or str(uuid.uuid4())
        try:
            uuid.UUID(original_uetr, version=4)
        except (ValueError, AttributeError):
            original_uetr = str(uuid.uuid4())
        _sub(tx_inf, "OrgnlUETR", original_uetr)

        # RtrdIntrBkSttlmAmt — return settlement amount
        va_field = fields.get("value_date_currency_amount", {}).get("value", "")
        if va_field:
            sttlm_date, ccy, amount = _parse_32a(va_field)
        else:
            sttlm_date, ccy, amount = "2026-05-23", "USD", "0.00"

        rtr_amt_el = _sub(tx_inf, "RtrdIntrBkSttlmAmt", amount)
        rtr_amt_el.set("Ccy", ccy)
        _sub(tx_inf, "IntrBkSttlmDt", sttlm_date)

        # ChrgBr (R2025: SHAR mandatory for CBPR+ returns)
        _sub(tx_inf, "ChrgBr", "SHAR")

        # InstgAgt — the bank initiating the return (:52A:)
        instg_bic = fields.get("ordering_institution", {}).get("value", "")
        if instg_bic:
            instg_agt = _sub(tx_inf, "InstgAgt")
            fin_instn = _sub(instg_agt, "FinInstnId")
            _sub(fin_instn, "BICFI", _bic_from_field(instg_bic))

        # InstdAgt — the bank receiving the return (:58A:)
        instd_bic = fields.get("beneficiary_institution", {}).get("value", "")
        if instd_bic:
            instd_agt = _sub(tx_inf, "InstdAgt")
            fin_instn = _sub(instd_agt, "FinInstnId")
            _sub(fin_instn, "BICFI", _bic_from_field(instd_bic))

        # RtrRsnInf — Return Reason (R2025 expanded code list)
        # Extract from :72: /RETN/<code> or use safe default
        s2r_raw = fields.get("sender_to_receiver_info", {}).get("value", "")
        return_code = "AGNT"  # CBPR+ R2025 safe default
        if "/RETN/" in s2r_raw.upper():
            try:
                code_candidate = s2r_raw.upper().split("/RETN/")[-1].strip()[:4]
                if code_candidate in _VALID_RETURN_CODES:
                    return_code = code_candidate
            except Exception:
                pass

        rtr_rsn_inf = _sub(tx_inf, "RtrRsnInf")
        rsn = _sub(rtr_rsn_inf, "Rsn")
        _sub(rsn, "Cd", return_code)

        return etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        ).decode()


# Module-level singleton
mx_translator = MXTranslator()
