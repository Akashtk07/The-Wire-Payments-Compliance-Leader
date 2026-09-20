"""
MX → MX Converter: pacs.008 → pacs.009 COV (Direct to Cover Wrapping)

Converts a pacs.008.001.08 (FI-to-FI Customer Credit Transfer) into a
pacs.009.001.08 COV (Cover Payment) by embedding the customer data into
the <UndrlygCstmrCdtTrf> block.

Use case:
    A payment originator has a pacs.008 and needs to generate the
    corresponding cover payment leg (pacs.009COV) to send through a
    correspondent banking chain.

UETR rules (scheme-aware):
    CBPR+: Cover leg gets a NEW UUID4 UETR. The original pacs.008 UETR
           is preserved in context (can be referenced in UndrlygCstmrCdtTrf).
    LYNX:  Cover leg CARRIES THE SAME UETR as the underlying pacs.008.
           This is a key LYNX-specific rule for reconciliation.

Settlement method:
    CBPR+: CLRG (Clearing) — standard interbank settlement
    LYNX:  CLRG ONLY — LYNX does not permit any other SttlmMtd
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

import structlog
from lxml import etree

log = structlog.get_logger(__name__)

# Namespace declarations
NS_PACS008 = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"
NS_PACS009 = "urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08"


def _sub(parent: etree._Element, tag: str, text: str | None = None) -> etree._Element:
    el = etree.SubElement(parent, tag)
    if text is not None:
        el.text = text
    return el


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S") + "+00:00"


def _text(root: etree._Element, path: str, ns: dict) -> str:
    nodes = root.xpath(path, namespaces=ns)
    return (nodes[0].text or "").strip() if nodes else ""


def _attr(root: etree._Element, path: str, attr: str, ns: dict) -> str:
    nodes = root.xpath(path, namespaces=ns)
    return (nodes[0].get(attr) or "").strip() if nodes else ""


class MXtOMXConverter:
    """
    Converts pacs.008.001.08 → pacs.009.001.08 COV.

    Scheme-aware:
        CBPR+: new UETR for cover leg
        LYNX:  same UETR as underlying pacs.008 (propagated)
    """

    async def convert_pacs008_to_pacs009cov(
        self,
        pacs008_xml: str,
        scheme: str = "CBPR+",
    ) -> Tuple[str, str, str]:
        """
        Convert a pacs.008 XML string to a pacs.009 COV XML string.

        Args:
            pacs008_xml: Raw pacs.008.001.08 XML string.
            scheme:      'CBPR+' or 'LYNX'.

        Returns:
            Tuple of (pacs009cov_xml, new_uetr, original_uetr).

        Raises:
            ValueError if pacs008_xml is malformed or missing required fields.
        """
        scheme = scheme.upper().strip()
        if scheme not in ("CBPR+", "LYNX"):
            raise ValueError("scheme must be 'CBPR+' or 'LYNX'")

        try:
            src_root = etree.fromstring(
                pacs008_xml.encode() if isinstance(pacs008_xml, str) else pacs008_xml
            )
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Invalid pacs.008 XML: {exc}") from exc

        ns008 = {"p": NS_PACS008}

        # ── Extract fields from pacs.008 ──────────────────────────────

        original_uetr = _text(src_root, ".//p:PmtId/p:UETR", ns008)
        msg_id = _text(src_root, ".//p:GrpHdr/p:MsgId", ns008)
        instr_id = _text(src_root, ".//p:PmtId/p:InstrId", ns008)
        end_to_end = _text(src_root, ".//p:PmtId/p:EndToEndId", ns008)

        sttlm_amt = _text(src_root, ".//p:IntrBkSttlmAmt", ns008)
        sttlm_ccy = _attr(src_root, ".//p:IntrBkSttlmAmt", "Ccy", ns008)
        sttlm_dt = _text(src_root, ".//p:IntrBkSttlmDt", ns008)

        dbtr_agt_bic = _text(src_root, ".//p:DbtrAgt/p:FinInstnId/p:BICFI", ns008)
        cdtr_agt_bic = _text(src_root, ".//p:CdtrAgt/p:FinInstnId/p:BICFI", ns008)
        intrmy_bic = _text(src_root, ".//p:IntrmyAgt1/p:FinInstnId/p:BICFI", ns008)

        # Debtor (customer) fields
        dbtr_nm = _text(src_root, ".//p:Dbtr/p:Nm", ns008)
        dbtr_twn = _text(src_root, ".//p:Dbtr/p:PstlAdr/p:TwnNm", ns008)
        dbtr_ctry = _text(src_root, ".//p:Dbtr/p:PstlAdr/p:Ctry", ns008)
        dbtr_adr = src_root.xpath(".//p:Dbtr/p:PstlAdr/p:AdrLine/text()", namespaces=ns008)
        dbtr_iban = _text(src_root, ".//p:DbtrAcct/p:Id/p:IBAN", ns008)
        dbtr_othr = _text(src_root, ".//p:DbtrAcct/p:Id/p:Othr/p:Id", ns008)

        # Creditor (customer) fields
        cdtr_nm = _text(src_root, ".//p:Cdtr/p:Nm", ns008)
        cdtr_twn = _text(src_root, ".//p:Cdtr/p:PstlAdr/p:TwnNm", ns008)
        cdtr_ctry = _text(src_root, ".//p:Cdtr/p:PstlAdr/p:Ctry", ns008)
        cdtr_adr = src_root.xpath(".//p:Cdtr/p:PstlAdr/p:AdrLine/text()", namespaces=ns008)
        cdtr_iban = _text(src_root, ".//p:CdtrAcct/p:Id/p:IBAN", ns008)
        cdtr_othr = _text(src_root, ".//p:CdtrAcct/p:Id/p:Othr/p:Id", ns008)

        # ── Determine UETR for cover leg ──────────────────────────────
        # CBPR+: NEW UUID4 for the cover leg
        # LYNX:  SAME UETR as pacs.008 (propagated for reconciliation)
        if scheme == "LYNX":
            cover_uetr = original_uetr or str(uuid.uuid4())
        else:
            cover_uetr = str(uuid.uuid4())

        # Generate cover message ID
        cover_msg_id = f"COV-{msg_id[:14]}" if msg_id else f"COV-{str(uuid.uuid4())[:14]}"

        # ── Build pacs.009 COV XML ─────────────────────────────────────

        root = etree.Element("Document", nsmap={None: NS_PACS009})
        fi_cdt_trf = _sub(root, "FICdtTrf")

        # GrpHdr
        grp_hdr = _sub(fi_cdt_trf, "GrpHdr")
        _sub(grp_hdr, "MsgId", cover_msg_id)
        _sub(grp_hdr, "CreDtTm", _iso_now())
        _sub(grp_hdr, "NbOfTxs", "1")
        sttlm_inf = _sub(grp_hdr, "SttlmInf")
        _sub(sttlm_inf, "SttlmMtd", "CLRG")  # CLRG mandatory in both CBPR+ and LYNX

        # CdtTrfTxInf
        cdt_tx = _sub(fi_cdt_trf, "CdtTrfTxInf")

        # PmtId (UETR mandatory per R2025)
        pmt_id = _sub(cdt_tx, "PmtId")
        _sub(pmt_id, "InstrId", cover_msg_id)
        _sub(pmt_id, "EndToEndId", end_to_end or instr_id or cover_msg_id)
        _sub(pmt_id, "UETR", cover_uetr)

        # PmtTpInf — SDVA service level
        pmt_tp = _sub(cdt_tx, "PmtTpInf")
        svc_lvl = _sub(pmt_tp, "SvcLvl")
        _sub(svc_lvl, "Cd", "SDVA")

        # Settlement amount (copied from pacs.008)
        sttlm_amt_el = _sub(cdt_tx, "IntrBkSttlmAmt", sttlm_amt or "0.00")
        sttlm_amt_el.set("Ccy", sttlm_ccy or "CAD")
        if sttlm_dt:
            _sub(cdt_tx, "IntrBkSttlmDt", sttlm_dt)

        # ChrgBr = SHAR (CBPR+ R2025 mandatory for interbank)
        _sub(cdt_tx, "ChrgBr", "SHAR")

        # InstgAgt (Debtor's Agent → initiating the cover)
        if dbtr_agt_bic:
            instg_agt = _sub(cdt_tx, "InstgAgt")
            fi = _sub(instg_agt, "FinInstnId")
            _sub(fi, "BICFI", dbtr_agt_bic)

        # InstdAgt (Creditor's Agent → receiving the cover)
        if cdtr_agt_bic:
            instd_agt = _sub(cdt_tx, "InstdAgt")
            fi = _sub(instd_agt, "FinInstnId")
            _sub(fi, "BICFI", cdtr_agt_bic)

        # IntrmyAgt1 (if present in original pacs.008)
        if intrmy_bic:
            intrmy_agt = _sub(cdt_tx, "IntrmyAgt1")
            fi = _sub(intrmy_agt, "FinInstnId")
            _sub(fi, "BICFI", intrmy_bic)

        # Cdtr (Creditor Agent as financial institution — CORE element)
        if cdtr_agt_bic:
            cdtr_el = _sub(cdt_tx, "Cdtr")
            fi = _sub(cdtr_el, "FinInstnId")
            _sub(fi, "BICFI", cdtr_agt_bic)

        # ── UndrlygCstmrCdtTrf — mandatory in COV ────────────────────
        undrlg = _sub(cdt_tx, "UndrlygCstmrCdtTrf")

        # Underlying Debtor
        if dbtr_nm or dbtr_iban or dbtr_othr:
            dbtr_el = _sub(undrlg, "Dbtr")
            if dbtr_nm:
                _sub(dbtr_el, "Nm", dbtr_nm[:140])
            # PostalAddress (R2025 hybrid)
            pstl_adr = _sub(dbtr_el, "PstlAdr")
            _sub(pstl_adr, "TwnNm", dbtr_twn or "UNKNOWN")
            _sub(pstl_adr, "Ctry", dbtr_ctry or "XX")
            for adr_line in dbtr_adr[:2]:
                _sub(pstl_adr, "AdrLine", adr_line[:70])

            # DbtrAcct
            dbtr_acct_el = _sub(undrlg, "DbtrAcct")
            acct_id = _sub(dbtr_acct_el, "Id")
            acct_val = dbtr_iban or dbtr_othr
            if acct_val:
                if dbtr_iban:
                    _sub(acct_id, "IBAN", dbtr_iban)
                else:
                    othr = _sub(acct_id, "Othr")
                    _sub(othr, "Id", dbtr_othr)

        # Underlying Creditor
        if cdtr_nm or cdtr_iban or cdtr_othr:
            cdtr_cust = _sub(undrlg, "Cdtr")
            if cdtr_nm:
                _sub(cdtr_cust, "Nm", cdtr_nm[:140])
            pstl_adr = _sub(cdtr_cust, "PstlAdr")
            _sub(pstl_adr, "TwnNm", cdtr_twn or "UNKNOWN")
            _sub(pstl_adr, "Ctry", cdtr_ctry or "XX")
            for adr_line in cdtr_adr[:2]:
                _sub(pstl_adr, "AdrLine", adr_line[:70])

            cdtr_acct_el = _sub(undrlg, "CdtrAcct")
            acct_id = _sub(cdtr_acct_el, "Id")
            if cdtr_iban:
                _sub(acct_id, "IBAN", cdtr_iban)
            elif cdtr_othr:
                othr = _sub(acct_id, "Othr")
                _sub(othr, "Id", cdtr_othr)

        xml_str = etree.tostring(
            root, pretty_print=True, xml_declaration=True, encoding="UTF-8"
        ).decode()

        log.info(
            "pacs008_to_pacs009cov_complete",
            scheme=scheme,
            original_uetr=original_uetr,
            cover_uetr=cover_uetr,
            same_uetr=(cover_uetr == original_uetr),
        )

        return xml_str, cover_uetr, original_uetr


# Module-level singleton
mx_to_mx_converter = MXtOMXConverter()
