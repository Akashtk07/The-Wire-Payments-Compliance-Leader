"""
Pydantic v2 schemas for The Compliance Leader API.
All models use strict type annotations and field validators where appropriate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Translation / Validation schemas
# ---------------------------------------------------------------------------


class MTTranslateRequest(BaseModel):
    """Request body for MT → MX translation endpoint."""

    mt_raw: str = Field(
        ...,
        description="Raw SWIFT MT message string including block delimiters",
        min_length=10,
    )
    source_type: Literal[
        "MT103", "MT103STP",
        "MT202", "MT202COV", "MT204",
        "MT205", "MT205COV",
        "MT103RETURN", "MT202RETURN", "MT205RETURN"
    ] = Field(
        ...,
        description="The SWIFT MT message type being submitted",
    )
    target_type: Optional[str] = Field(
        default=None,
        description=(
            "Override the auto-detected ISO 20022 target type "
            "(e.g. pacs.008.001.08). Leave None for auto-detection."
        ),
    )
    force_output: bool = Field(
        default=False,
        description=(
            "Full Translation Mode: when True, validation errors become warnings "
            "and XML is always returned. When False (default), strict CBPR+ "
            "rule violations raise a ValidationException."
        ),
    )

    model_config = {"str_strip_whitespace": True}


class MXValidateRequest(BaseModel):
    """Request body for standalone ISO 20022 XML validation."""

    xml_content: str = Field(
        ...,
        description="The ISO 20022 XML string to validate",
        min_length=5,
    )
    message_type: str = Field(
        ...,
        description="ISO 20022 message type identifier (e.g. pacs.008.001.08)",
        examples=["pacs.008.001.08", "pacs.009.001.08", "pacs.004.001.09"],
    )


class TranslationResponse(BaseModel):
    """Response returned after a successful or partial MT → MX translation."""

    status: str = Field(..., description="'SUCCESS', 'PARTIAL', or 'ERROR'")
    message_type: str = Field(
        ..., description="ISO 20022 message type that was generated"
    )
    xml_output: Optional[str] = Field(
        default=None, description="The generated ISO 20022 XML string"
    )
    uetr: Optional[str] = Field(
        default=None, description="Unique End-to-end Transaction Reference (UUID4)"
    )
    validation_errors: List[str] = Field(
        default_factory=list,
        description="List of CBPR+ / XSD validation errors (empty if clean)",
    )
    audit_id: str = Field(..., description="Immutable audit log entry identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the operation")


class ValidationExceptionResponse(BaseModel):
    """Returned (HTTP 422) when a SWIFT ISO schema mutation is prohibited."""

    status: Literal["VALIDATION_EXCEPTION"] = "VALIDATION_EXCEPTION"
    error_code: Literal["SWIFT_ISO_MUTATION_DENIED"] = "SWIFT_ISO_MUTATION_DENIED"
    message: str = Field(..., description="Human-readable explanation of the denial")
    action: str = Field(
        ...,
        description="Remediation action the caller should take",
        examples=["Submit an MT202COV to include the underlying customer block"],
    )


# ---------------------------------------------------------------------------
# MX → MT Reverse Translation schemas
# ---------------------------------------------------------------------------


class MXTranslateRequest(BaseModel):
    """Request body for MX → MT reverse translation endpoint."""

    xml_content: str = Field(
        ...,
        description="Raw ISO 20022 XML string (pacs.008, pacs.009, or pacs.004)",
        min_length=10,
    )
    source_type: Literal[
        "pacs.008.001.08",
        "pacs.009.001.08",
        "pacs.004.001.09",
    ] = Field(
        ...,
        description="The ISO 20022 message type being submitted",
    )
    scheme: Literal["CBPR+", "LYNX"] = Field(
        default="CBPR+",
        description=(
            "Payment scheme: 'CBPR+' for global cross-border (SWIFT FINplus) "
            "or 'LYNX' for Canada domestic high-value payments. "
            "Determines MT output type (e.g. LYNX pacs.009 CORE → MT205, CBPR+ → MT202)."
        ),
    )
    target_mt_override: Optional[str] = Field(
        default=None,
        description=(
            "Optional: Override the auto-detected MT type "
            "(e.g. 'MT202', 'MT205'). Leave None for auto-detection."
        ),
    )

    model_config = {"str_strip_whitespace": True}


class MXTranslateResponse(BaseModel):
    """Response from MX → MT reverse translation."""

    status: str = Field(..., description="'SUCCESS' or 'ERROR'")
    source_type: str = Field(..., description="ISO 20022 source message type")
    target_mt_type: str = Field(
        ..., description="SWIFT MT type produced (e.g. MT103, MT202, MT205, MT205COV)"
    )
    scheme: str = Field(..., description="Scheme used: CBPR+ or LYNX")
    variant: str = Field(
        default="STANDARD",
        description="Message variant: STANDARD, STP, CORE, COV, PACS008_RETURN, PACS009_RETURN",
    )
    mt_raw: Optional[str] = Field(
        default=None, description="The generated raw SWIFT MT message string"
    )
    uetr: Optional[str] = Field(
        default=None, description="UETR extracted from the XML"
    )
    audit_id: str = Field(..., description="Immutable audit log entry identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class MXCoverRequest(BaseModel):
    """Request body for pacs.008 → pacs.009COV cover conversion."""

    pacs008_xml: str = Field(
        ...,
        description="Raw pacs.008.001.08 XML to convert into a pacs.009COV cover payment",
        min_length=10,
    )
    scheme: Literal["CBPR+", "LYNX"] = Field(
        default="CBPR+",
        description=(
            "Scheme determines UETR handling: "
            "CBPR+ = new UETR for cover leg; "
            "LYNX = same UETR as pacs.008 (propagated for reconciliation)."
        ),
    )

    model_config = {"str_strip_whitespace": True}


class MXCoverResponse(BaseModel):
    """Response from pacs.008 → pacs.009COV conversion."""

    status: str = Field(..., description="'SUCCESS' or 'ERROR'")
    scheme: str = Field(..., description="Scheme used: CBPR+ or LYNX")
    pacs009cov_xml: Optional[str] = Field(
        default=None, description="The generated pacs.009COV XML string"
    )
    cover_uetr: Optional[str] = Field(
        default=None,
        description="UETR assigned to the cover leg (new for CBPR+, same as pacs.008 for LYNX)",
    )
    original_uetr: Optional[str] = Field(
        default=None, description="Original UETR from the input pacs.008"
    )
    uetr_rule: str = Field(
        default="",
        description="Explanation of the UETR rule applied (scheme-specific)",
    )
    audit_id: str = Field(..., description="Immutable audit log entry identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ---------------------------------------------------------------------------
# Prompt Engineering schemas
# ---------------------------------------------------------------------------


class PromptTryRequest(BaseModel):
    """Request body for the Prompt Engineering 'Try It Live' endpoint."""

    prompt: str = Field(
        ...,
        description="The prompt text to send to the LLM",
        min_length=5,
    )
    technique: Optional[str] = Field(
        default=None,
        description="Prompt engineering technique being demonstrated (e.g. 'chain_of_thought')",
    )
    topic_id: Optional[str] = Field(
        default=None,
        description="The topic ID this prompt belongs to for context logging",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional system/role prompt to prepend (for role prompting technique)",
    )


class PromptTryResponse(BaseModel):
    """Response from Prompt Engineering 'Try It Live'."""

    response: str = Field(..., description="LLM-generated response to the prompt")
    technique: Optional[str] = Field(default=None)
    topic_id: Optional[str] = Field(default=None)
    model_used: str = Field(..., description="LLM model that generated the response")
    audit_id: str = Field(..., description="Immutable audit log entry identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")


# ---------------------------------------------------------------------------
# Learn / LLM schemas
# ---------------------------------------------------------------------------


class LearnRequest(BaseModel):
    """Request body for the domain-knowledge learning endpoint."""

    query: str = Field(
        ...,
        description="The financial domain question or topic to explore",
        min_length=3,
    )
    context: Optional[str] = Field(
        default=None,
        description=(
            "Optional additional context (e.g. an XML snippet or field value) "
            "to anchor the LLM response"
        ),
    )
    selected_versions: Optional[List[str]] = Field(
        default=None,
        description="Guideline version labels to focus the answer on (e.g. ['CBPR+ R2025'])",
    )
    cross_version_compare: bool = Field(
        default=False,
        description="If True and multiple selected_versions, perform per-version comparison",
    )


class LearnResponse(BaseModel):
    """Response from the LLM-powered domain-knowledge endpoint."""

    answer: str = Field(..., description="The synthesised expert answer")
    sources: List[str] = Field(
        default_factory=list,
        description="Source references used to construct the answer",
    )
    message_type_referenced: Optional[str] = Field(
        default=None,
        description="ISO 20022 or MT message type most relevant to the answer",
    )
    audit_id: str = Field(..., description="Immutable audit log entry identifier")


# ---------------------------------------------------------------------------
# Document intelligence schemas
# ---------------------------------------------------------------------------


class DocumentUploadResponse(BaseModel):
    """Response after a document has been ingested into the RAG pipeline."""

    doc_id: str = Field(..., description="Unique identifier assigned to the document")
    filename: str = Field(..., description="Original uploaded filename")
    chunks_indexed: int = Field(
        ..., description="Number of text chunks indexed into ChromaDB"
    )
    status: str = Field(..., description="'INDEXED' or 'ERROR'")


class DocumentQueryRequest(BaseModel):
    """Request body for RAG-powered document query."""

    query: str = Field(
        ...,
        description="Natural-language question to answer using uploaded documents",
        min_length=3,
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of top document chunks to retrieve",
    )
    selected_versions: Optional[List[str]] = Field(
        default=None,
        description="Filter results to specific guideline version labels (e.g. ['CBPR+ R2025'])",
    )
    cross_version_compare: bool = Field(
        default=False,
        description="If True and multiple selected_versions provided, run per-version queries and compare",
    )


class DocumentQueryResponse(BaseModel):
    """Response from a RAG-powered document query."""

    answer: str = Field(..., description="LLM-synthesised answer from retrieved chunks")
    sources: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of source chunk metadata dicts (doc_id, filename, page_num, chunk_index)",
    )
    audit_id: str = Field(..., description="Immutable audit log entry identifier")


# ---------------------------------------------------------------------------
# Audit log schemas
# ---------------------------------------------------------------------------


class AuditLogEntry(BaseModel):
    """Single tamper-evident audit log entry."""

    audit_id: str = Field(..., description="UUID4 identifier for this audit entry")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the event")
    event_type: str = Field(
        ...,
        description="e.g. TRANSLATION, VALIDATION, LEARN_QUERY, DOCUMENT_UPLOAD",
    )
    module: str = Field(
        ..., description="Originating module (e.g. 'translate', 'learn', 'documents')"
    )
    status: str = Field(..., description="'SUCCESS', 'ERROR', 'PARTIAL'")
    uetr: Optional[str] = Field(
        default=None, description="UETR if the event relates to a payment message"
    )
    message_type: Optional[str] = Field(
        default=None,
        description="ISO 20022 or MT message type if applicable",
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional PII-masked event details",
    )
    hash: str = Field(
        ..., description="SHA-256 hash chained from the previous entry's hash"
    )


class AuditLogsResponse(BaseModel):
    """Paginated list of audit log entries."""

    total: int = Field(..., description="Total number of matching log entries")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of entries per page")
    entries: List[AuditLogEntry] = Field(
        default_factory=list, description="Audit log entries for this page"
    )


# ---------------------------------------------------------------------------
# Telemetry schemas
# ---------------------------------------------------------------------------


class TelemetryEvent(BaseModel):
    """Real-time telemetry event broadcast over WebSocket."""

    event_id: str = Field(..., description="Unique identifier for this telemetry event")
    timestamp: str = Field(..., description="ISO 8601 timestamp of the event")
    event_type: str = Field(
        ...,
        description="e.g. TRANSLATION_COMPLETE, VALIDATION_ERROR, DOCUMENT_INDEXED",
    )
    module: int = Field(
        ...,
        description=(
            "Numeric module code: 1=Translate, 2=Learn, 3=Documents, 4=Audit"
        ),
    )
    severity: str = Field(
        ...,
        description="'INFO', 'WARN', 'ERROR'",
    )
    summary: str = Field(..., description="Short human-readable event summary")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Additional structured event data"
    )


# ---------------------------------------------------------------------------
# Health check schemas
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response from the /health endpoint."""

    status: str = Field(..., description="'healthy' or 'degraded'")
    version: str = Field(..., description="API semantic version string")
    modules: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Per-module health status dict with keys: "
            "translate, learn, documents, audit, telemetry"
        ),
    )
