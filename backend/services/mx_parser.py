"""
ISO 20022 MX → Structured Dict Parser (Reverse of mt_parser.py)

Parses ISO 20022 XML payloads (pacs.008, pacs.009, pacs.004) into a
normalised Python dict that can be consumed by mt_builder.py to produce
raw SWIFT MT strings.

Scheme-aware: caller passes scheme="CBPR+" or scheme="LYNX" so that
UETR handling rules and Business Service header detection can differ.

Supported source types:
    pacs.008.001.08  — FI-to-FI Customer Credit Transfer
    pacs.009.001.08  — FI-to-FI Credit Transfer (CORE or COV)
    pacs.004.001.09  — Payment Return

COV auto-detection: presence of <UndrlygCstmrCdtTrf> in pacs.009 → COV
STP auto-detection: presence of <SvcLvl><Cd>NURG</Cd> or <LclInstrm>
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Optional, Tuple

import structlog
from lxml import etree

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Namespace maps
# ---------------------------------------------------------------------------

_NS = {
    "pacs008": "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08",
    "pacs009": "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08",
    "pacs004": "urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09",
}

# Reverse map: namespace URI → short key
_NS_REV = {v: k for k, v in _NS.items()}

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

_SUPPORTED_SOURCES = {
    "pacs.008.001.08",
    "pacs.009.001.08",
    "pacs.004.001.09",
}


# ---------------------------------------------------------------------------
# Helper: safe XPath text extraction
# ---------------------------------------------------------------------------


def _text(root: etree._Element, path: str, ns: dict) -> str:
    """Return stripped text of first XPath match, or empty string."""
    nodes = root.xpath(path, namespaces=ns)
    if nodes:
        return (nodes[0].text or "").strip()
    return ""


def _attr(root: etree._Element, path: str, attr: str, ns: dict) -> str:
    """Return attribute value of first XPath match, or empty string."""
    nodes = root.xpath(path, namespaces=ns)
    if nodes:
        return (nodes[0].get(attr) or "").strip()
    return ""


def _detect_ns_alias(root: etree._Element) -> Optional[str]:
    """Detect which pacs namespace this document uses."""
    ns_uri = root.nsmap.get(None) or ""
    return _NS_REV.get(ns_uri)


def _build_ns(alias: str) -> Dict[str, str]:
    return {alias: _NS[alias]}


# ---------------------------------------------------------------------------
# Amount helpers
# ---------------------------------------------------------------------------


def _fmt_amount(amount_str: str) -> str:
    """Convert decimal dot amount to SWIFT comma-format: '10000.00' → '10000,00'."""
    try:
        val = float(amount_str)
        # Use comma decimal separator for SWIFT MT
        return f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "")
    except (ValueError, TypeError):
        return "0,00"


def _parse_iso_date_to_yymmdd(iso_date: str) -> str:
    """Convert 'YYYY-MM-DD' → 'YYMMDD' for :32A: field."""
    try:
        parts = iso_date[:10].split("-")
        if len(parts) == 3:
            return parts[0][2:] + parts[1] + parts[2]
    except Exception:
        pass
    return "000101"


# ---------------------------------------------------------------------------
# Public parser class
# ---------------------------------------------------------------------------


class MXParser:
    """
    Parses ISO 20022 pacs.008 / pacs.009 / pacs.004 XML into a structured
    dict suitable for mt_builder.MTBuilder to convert to raw SWIFT MT strings.
    """

    def parse(
        self,
        xml_str: str,
        source_type: str,
        scheme: str = "CBPR+",
    ) -> Dict[str, Any]:
        """
        Parse ISO 20022 XML into a normalised dict.

        Args:
            xml_str:     Raw ISO 20022 XML string.
            source_type: One of 'pacs.008.001.08', 'pacs.009.001.08', 'pacs.004.001.09'.
            scheme:      'CBPR+' or 'LYNX'.

        Returns:
            dict with keys: source_type, variant, scheme, fields, uetr, ...

        Raises:
            ValueError: On unrecognised source_type or malformed XML.
        """
        source_type = source_type.lower().strip()
        if source_type not in _SUPPORTED_SOURCES:
            raise ValueError(
                f"Unsupported source_type '{source_type}'. "
                f"Must be one of: {sorted(_SUPPORTED_SOURCES)}"
            )
        scheme = scheme.upper().strip()
        if scheme not in ("CBPR+", "LYNX"):
            raise ValueError("scheme must be 'CBPR+' or 'LYNX'")

        try:
            root = etree.fromstring(xml_str.encode() if isinstance(xml_str, str) else xml_str)
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"XML parse error: {exc}") from exc

        if source_type == "pacs.008.001.08":
            return self._parse_pacs008(root, scheme)
        elif source_type == "pacs.009.001.08":
            return self._parse_pacs009(root, scheme)
        elif source_type == "pacs.004.001.09":
            return self._parse_pacs004(root, scheme)
        else:
            raise ValueError(f"Unhandled source_type: {source_type}")

    # ------------------------------------------------------------------
    # pacs.008 parser
    # ------------------------------------------------------------------

    def _parse_pacs008(self, root: etree._Element, scheme: str) -> Dict[str, Any]:
        ns_alias = "pacs008"
        ns = _build_ns(ns_alias)
        p = f"{ns_alias}:"

        # Detect STP: presence of SvcLvl/Cd=NURG or LclInstrm
        svc_lvl = _text(root, f".//{p}SvcLvl/{p}Cd", ns)
        lcl_instr = _text(root, f".//{p}LclInstrm/{p}Cd", ns)
        is_stp = svc_lvl.upper() in ("NURG", "SDVA") or bool(lcl_instr)

        # Core fields
        msg_id = _text(root, f".//{p}GrpHdr/{p}MsgId", ns)
        cre_dt_tm = _text(root, f".//{p}GrpHdr/{p}CreDtTm", ns)

        # Payment identifiers
        instr_id = _text(root, f".//{p}PmtId/{p}InstrId", ns)
        end_to_end = _text(root, f".//{p}PmtId/{p}EndToEndId", ns)
        uetr = _text(root, f".//{p}PmtId/{p}UETR", ns)

        # Amount
        sttlm_amt = _text(root, f".//{p}IntrBkSttlmAmt", ns)
        sttlm_ccy = _attr(root, f".//{p}IntrBkSttlmAmt", "Ccy", ns)
        sttlm_dt = _text(root, f".//{p}IntrBkSttlmDt", ns)
        instd_amt = _text(root, f".//{p}InstdAmt", ns)
        instd_ccy = _attr(root, f".//{p}InstdAmt", "Ccy", ns)

        # Charge bearer
        chrg_br = _text(root, f".//{p}ChrgBr", ns)

        # Agents
        dbtr_agt_bic = _text(root, f".//{p}DbtrAgt/{p}FinInstnId/{p}BICFI", ns)
        cdtr_agt_bic = _text(root, f".//{p}CdtrAgt/{p}FinInstnId/{p}BICFI", ns)
        intrmy_bic = _text(root, f".//{p}IntrmyAgt1/{p}FinInstnId/{p}BICFI", ns)
        sndr_corr_bic = _text(root, f".//{p}InstgAgt/{p}FinInstnId/{p}BICFI", ns)

        # Debtor
        dbtr_nm = _text(root, f".//{p}Dbtr/{p}Nm", ns)
        dbtr_iban = _text(root, f".//{p}DbtrAcct/{p}Id/{p}IBAN", ns)
        dbtr_othr = _text(root, f".//{p}DbtrAcct/{p}Id/{p}Othr/{p}Id", ns)
        dbtr_town = _text(root, f".//{p}Dbtr/{p}PstlAdr/{p}TwnNm", ns)
        dbtr_ctry = _text(root, f".//{p}Dbtr/{p}PstlAdr/{p}Ctry", ns)
        dbtr_adr_lines = root.xpath(f".//{p}Dbtr/{p}PstlAdr/{p}AdrLine/text()", namespaces=ns)

        # Creditor
        cdtr_nm = _text(root, f".//{p}Cdtr/{p}Nm", ns)
        cdtr_iban = _text(root, f".//{p}CdtrAcct/{p}Id/{p}IBAN", ns)
        cdtr_othr = _text(root, f".//{p}CdtrAcct/{p}Id/{p}Othr/{p}Id", ns)
        cdtr_town = _text(root, f".//{p}Cdtr/{p}PstlAdr/{p}TwnNm", ns)
        cdtr_ctry = _text(root, f".//{p}Cdtr/{p}PstlAdr/{p}Ctry", ns)
        cdtr_adr_lines = root.xpath(f".//{p}Cdtr/{p}PstlAdr/{p}AdrLine/text()", namespaces=ns)

        # Remittance info
        rmt_info = _text(root, f".//{p}RmtInf/{p}Ustrd", ns)
        purpose = _text(root, f".//{p}Purp/{p}Cd", ns)

        # Build 32A value: YYMMDD + CCY + AMOUNT
        yymmdd = _parse_iso_date_to_yymmdd(sttlm_dt)
        amount_32a = f"{yymmdd}{sttlm_ccy}{_fmt_amount(sttlm_amt)}"

        # Build ordered customer string for :50K:
        dbtr_acct = dbtr_iban or dbtr_othr
        dbtr_addr_parts = [ln for ln in [
            " ".join(dbtr_adr_lines),
            f"{dbtr_town} {dbtr_ctry}".strip(),
        ] if ln.strip()]
        dbtr_field = (
            (f"/{dbtr_acct}\n" if dbtr_acct else "") +
            (f"{dbtr_nm}\n" if dbtr_nm else "") +
            "\n".join(dbtr_addr_parts)
        ).strip()

        # Build beneficiary string for :59:
        cdtr_acct = cdtr_iban or cdtr_othr
        cdtr_addr_parts = [ln for ln in [
            " ".join(cdtr_adr_lines),
            f"{cdtr_town} {cdtr_ctry}".strip(),
        ] if ln.strip()]
        cdtr_field = (
            (f"/{cdtr_acct}\n" if cdtr_acct else "") +
            (f"{cdtr_nm}\n" if cdtr_nm else "") +
            "\n".join(cdtr_addr_parts)
        ).strip()

        return {
            "source_type": "pacs.008.001.08",
            "variant": "STP" if is_stp else "STANDARD",
            "scheme": scheme,
            "msg_id": msg_id,
            "cre_dt_tm": cre_dt_tm,
            "uetr": uetr,
            "fields": {
                "transaction_reference": instr_id or msg_id,
                "bank_operation_code": "CRED",
                "value_date_currency_amount": amount_32a,
                "instructed_amount": (
                    f"{yymmdd}{instd_ccy}{_fmt_amount(instd_amt)}" if instd_amt else ""
                ),
                "ordering_customer": dbtr_field,
                "ordering_institution": dbtr_agt_bic,
                "sender_correspondent": sndr_corr_bic,
                "intermediary_institution": intrmy_bic,
                "account_with_institution": cdtr_agt_bic,
                "beneficiary_customer": cdtr_field,
                "details_of_charges": _map_chrgbr_to_mt(chrg_br),
                "remittance_info": rmt_info,
                "transaction_type_code": purpose,
            },
        }

    # ------------------------------------------------------------------
    # pacs.009 parser
    # ------------------------------------------------------------------

    def _parse_pacs009(self, root: etree._Element, scheme: str) -> Dict[str, Any]:
        ns_alias = "pacs009"
        ns = _build_ns(ns_alias)
        p = f"{ns_alias}:"

        # Detect COV by presence of UndrlygCstmrCdtTrf
        undrlg_nodes = root.xpath(f".//{p}UndrlygCstmrCdtTrf", namespaces=ns)
        is_cov = bool(undrlg_nodes)

        msg_id = _text(root, f".//{p}GrpHdr/{p}MsgId", ns)
        cre_dt_tm = _text(root, f".//{p}GrpHdr/{p}CreDtTm", ns)

        instr_id = _text(root, f".//{p}PmtId/{p}InstrId", ns)
        end_to_end = _text(root, f".//{p}PmtId/{p}EndToEndId", ns)
        uetr = _text(root, f".//{p}PmtId/{p}UETR", ns)

        sttlm_amt = _text(root, f".//{p}IntrBkSttlmAmt", ns)
        sttlm_ccy = _attr(root, f".//{p}IntrBkSttlmAmt", "Ccy", ns)
        sttlm_dt = _text(root, f".//{p}IntrBkSttlmDt", ns)

        yymmdd = _parse_iso_date_to_yymmdd(sttlm_dt)
        amount_32a = f"{yymmdd}{sttlm_ccy}{_fmt_amount(sttlm_amt)}"

        instg_bic = _text(root, f".//{p}InstgAgt/{p}FinInstnId/{p}BICFI", ns)
        instd_bic = _text(root, f".//{p}InstdAgt/{p}FinInstnId/{p}BICFI", ns)
        intrmy_bic = _text(root, f".//{p}IntrmyAgt1/{p}FinInstnId/{p}BICFI", ns)
        awi_bic = _text(root, f".//{p}CdtrAgt/{p}FinInstnId/{p}BICFI", ns)
        bene_inst_bic = _text(root, f".//{p}InstdAgt/{p}FinInstnId/{p}BICFI", ns) or \
                        _text(root, f".//{p}Cdtr/{p}FinInstnId/{p}BICFI", ns)

        fields: Dict[str, Any] = {
            "transaction_reference": instr_id or msg_id,
            "related_reference": end_to_end or instr_id or msg_id,
            "value_date_currency_amount": amount_32a,
            "ordering_institution": instg_bic,
            "sender_correspondent": "",
            "receiver_correspondent": "",
            "intermediary_institution": intrmy_bic,
            "account_with_institution": awi_bic,
            "beneficiary_institution": bene_inst_bic or instd_bic,
        }

        # COV: extract underlying customer data
        if is_cov:
            oc_nm = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}Dbtr/{p}Nm", ns)
            oc_iban = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}DbtrAcct/{p}Id/{p}IBAN", ns)
            oc_othr = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}DbtrAcct/{p}Id/{p}Othr/{p}Id", ns)
            oc_town = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}Dbtr/{p}PstlAdr/{p}TwnNm", ns)
            oc_ctry = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}Dbtr/{p}PstlAdr/{p}Ctry", ns)

            ub_nm = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}Cdtr/{p}Nm", ns)
            ub_iban = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}CdtrAcct/{p}Id/{p}IBAN", ns)
            ub_othr = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}CdtrAcct/{p}Id/{p}Othr/{p}Id", ns)
            ub_town = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}Cdtr/{p}PstlAdr/{p}TwnNm", ns)
            ub_ctry = _text(root, f".//{p}UndrlygCstmrCdtTrf/{p}Cdtr/{p}PstlAdr/{p}Ctry", ns)

            oc_acct = oc_iban or oc_othr
            ub_acct = ub_iban or ub_othr

            fields["underlying_ordering_customer"] = (
                (f"/{oc_acct}\n" if oc_acct else "") +
                (f"{oc_nm}\n" if oc_nm else "") +
                f"{oc_town} {oc_ctry}".strip()
            ).strip()

            fields["underlying_beneficiary"] = (
                (f"/{ub_acct}\n" if ub_acct else "") +
                (f"{ub_nm}\n" if ub_nm else "") +
                f"{ub_town} {ub_ctry}".strip()
            ).strip()

        return {
            "source_type": "pacs.009.001.08",
            "variant": "COV" if is_cov else "CORE",
            "scheme": scheme,
            "msg_id": msg_id,
            "cre_dt_tm": cre_dt_tm,
            "uetr": uetr,
            "fields": fields,
        }

    # ------------------------------------------------------------------
    # pacs.004 parser
    # ------------------------------------------------------------------

    def _parse_pacs004(self, root: etree._Element, scheme: str) -> Dict[str, Any]:
        ns_alias = "pacs004"
        ns = _build_ns(ns_alias)
        p = f"{ns_alias}:"

        msg_id = _text(root, f".//{p}GrpHdr/{p}MsgId", ns)
        rtr_id = _text(root, f".//{p}TxInf/{p}RtrId", ns)

        orgn_msg_id = _text(root, f".//{p}OrgnlGrpInf/{p}OrgnlMsgId", ns)
        orgn_msg_nm_id = _text(root, f".//{p}OrgnlGrpInf/{p}OrgnlMsgNmId", ns)
        orgn_uetr = _text(root, f".//{p}TxInf/{p}OrgnlUETR", ns)
        uetr = _text(root, f".//{p}PmtId/{p}UETR", ns) or str(uuid.uuid4())

        rtr_amt = _text(root, f".//{p}RtrdIntrBkSttlmAmt", ns)
        rtr_ccy = _attr(root, f".//{p}RtrdIntrBkSttlmAmt", "Ccy", ns)
        sttlm_dt = _text(root, f".//{p}IntrBkSttlmDt", ns)

        yymmdd = _parse_iso_date_to_yymmdd(sttlm_dt)
        amount_32a = f"{yymmdd}{rtr_ccy}{_fmt_amount(rtr_amt)}"

        instg_bic = _text(root, f".//{p}InstgAgt/{p}FinInstnId/{p}BICFI", ns)
        instd_bic = _text(root, f".//{p}InstdAgt/{p}FinInstnId/{p}BICFI", ns)

        return_code = _text(root, f".//{p}RtrRsnInf/{p}Rsn/{p}Cd", ns) or "AGNT"
        return_narr = _text(root, f".//{p}RtrRsnInf/{p}AddtlInf", ns)

        # Detect original message type to determine target MT
        # pacs.008 → MT103RETURN; pacs.009 → MT202RETURN (CBPR+) or MT205RETURN (LYNX)
        orgn_is_pacs009 = "pacs.009" in orgn_msg_nm_id.lower() if orgn_msg_nm_id else False

        return {
            "source_type": "pacs.004.001.09",
            "variant": "PACS009_RETURN" if orgn_is_pacs009 else "PACS008_RETURN",
            "scheme": scheme,
            "msg_id": msg_id,
            "uetr": uetr,
            "original_uetr": orgn_uetr,
            "fields": {
                "transaction_reference": rtr_id or msg_id,
                "related_reference": orgn_msg_id,
                "value_date_currency_amount": amount_32a,
                "ordering_institution": instg_bic,
                "beneficiary_institution": instd_bic,
                "sender_to_receiver_info": f"/RETN/{return_code}" + (
                    f"\n/NARR/{return_narr}" if return_narr else ""
                ),
            },
        }


# ---------------------------------------------------------------------------
# ChrgBr → MT :71A: mapping (reverse of CBPR+ map)
# ---------------------------------------------------------------------------

def _map_chrgbr_to_mt(chrg_br: str) -> str:
    """Map ISO 20022 ChrgBr code to SWIFT MT :71A: value."""
    mapping = {
        "SHAR": "SHA",
        "DEBT": "OUR",
        "CRED": "BEN",
    }
    return mapping.get((chrg_br or "SHAR").upper(), "SHA")


# Module-level singleton
mx_parser = MXParser()
