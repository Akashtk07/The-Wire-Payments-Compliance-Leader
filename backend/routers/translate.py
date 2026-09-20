"""
Translation & Validation router.

Endpoints:
  POST /api/v1/translate         — MT → MX translation
  POST /api/v1/validate          — ISO 20022 XML validation
  GET  /api/v1/translate/sample/{message_type} — Sample MT message strings
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from models.schemas import (
    MTTranslateRequest,
    MXValidateRequest,
    TranslationResponse,
    ValidationExceptionResponse,
)
from services.audit_logger import audit_logger
from services.mt_parser import (
    SAMPLE_MT103,
    SAMPLE_MT202,
    SAMPLE_MT202COV,
    SAMPLE_MT103RETURN,
    SAMPLE_MT202RETURN,
    SAMPLE_MT205,
    SAMPLE_MT205COV,
    SAMPLE_MT205RETURN,
    mt_parser,
)
from services.mx_translator import ValidationException, mx_translator
from services.telemetry_bus import TelemetryBus, telemetry_bus
from services.validator import iso20022_validator

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Translation & Validation"])

# ---------------------------------------------------------------------------
# Sample messages registry
# ---------------------------------------------------------------------------

_SAMPLES: Dict[str, str] = {
    "MT103": SAMPLE_MT103,
    "MT103STP": SAMPLE_MT103,
    "MT202": SAMPLE_MT202,
    "MT202COV": SAMPLE_MT202COV,
    "MT204": (
        "{1:F01MARKDEFFXXXX0000000000}"
        "{2:I204DEUTDEDBXXXXN}"
        "{4:\n"
        ":20:DD20260523001\n"
        ":19:EUR500000,00\n"
        ":25:DE89370400440532013000\n"
        ":30:260523\n"
        "-}"
        "{5:{CHK:ABCDEF012345}}"
    ),
    "MT103RETURN": SAMPLE_MT103RETURN,
    "MT202RETURN": SAMPLE_MT202RETURN,
    # LYNX Canada domestic variants
    "MT205":       SAMPLE_MT205,
    "MT205COV":    SAMPLE_MT205COV,
    "MT205RETURN": SAMPLE_MT205RETURN,
}


# ---------------------------------------------------------------------------
# POST /translate
# ---------------------------------------------------------------------------


@router.post(
    "/translate",
    response_model=TranslationResponse,
    summary="Translate SWIFT MT message to ISO 20022 XML",
    responses={
        400: {"description": "MT parsing error"},
        422: {"model": ValidationExceptionResponse, "description": "SWIFT ISO mutation denied"},
    },
)
async def translate_mt_to_mx(body: MTTranslateRequest) -> Any:
    """
    Parses a raw SWIFT MT message and translates it to ISO 20022 XML per **CBPR+ R2025**.

    As of Nov 22, 2025, MT103/MT202/MT202COV are retired from SWIFT FINplus.
    All generated XML conforms to CBPR+ R2025 rules:
    - **UETR** (UUID4) mandatory in `<PmtId><UETR>`
    - **ChrgBr = SHAR** for interbank messages
    - **Hybrid PostalAddress**: `<TwnNm>` and `<Ctry>` mandatory
    - **PmtTpInf/SvcLvl/Cd** = SDVA included

    - **mt_raw**: Raw SWIFT MT string (with block delimiters `{1:…}{4:…}`)
    - **source_type**: One of MT103, MT103STP, MT202, MT202COV, MT204
    - **target_type**: Optional override for the ISO 20022 target type
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    force_output = getattr(body, "force_output", False)

    # --- Step 1: Parse MT ---
    try:
        parsed = mt_parser.parse(body.mt_raw, body.source_type)
    except ValueError as exc:
        audit_id = await audit_logger.log(
            event_type="TRANSLATION",
            module="translate",
            status="ERROR",
            details={"error": str(exc), "source_type": body.source_type},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "MT_PARSE_ERROR",
                "message": str(exc),
                "audit_id": audit_id,
            },
        )

    # --- Step 2: Translate to MX ---
    forced_warnings: list[str] = []  # CBPR+ warnings accumulated in force_output mode

    try:
        xml_output, message_type = await mx_translator.translate(
            parsed, body.source_type, body.target_type
        )
    except ValidationException as ve:
        if not force_output:
            # Strict mode: return 422 and halt
            audit_id = await audit_logger.log(
                event_type="TRANSLATION",
                module="translate",
                status="VALIDATION_EXCEPTION",
                details={
                    "error_code": "SWIFT_ISO_MUTATION_DENIED",
                    "field_name": ve.field_name,
                    "message_type": ve.message_type,
                    "message": ve.message,
                },
                message_type=body.source_type,
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=ValidationExceptionResponse(
                    message=ve.message,
                    action=ve.action,
                ).model_dump(),
            )
        # Full mode: record the CBPR+ warning but continue building XML
        forced_warnings.append(f"[CBPR+ RULE] {ve.message}")
        log.warning("force_output_mode_cbpr_warning", warning=ve.message, source=body.source_type)
        # Re-attempt translation without pre-validation guards
        try:
            xml_output, message_type = await mx_translator.translate(
                parsed, body.source_type, body.target_type, skip_validation=True
            )
        except Exception as exc2:
            audit_id = await audit_logger.log(
                event_type="TRANSLATION",
                module="translate",
                status="ERROR",
                details={"error": str(exc2), "source_type": body.source_type},
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "TRANSLATION_ERROR", "audit_id": audit_id},
            )
    except Exception as exc:
        log.exception("translation_unexpected_error", error=str(exc))
        audit_id = await audit_logger.log(
            event_type="TRANSLATION",
            module="translate",
            status="ERROR",
            details={"error": str(exc), "source_type": body.source_type},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "TRANSLATION_ERROR", "audit_id": audit_id},
        )

    # --- Step 3: Validate generated XML ---
    is_valid, validation_errors = await iso20022_validator.validate(xml_output, message_type)

    # In force_output mode, include CBPR+ warnings alongside XSD errors
    all_errors = forced_warnings + validation_errors

    # --- Step 4: Audit log ---
    uetr = parsed.get("uetr")
    final_status = "SUCCESS" if (is_valid and not forced_warnings) else "PARTIAL"
    audit_id = await audit_logger.log(
        event_type="TRANSLATION",
        module="translate",
        status=final_status,
        details={
            "source_type": body.source_type,
            "target_type": message_type,
            "validation_errors": all_errors,
            "force_output": force_output,
        },
        uetr=uetr,
        message_type=message_type,
    )

    # --- Step 5: Broadcast telemetry ---
    event = TelemetryBus.make_event(
        event_type="TRANSLATION_COMPLETE",
        module=1,
        severity="INFO" if is_valid else "WARN",
        summary=f"{body.source_type} → {message_type} translation {'succeeded' if is_valid else 'completed with warnings'}",
        data={"audit_id": audit_id, "uetr": uetr, "validation_errors": len(all_errors)},
    )
    await telemetry_bus.broadcast(event)

    return TranslationResponse(
        status=final_status,
        message_type=message_type,
        xml_output=xml_output,
        uetr=uetr,
        validation_errors=all_errors,
        audit_id=audit_id,
        timestamp=timestamp,
    )


