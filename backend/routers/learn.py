"""
Learn router — LLM-powered financial domain knowledge Q&A.

Endpoints:
  POST /api/v1/learn         — Query the LLM about financial domain topics
  GET  /api/v1/learn/topics  — List available learning topics
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from models.schemas import LearnRequest, LearnResponse
from services.audit_logger import audit_logger
from services.auth_service import User, get_current_user
from services.llm_router import llm_router
from services.rag_pipeline import rag_pipeline
from services.telemetry_bus import TelemetryBus, telemetry_bus

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Domain Learning"])

# ---------------------------------------------------------------------------
# Hardcoded topic catalogue
# ---------------------------------------------------------------------------

LEARNING_TOPICS: List[Dict[str, str]] = [
    {
        "id": "pacs008",
        "title": "pacs.008 FI-to-FI Customer Credit Transfer",
        "description": (
            "ISO 20022 equivalent of SWIFT MT103. Covers the full debtor-to-creditor "
            "chain including <DbtrAgt>, <Dbtr> with IBAN, <CdtrAgt>, <Cdtr>, "
            "<IntrBkSttlmAmt>, and <InstdAmt> for FX transactions."
        ),
        "message_type": "pacs.008.001.08",
    },
    {
        "id": "pacs009_core",
        "title": "pacs.009 FI-to-FI Credit Transfer — CORE Variant",
        "description": (
            "ISO 20022 equivalent of SWIFT MT202. Used for bank-to-bank fund transfers "
            "without underlying retail customer data. Must NOT contain <InstructedAmt> "
            "or retail customer elements per CBPR+ rules."
        ),
        "message_type": "pacs.009.001.08",
    },
    {
        "id": "pacs009_cov",
        "title": "pacs.009 FI-to-FI Credit Transfer — COV Variant",
        "description": (
            "ISO 20022 equivalent of SWIFT MT202COV. Includes <UndrlygCstmrCdtTrf> "
            "block carrying the original retail customer credit transfer details. "
            "Required when covering a pacs.008 transaction."
        ),
        "message_type": "pacs.009.001.08",
    },
    {
        "id": "pacs009_adv",
        "title": "pacs.009 FI-to-FI Credit Transfer — ADV Variant",
        "description": (
            "ISO 20022 equivalent of SWIFT MT204. Used for direct debit advices "
            "between financial institutions."
        ),
        "message_type": "pacs.009.001.08",
    },
    {
        "id": "pacs004",
        "title": "pacs.004 Payment Return",
        "description": (
            "ISO 20022 payment return message. Must reference original transaction "
            "via <OrgnlUETR> (UUID4) and <OrgnlMsgId>. CBPR+ R2025 extended return "
            "reason codes: AM09 (wrong amount), AGNT (agent decision), CUST (customer "
            "request), DUPL (duplicate), AC04 (closed account), AC06 (blocked), "
            "BE04 (missing creditor address), RR01-RR04 (regulatory), and more."
        ),
        "message_type": "pacs.004.001.09",
    },
    {
        "id": "mt103_fields",
        "title": "MT103 / MT103 STP Field Breakdown",
        "description": (
            "Detailed walkthrough of all SWIFT MT103 tagged fields: :20: (TxRef), "
            ":23B: (BankOpCode), :32A: (Value Date/CCY/Amount), :50K: (Ordering Customer), "
            ":52A: (Ordering Institution), :57A: (Account-With Institution), "
            ":59: (Beneficiary), :70: (Remittance Info), :71A: (Charges)."
        ),
        "message_type": "MT103",
    },
    {
        "id": "mt202_fields",
        "title": "MT202 / MT202COV Field Breakdown",
        "description": (
            "Detailed walkthrough of SWIFT MT202 fields: :20:, :21:, :32A:, :52A:, "
            ":53A:, :54A:, :57A:, :58A:. Plus MT202COV extras: :50K: (underlying "
            "ordering customer) and :59: (underlying beneficiary)."
        ),
        "message_type": "MT202",
    },
    {
        "id": "cbpr_plus",
        "title": "SWIFT CBPR+ R2025 — Current Mandatory Standard",
        "description": (
            "CBPR+ R2025 is the current mandatory SWIFT standard (effective Nov 22, 2025). "
            "MT103/MT202/MT202COV retired from SWIFT FINplus. Key R2025 rules: "
            "hybrid PostalAddress with mandatory TownName+Country, UETR mandatory in every "
            "pacs message, ChrgBr=SHAR for interbank, PmtTpInf/SvcLvl recommended. "
            "Fully unstructured addresses will be rejected from Nov 2026."
        ),
        "message_type": None,
    },
    {
        "id": "cbpr_r2025_address",
        "title": "CBPR+ R2025 — Hybrid Postal Address Rules",
        "description": (
            "R2025 introduced hybrid addressing: TownName and Country are mandatory "
            "in all structured and hybrid postal addresses. Up to 2 AddressLine elements "
            "are permitted alongside structured fields. Fully unstructured (free-text only) "
            "addresses are deprecated and will be rejected by the SWIFT network from Nov 2026. "
            "Affects <Dbtr>, <Cdtr>, and underlying debtor/creditor in pacs.008 and pacs.009 COV."
        ),
        "message_type": None,
    },
    {
        "id": "iso20022_settlement",
        "title": "ISO 20022 Settlement Chain Mechanics",
        "description": (
            "End-to-end walkthrough of a cross-border payment settlement chain: "
            "originator bank → correspondent → nostro/vostro accounts → "
            "beneficiary bank. Explains how pacs.008 and pacs.009 messages "
            "flow through each leg."
        ),
        "message_type": None,
    },
    {
        "id": "uetr_tracking",
        "title": "UETR and End-to-End Payment Tracking",
        "description": (
            "Explanation of the UETR (Unique End-to-end Transaction Reference) UUID4 "
            "identifier mandated by SWIFT gpi. Covers MT block 3 field {121:}, "
            "ISO 20022 <PmtId><UETR>, and the SWIFT gpi Tracker API."
        ),
        "message_type": None,
    },
    {
        "id": "nostro_vostro",
        "title": "Nostro/Vostro Account Mechanics",
        "description": (
            "Explanation of Nostro (our account at your bank) and Vostro "
            "(your account at our bank) accounts in the context of correspondent "
            "banking, settlement, and liquidity management."
        ),
        "message_type": None,
    },
    {
        "id": "clearing_systems",
        "title": "TARGET2 / FedNow / CHAPS Clearing",
        "description": (
            "Overview of major real-time gross settlement (RTGS) systems: "
            "TARGET2 (Eurozone), FedNow (USA, 2023+), CHAPS (UK). "
            "Covers settlement finality, operating hours, and ISO 20022 adoption status."
        ),
        "message_type": None,
    },
]


# ---------------------------------------------------------------------------
# POST /learn
# ---------------------------------------------------------------------------


@router.post(
    "/learn",
    response_model=LearnResponse,
    summary="Query the financial domain knowledge base",
)
async def learn_query(
    body: LearnRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Submit a financial domain question to the LLM router.
    Optionally provide additional context or guideline version filter.
    Supports cross-version comparison when multiple versions are selected.
    """
    log.info(
        "learn_query",
        query_preview=body.query[:80],
        user=current_user.username,
        versions=body.selected_versions,
        cross_version=body.cross_version_compare,
    )

    answer = ""
    sources = []

    # Route to RAG pipeline if documents are indexed, else fall back to pure LLM
    try:
        from services.rag_pipeline import _get_collection
        rag_count = _get_collection().count()
    except Exception:
        rag_count = 0

    if rag_count > 0:
        try:
            if body.cross_version_compare and body.selected_versions and len(body.selected_versions) > 1:
                # Cross-version comparison mode
                result = await rag_pipeline.query_cross_version(
                    question=body.query,
                    selected_versions=body.selected_versions,
                    top_k=4,
                )
                answer = result["unified_comparison"]
                sources = [f"{v} documents" for v in result["versions_compared"]]
            else:
                answer, src_metas = await rag_pipeline.query(
                    body.query,
                    top_k=5,
                    version_filter=body.selected_versions,
                )
                sources = [m.get("filename", "Document") for m in src_metas]
        except Exception as exc:
            log.warning("rag_query_fallback", error=str(exc))
            answer = await llm_router.query(
                body.query, context=body.context, version_context=body.selected_versions
            )
    else:
        answer = await llm_router.query(
            body.query, context=body.context, version_context=body.selected_versions
        )

    if not answer:
        answer = await llm_router.query(
            body.query, context=body.context, version_context=body.selected_versions
        )

    if not sources:
        sources = ["LLM Domain Knowledge", "Financial Systems Educator Prompt"]

    # Heuristically detect which message type the answer references
    msg_type_ref = None
    for keyword, mt in [
        ("pacs.008", "pacs.008.001.08"),
        ("pacs.009", "pacs.009.001.08"),
        ("pacs.004", "pacs.004.001.09"),
        ("MT103", "MT103"),
        ("MT202", "MT202"),
        ("MT204", "MT204"),
    ]:
        if keyword in answer or keyword in body.query:
            msg_type_ref = mt
            break

    audit_id = await audit_logger.log(
        event_type="LEARN_QUERY",
        module="learn",
        status="SUCCESS",
        details={
            "query": body.query[:200],
            "has_context": body.context is not None,
            "message_type_referenced": msg_type_ref,
            "selected_versions": body.selected_versions,
            "cross_version_compare": body.cross_version_compare,
            "queried_by": current_user.username,
        },
        message_type=msg_type_ref,
    )

    event = TelemetryBus.make_event(
        event_type="LEARN_QUERY_COMPLETE",
        module=2,
        severity="INFO",
        summary=f"Learn query processed: '{body.query[:60]}...'",
        data={"audit_id": audit_id, "message_type_referenced": msg_type_ref, "versions": body.selected_versions},
    )
    await telemetry_bus.broadcast(event)

    return LearnResponse(
        answer=answer,
        sources=sources,
        message_type_referenced=msg_type_ref,
        audit_id=audit_id,
    )


# ---------------------------------------------------------------------------
# GET /learn/topics
# ---------------------------------------------------------------------------


@router.get(
    "/learn/topics",
    summary="List available financial domain learning topics",
)
async def list_topics() -> Dict[str, Any]:
    """
    Returns a curated list of learning topics covering ISO 20022, SWIFT MT,
    CBPR+ guidelines, settlement mechanics, and clearing systems.
    """
    return {
        "total": len(LEARNING_TOPICS),
        "topics": LEARNING_TOPICS,
    }
