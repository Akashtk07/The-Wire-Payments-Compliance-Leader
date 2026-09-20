"""
Documents router — multi-format document upload, RAG indexing, and querying.

Endpoints:
  POST /api/v1/documents/upload  — Upload and index a compliance document
  POST /api/v1/documents/query   — RAG-powered document Q&A
  GET  /api/v1/documents/list    — List indexed documents
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import aiofiles
import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    DocumentUploadResponse,
)
from services.audit_logger import audit_logger
from services.auth_service import User, get_current_user
from services.rag_pipeline import rag_pipeline
from services.telemetry_bus import TelemetryBus, telemetry_bus

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Document Intelligence"])

# Supported upload file extensions
_ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".docx", ".txt", ".xml"}


def _validate_extension(filename: str) -> str:
    """Return the lowercased extension or raise HTTPException if unsupported."""
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "error": "UNSUPPORTED_FILE_TYPE",
                "message": f"File extension '{ext}' is not supported.",
                "allowed": sorted(_ALLOWED_EXTENSIONS),
            },
        )
    return ext


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------


@router.post(
    "/documents/upload",
    response_model=DocumentUploadResponse,
    summary="Upload and index a compliance document",
)
async def upload_document(
    file: UploadFile,
    guideline_version: str = Form(default="Unclassified"),
    guideline_category: str = Form(default="Custom"),
    tags: str = Form(default=""),
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Accepts a multipart file upload (PDF, PPTX, DOCX, TXT, XML),
    saves it to the upload directory, and indexes it into the RAG pipeline.
    """
    filename = file.filename or "unknown"
    _validate_extension(filename)

    doc_id = str(uuid.uuid4())
    upload_dir = Path(settings.UPLOAD_DIR)
    upload_dir.mkdir(parents=True, exist_ok=True)

    safe_filename = f"{doc_id}_{filename}"
    save_path = upload_dir / safe_filename

    # Stream-save the uploaded file
    try:
        async with aiofiles.open(save_path, "wb") as out_file:
            while chunk := await file.read(1024 * 64):  # 64 KB chunks
                await out_file.write(chunk)
    except Exception as exc:
        log.exception("document_save_failed", filename=filename, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "FILE_SAVE_ERROR", "message": str(exc)},
        )
    finally:
        await file.close()

    # Ingest into RAG pipeline
    try:
        chunks_indexed = await rag_pipeline.ingest(
            file_path=str(save_path),
            filename=filename,
            doc_id=doc_id,
            guideline_version=guideline_version,
            guideline_category=guideline_category,
            tags=tags,
        )
        upload_status = "INDEXED"
    except Exception as exc:
        log.exception("rag_ingest_failed", filename=filename, error=str(exc))
        chunks_indexed = 0
        upload_status = "ERROR"

    # Audit log
    audit_id = await audit_logger.log(
        event_type="DOCUMENT_UPLOAD",
        module="documents",
        status=upload_status,
        details={
            "filename": filename,
            "doc_id": doc_id,
            "chunks_indexed": chunks_indexed,
            "save_path": str(save_path),
            "guideline_version": guideline_version,
            "guideline_category": guideline_category,
            "uploaded_by": current_user.username,
        },
    )

    # Telemetry broadcast
    event = TelemetryBus.make_event(
        event_type="DOCUMENT_INDEXED",
        module=3,
        severity="INFO" if upload_status == "INDEXED" else "ERROR",
        summary=f"Document '{filename}' indexed: {chunks_indexed} chunks",
        data={"doc_id": doc_id, "audit_id": audit_id, "chunks_indexed": chunks_indexed},
    )
    await telemetry_bus.broadcast(event)

    return DocumentUploadResponse(
        doc_id=doc_id,
        filename=filename,
        chunks_indexed=chunks_indexed,
        status=upload_status,
    )


# ---------------------------------------------------------------------------
# POST /documents/query
# ---------------------------------------------------------------------------


@router.post(
    "/documents/query",
    response_model=DocumentQueryResponse,
    summary="Query indexed documents using natural language",
)
async def query_documents(
    body: DocumentQueryRequest,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Embeds the query, retrieves top-k relevant document chunks from ChromaDB,
    and uses the LLM to synthesise an answer grounded in the retrieved content.
    """
    log.info("document_query", query_preview=body.query[:80], top_k=body.top_k)

    try:
        answer, sources = await rag_pipeline.query(
            body.query,
            body.top_k,
            version_filter=body.selected_versions if hasattr(body, 'selected_versions') else None,
        )
    except Exception as exc:
        log.exception("document_query_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "RAG_QUERY_ERROR", "message": str(exc)},
        )

    audit_id = await audit_logger.log(
        event_type="DOCUMENT_QUERY",
        module="documents",
        status="SUCCESS",
        details={
            "query": body.query[:200],
            "top_k": body.top_k,
            "sources_returned": len(sources),
        },
    )

    event = TelemetryBus.make_event(
        event_type="DOCUMENT_QUERY_COMPLETE",
        module=3,
        severity="INFO",
        summary=f"RAG query answered with {len(sources)} sources",
        data={"audit_id": audit_id, "sources_count": len(sources)},
    )
    await telemetry_bus.broadcast(event)

    return DocumentQueryResponse(
        answer=answer,
        sources=sources,
        audit_id=audit_id,
    )


# ---------------------------------------------------------------------------
# GET /documents/list
# ---------------------------------------------------------------------------


@router.get(
    "/documents/list",
    summary="List all indexed documents",
)
async def list_documents(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns a list of all documents currently indexed in the ChromaDB collection,
    with their doc_id, filename, and total chunk count.
    """
    try:
        docs = await rag_pipeline.list_documents()
    except Exception as exc:
        log.exception("list_documents_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "LIST_DOCUMENTS_ERROR", "message": str(exc)},
        )

    return {
        "total": len(docs),
        "documents": docs,
    }


# ---------------------------------------------------------------------------
# DELETE /documents/{doc_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/documents/{doc_id}",
    summary="Delete a document and its chunks from the RAG index",
)
async def delete_document_endpoint(
    doc_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Removes all vector chunks associated with the given doc_id from ChromaDB.
    """
    try:
        deleted_count = await rag_pipeline.delete_document(doc_id)
    except Exception as exc:
        log.exception("delete_document_failed", doc_id=doc_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "DELETE_DOCUMENT_ERROR", "message": str(exc)},
        )

    audit_id = await audit_logger.log(
        event_type="DOCUMENT_DELETE",
        module="documents",
        status="SUCCESS",
        details={"doc_id": doc_id, "chunks_removed": deleted_count},
    )

    event = TelemetryBus.make_event(
        event_type="DOCUMENT_DELETED",
        module=3,
        severity="INFO",
        summary=f"Document {doc_id} deleted ({deleted_count} chunks removed)",
        data={"doc_id": doc_id, "audit_id": audit_id},
    )
    await telemetry_bus.broadcast(event)

    return {
        "status": "DELETED",
        "doc_id": doc_id,
        "chunks_removed": deleted_count,
        "audit_id": audit_id,
    }