# ---------------------------------------------------------------------------
# POST /validate
# ---------------------------------------------------------------------------


@router.post(
    "/validate",
    summary="Validate an ISO 20022 XML message",
)
async def validate_mx(body: MXValidateRequest) -> Dict[str, Any]:
    """
    Validates an ISO 20022 XML string against XSD (if available) and **CBPR+ R2025** rules.

    CBPR+ R2025 rules checked:
    - UETR mandatory and UUID4-validated in `<PmtId><UETR>`
    - ChrgBr must be `SHAR` for interbank pacs messages
    - PostalAddress: `<TwnNm>` and `<Ctry>` mandatory in structured/hybrid mode
    - pacs.009 COV: `<UndrlygCstmrCdtTrf>` with `<Dbtr>` and `<Cdtr>` required
    - pacs.004: `<OrgnlUETR>`, `<OrgnlMsgId>`, `<RtrId>`, and valid `<Rsn><Cd>` required
    - Extended R2025 return reason code list (24 codes)
    """
    is_valid, errors = await iso20022_validator.validate(
        body.xml_content, body.message_type
    )

    audit_id = await audit_logger.log(
        event_type="VALIDATION",
        module="translate",
        status="SUCCESS" if is_valid else "ERROR",
        details={
            "message_type": body.message_type,
            "is_valid": is_valid,
            "errors": errors,
        },
        message_type=body.message_type,
    )

    event = TelemetryBus.make_event(
        event_type="VALIDATION_COMPLETE",
        module=1,
        severity="INFO" if is_valid else "WARN",
        summary=f"Validation of {body.message_type}: {'PASS' if is_valid else 'FAIL'}",
        data={"audit_id": audit_id, "error_count": len(errors)},
    )
    await telemetry_bus.broadcast(event)

    return {
        "status": "VALID" if is_valid else "INVALID",
        "message_type": body.message_type,
        "validation_errors": errors,
        "audit_id": audit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# GET /translate/sample/{message_type}
# ---------------------------------------------------------------------------


@router.get(
    "/translate/sample/{message_type}",
    summary="Get a sample raw SWIFT MT message for a given type",
)
async def get_sample_mt(message_type: str) -> Dict[str, str]:
    """
    Returns a sample raw SWIFT MT string for the requested message type.
    Supported: MT103, MT103STP, MT202, MT202COV, MT204, MT103RETURN, MT202RETURN
    """
    key = message_type.upper()
    sample = _SAMPLES.get(key)
    if not sample:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "SAMPLE_NOT_FOUND",
                "message": f"No sample available for message type '{message_type}'.",
                "available": list(_SAMPLES.keys()),
            },
        )
    return {
        "message_type": key,
        "sample_mt": sample,
    }
