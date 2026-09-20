"""
MX → MT Reverse Translation & MX → MX Cover Conversion Router.

Endpoints:
  POST /api/v1/mx-translate        — ISO 20022 XML → SWIFT MT string
  POST /api/v1/mx-translate/cover  — pacs.008 → pacs.009COV cover wrapping
  GET  /api/v1/mx-translate/sample/{source_type}/{scheme}  — Sample ISO 20022 XML

Scheme-aware:
  CBPR+: pacs.009 CORE → MT202, pacs.009 COV → MT202COV, pacs.004 → MT202RETURN
  LYNX:  pacs.009 CORE → MT205, pacs.009 COV → MT205COV, pacs.004 → MT205RETURN
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import structlog
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse

from models.schemas import (
    MXCoverRequest,
    MXCoverResponse,
    MXTranslateRequest,
    MXTranslateResponse,
)
from services.audit_logger import audit_logger
from services.mx_parser import mx_parser
from services.mx_to_mx_converter import mx_to_mx_converter
from services.mt_builder import mt_builder, auto_detect_target_mt
from services.telemetry_bus import TelemetryBus, telemetry_bus
from services.validator import iso20022_validator

log = structlog.get_logger(__name__)

router = APIRouter(tags=["MX → MT Reverse Translation"])

# ---------------------------------------------------------------------------
# Sample ISO 20022 XML snippets (minimal valid examples per message type)
# ---------------------------------------------------------------------------

_SAMPLE_PACS008_CBPR = """<?xml version='1.0' encoding='UTF-8'?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>SAMPLE-PACS008-001</MsgId>
      <CreDtTm>2026-05-23T10:00:00+00:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf><SttlmMtd>CLRG</SttlmMtd></SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>SAMPLE-PACS008-001</InstrId>
        <EndToEndId>SAMPLE-PACS008-001</EndToEndId>
        <UETR>f9e4a3b2-1c5d-4e7f-8a9b-0d1e2f3a4b5c</UETR>
      </PmtId>
      <PmtTpInf><SvcLvl><Cd>SDVA</Cd></SvcLvl></PmtTpInf>
      <IntrBkSttlmAmt Ccy="USD">10000.00</IntrBkSttlmAmt>
      <IntrBkSttlmDt>2026-05-23</IntrBkSttlmDt>
      <ChrgBr>SHAR</ChrgBr>
      <DbtrAgt><FinInstnId><BICFI>BARCGB22XXX</BICFI></FinInstnId></DbtrAgt>
      <Dbtr>
        <Nm>ACME CORPORATION</Nm>
        <PstlAdr><TwnNm>LONDON</TwnNm><Ctry>GB</Ctry><AdrLine>1 HIGH STREET</AdrLine></PstlAdr>
      </Dbtr>
      <DbtrAcct><Id><IBAN>GB29NWBK60161331926819</IBAN></Id></DbtrAcct>
      <CdtrAgt><FinInstnId><BICFI>BOFAUS3NXXX</BICFI></FinInstnId></CdtrAgt>
      <Cdtr>
        <Nm>JOHN DOE</Nm>
        <PstlAdr><TwnNm>NEW YORK</TwnNm><Ctry>US</Ctry><AdrLine>123 MAIN STREET</AdrLine></PstlAdr>
      </Cdtr>
      <CdtrAcct><Id><IBAN>US64SVBKUS6S3300622287</IBAN></Id></CdtrAcct>
      <RmtInf><Ustrd>INVOICE 2026-INV-001</Ustrd></RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>"""

_SAMPLE_PACS009_CORE_CBPR = """<?xml version='1.0' encoding='UTF-8'?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <GrpHdr>
      <MsgId>SAMPLE-PACS009-CORE-001</MsgId>
      <CreDtTm>2026-05-23T10:00:00+00:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf><SttlmMtd>CLRG</SttlmMtd></SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>SAMPLE-PACS009-CORE-001</InstrId>
        <EndToEndId>SAMPLE-PACS009-CORE-001</EndToEndId>
        <UETR>a1b2c3d4-e5f6-4789-abcd-ef0123456789</UETR>
      </PmtId>
      <PmtTpInf><SvcLvl><Cd>SDVA</Cd></SvcLvl></PmtTpInf>
      <IntrBkSttlmAmt Ccy="CAD">250000.00</IntrBkSttlmAmt>
      <IntrBkSttlmDt>2026-05-23</IntrBkSttlmDt>
      <ChrgBr>SHAR</ChrgBr>
      <InstgAgt><FinInstnId><BICFI>ROYCCAT2XXX</BICFI></FinInstnId></InstgAgt>
      <InstdAgt><FinInstnId><BICFI>TDOMCATTXXX</BICFI></FinInstnId></InstdAgt>
      <Cdtr><FinInstnId><BICFI>TDOMCATTXXX</BICFI></FinInstnId></Cdtr>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>"""

_SAMPLE_PACS009_COV_CBPR = """<?xml version='1.0' encoding='UTF-8'?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.009.001.08">
  <FICdtTrf>
    <GrpHdr>
      <MsgId>SAMPLE-PACS009-COV-001</MsgId>
      <CreDtTm>2026-05-23T10:00:00+00:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf><SttlmMtd>CLRG</SttlmMtd></SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>SAMPLE-PACS009-COV-001</InstrId>
        <EndToEndId>SAMPLE-PACS009-COV-001</EndToEndId>
        <UETR>b2c3d4e5-f6a7-4890-bcde-f01234567890</UETR>
      </PmtId>
      <PmtTpInf><SvcLvl><Cd>SDVA</Cd></SvcLvl></PmtTpInf>
      <IntrBkSttlmAmt Ccy="USD">10000.00</IntrBkSttlmAmt>
      <IntrBkSttlmDt>2026-05-23</IntrBkSttlmDt>
      <ChrgBr>SHAR</ChrgBr>
      <InstgAgt><FinInstnId><BICFI>BARCGB22XXX</BICFI></FinInstnId></InstgAgt>
      <InstdAgt><FinInstnId><BICFI>BOFAUS3NXXX</BICFI></FinInstnId></InstdAgt>
      <Cdtr><FinInstnId><BICFI>BOFAUS3NXXX</BICFI></FinInstnId></Cdtr>
      <UndrlygCstmrCdtTrf>
        <Dbtr>
          <Nm>ACME CORPORATION</Nm>
          <PstlAdr><TwnNm>LONDON</TwnNm><Ctry>GB</Ctry></PstlAdr>
        </Dbtr>
        <DbtrAcct><Id><IBAN>GB29NWBK60161331926819</IBAN></Id></DbtrAcct>
        <Cdtr>
          <Nm>JOHN DOE</Nm>
          <PstlAdr><TwnNm>NEW YORK</TwnNm><Ctry>US</Ctry></PstlAdr>
        </Cdtr>
        <CdtrAcct><Id><IBAN>US64SVBKUS6S3300622287</IBAN></Id></CdtrAcct>
      </UndrlygCstmrCdtTrf>
    </CdtTrfTxInf>
  </FICdtTrf>
</Document>"""

_SAMPLE_PACS009_CORE_LYNX = _SAMPLE_PACS009_CORE_CBPR  # Same XSD, different BAH

_SAMPLE_PACS004 = """<?xml version='1.0' encoding='UTF-8'?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.004.001.09">
  <PmtRtr>
    <GrpHdr>
      <MsgId>SAMPLE-PACS004-001</MsgId>
      <CreDtTm>2026-05-23T12:00:00+00:00</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf><SttlmMtd>CLRG</SttlmMtd></SttlmInf>
    </GrpHdr>
    <TxInf>
      <RtrId>RTR-SAMPLE-001</RtrId>
      <OrgnlGrpInf>
        <OrgnlMsgId>SAMPLE-PACS008-001</OrgnlMsgId>
        <OrgnlMsgNmId>pacs.008.001.08</OrgnlMsgNmId>
      </OrgnlGrpInf>
      <OrgnlUETR>f9e4a3b2-1c5d-4e7f-8a9b-0d1e2f3a4b5c</OrgnlUETR>
      <RtrdIntrBkSttlmAmt Ccy="USD">10000.00</RtrdIntrBkSttlmAmt>
      <IntrBkSttlmDt>2026-05-23</IntrBkSttlmDt>
      <ChrgBr>SHAR</ChrgBr>
      <InstgAgt><FinInstnId><BICFI>BOFAUS3NXXX</BICFI></FinInstnId></InstgAgt>
      <InstdAgt><FinInstnId><BICFI>BARCGB22XXX</BICFI></FinInstnId></InstdAgt>
      <RtrRsnInf><Rsn><Cd>AM09</Cd></Rsn></RtrRsnInf>
    </TxInf>
  </PmtRtr>
</Document>"""

_SAMPLES: Dict[str, Dict[str, str]] = {
    "pacs.008.001.08": {
        "CBPR+": _SAMPLE_PACS008_CBPR,
        "LYNX":  _SAMPLE_PACS008_CBPR,
    },
    "pacs.009.001.08": {
        "CBPR+": _SAMPLE_PACS009_CORE_CBPR,
        "LYNX":  _SAMPLE_PACS009_CORE_LYNX,
    },
    "pacs.009.001.08-cov": {
        "CBPR+": _SAMPLE_PACS009_COV_CBPR,
        "LYNX":  _SAMPLE_PACS009_COV_CBPR,
    },
    "pacs.004.001.09": {
        "CBPR+": _SAMPLE_PACS004,
        "LYNX":  _SAMPLE_PACS004,
    },
}


# ---------------------------------------------------------------------------
# POST /mx-translate  — MX → MT
# ---------------------------------------------------------------------------


@router.post(
    "/mx-translate",
    response_model=MXTranslateResponse,
    summary="Translate ISO 20022 XML → SWIFT MT string (Reverse Direction)",
    responses={
        400: {"description": "XML parse or field extraction error"},
        422: {"description": "Unsupported message type or scheme combination"},
    },
)
async def translate_mx_to_mt(body: MXTranslateRequest) -> Any:
    """
    Parses an ISO 20022 XML message and converts it to a raw SWIFT MT string.

    **Scheme-aware translation:**
    - **CBPR+**: `pacs.009 CORE → MT202`, `pacs.009 COV → MT202COV`
    - **LYNX** (Canada): `pacs.009 CORE → MT205`, `pacs.009 COV → MT205COV`

    `pacs.004` return messages auto-detect what was originally returned
    by reading `<OrgnlMsgNmId>` and produce MT103RETURN, MT202RETURN,
    or MT205RETURN accordingly.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Step 1: Parse MX XML
    try:
        parsed = mx_parser.parse(body.xml_content, body.source_type, body.scheme)
    except ValueError as exc:
        audit_id = await audit_logger.log(
            event_type="MX_TRANSLATION",
            module="mx_translate",
            status="ERROR",
            details={"error": str(exc), "source_type": body.source_type, "scheme": body.scheme},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "MX_PARSE_ERROR", "message": str(exc), "audit_id": audit_id},
        )

    # Step 2: Determine target MT type
    try:
        target_mt = body.target_mt_override or auto_detect_target_mt(parsed)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "TARGET_DETECTION_FAILED", "message": str(exc)},
        )

    # Step 3: Build MT string
    try:
        mt_raw = mt_builder.build(parsed, target_mt)
    except ValueError as exc:
        audit_id = await audit_logger.log(
            event_type="MX_TRANSLATION",
            module="mx_translate",
            status="ERROR",
            details={"error": str(exc), "target_mt": target_mt},
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error": "MT_BUILD_ERROR", "message": str(exc), "audit_id": audit_id},
        )
    except Exception as exc:
        log.exception("mx_to_mt_unexpected_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR"},
        )

    # Step 4: Audit log
    uetr = parsed.get("uetr")
    audit_id = await audit_logger.log(
        event_type="MX_TRANSLATION",
        module="mx_translate",
        status="SUCCESS",
        details={
            "source_type": body.source_type,
            "target_mt": target_mt,
            "scheme": body.scheme,
            "variant": parsed.get("variant", "STANDARD"),
        },
        uetr=uetr,
        message_type=target_mt,
    )

    # Step 5: Telemetry
    event = TelemetryBus.make_event(
        event_type="MX_TRANSLATION_COMPLETE",
        module=1,
        severity="INFO",
        summary=f"{body.source_type} [{body.scheme}] → {target_mt} translation succeeded",
        data={"audit_id": audit_id, "uetr": uetr, "scheme": body.scheme},
    )
    await telemetry_bus.broadcast(event)

    return MXTranslateResponse(
        status="SUCCESS",
        source_type=body.source_type,
        target_mt_type=target_mt,
        scheme=body.scheme,
        variant=parsed.get("variant", "STANDARD"),
        mt_raw=mt_raw,
        uetr=uetr,
        audit_id=audit_id,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# POST /mx-translate/cover  — pacs.008 → pacs.009COV
# ---------------------------------------------------------------------------


@router.post(
    "/mx-translate/cover",
    response_model=MXCoverResponse,
    summary="Convert pacs.008 → pacs.009COV cover payment (Direct to Cover)",
    responses={
        400: {"description": "Invalid pacs.008 XML or missing required fields"},
    },
)
async def convert_to_cover(body: MXCoverRequest) -> Any:
    """
    Wraps a `pacs.008.001.08` customer credit transfer into a
    `pacs.009.001.08 COV` cover payment.

    **UETR rules (scheme-aware):**
    - **CBPR+**: The cover leg gets a **new UUID4 UETR**. The original
      pacs.008 UETR is preserved in the `<UndrlygCstmrCdtTrf>` context.
    - **LYNX**: The cover leg carries the **same UETR** as the underlying
      pacs.008. This is a LYNX-specific rule for direct reconciliation.

    **Settlement method:** `CLRG` only (mandatory for both CBPR+ and LYNX).
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        pacs009cov_xml, cover_uetr, original_uetr = (
            await mx_to_mx_converter.convert_pacs008_to_pacs009cov(
                body.pacs008_xml, body.scheme
            )
        )
    except ValueError as exc:
        audit_id = await audit_logger.log(
            event_type="MX_COVER_CONVERSION",
            module="mx_translate",
            status="ERROR",
            details={"error": str(exc), "scheme": body.scheme},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "COVER_CONVERSION_ERROR", "message": str(exc), "audit_id": audit_id},
        )
    except Exception as exc:
        log.exception("cover_conversion_unexpected_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "INTERNAL_ERROR"},
        )

    audit_id = await audit_logger.log(
        event_type="MX_COVER_CONVERSION",
        module="mx_translate",
        status="SUCCESS",
        details={
            "scheme": body.scheme,
            "original_uetr": original_uetr,
            "cover_uetr": cover_uetr,
            "uetr_propagated": (cover_uetr == original_uetr),
        },
        uetr=original_uetr,
        message_type="pacs.009.001.08",
    )

    event = TelemetryBus.make_event(
        event_type="MX_COVER_CONVERSION_COMPLETE",
        module=1,
        severity="INFO",
        summary=f"pacs.008 → pacs.009COV [{body.scheme}] conversion succeeded",
        data={
            "audit_id": audit_id,
            "scheme": body.scheme,
            "same_uetr": (cover_uetr == original_uetr),
        },
    )
    await telemetry_bus.broadcast(event)

    uetr_rule = (
        "LYNX: Same UETR propagated from pacs.008 for direct reconciliation"
        if body.scheme == "LYNX"
        else "CBPR+: New UUID4 generated for cover leg; original UETR in UndrlygCstmrCdtTrf"
    )

    return MXCoverResponse(
        status="SUCCESS",
        scheme=body.scheme,
        pacs009cov_xml=pacs009cov_xml,
        cover_uetr=cover_uetr,
        original_uetr=original_uetr,
        uetr_rule=uetr_rule,
        audit_id=audit_id,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# GET /mx-translate/sample/{source_type}/{scheme}
# ---------------------------------------------------------------------------


@router.get(
    "/mx-translate/sample/{source_type_key}/{scheme}",
    summary="Get sample ISO 20022 XML for a given message type and scheme",
)
async def get_mx_sample(source_type_key: str, scheme: str) -> Dict[str, str]:
    """
    Returns a sample ISO 20022 XML string for the given source type and scheme.

    source_type_key options:
      pacs008, pacs009-core, pacs009-cov, pacs004

    scheme options: CBPR+, LYNX
    """
    key_map = {
        "pacs008":     "pacs.008.001.08",
        "pacs009":     "pacs.009.001.08",
        "pacs009-core": "pacs.009.001.08",
        "pacs009-cov": "pacs.009.001.08-cov",
        "pacs004":     "pacs.004.001.09",
    }
    scheme_upper = scheme.upper()
    if scheme_upper not in ("CBPR+", "LYNX"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_SCHEME", "message": "scheme must be 'CBPR+' or 'LYNX'"},
        )

    resolved_key = key_map.get(source_type_key.lower())
    if not resolved_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SAMPLE_NOT_FOUND",
                "message": f"No sample for '{source_type_key}'",
                "available": list(key_map.keys()),
            },
        )

    sample_xml = _SAMPLES.get(resolved_key, {}).get(scheme_upper)
    if not sample_xml:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "SAMPLE_NOT_FOUND", "message": f"No sample for {resolved_key}/{scheme_upper}"},
        )

    return {
        "source_type": resolved_key,
        "scheme": scheme_upper,
        "sample_xml": sample_xml,
    }
