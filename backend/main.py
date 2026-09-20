"""
The Compliance Leader API — main FastAPI application entry point.

Architecture:
  - Lifespan context manager: directory creation, service initialisation, startup audit log
  - CORS configured from FRONTEND_ORIGIN env var + localhost:3000
  - All business routers mounted under /api/v1
  - WebSocket telemetry mounted at /ws/telemetry
  - Global exception handler returns structured JSON (no stack traces)
  - /health endpoint with per-module status checks
"""

from __future__ import annotations

import os
import traceback
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Dict

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import settings
from models.schemas import HealthResponse
from routers.admin import router as admin_router
from routers.auth import router as auth_router
from routers.audit import router as audit_router
from routers.audit import ws_router
from routers.documents import router as documents_router
from routers.guidelines import router as guidelines_router
from routers.learn import router as learn_router
from routers.llm_config import router as llm_config_router
from routers.mx_translate import router as mx_translate_router
from routers.prompt_engineering import router as prompt_engineering_router
from routers.translate import router as translate_router
from services.audit_logger import audit_logger
from services.auth_service import init_db
from services.guideline_registry import GuidelineVersion, seed_guideline_versions
from services.llm_config_store import llm_config_store
from services.rag_pipeline import rag_pipeline
from services.telemetry_bus import telemetry_bus

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Structlog configuration
# ---------------------------------------------------------------------------


def _add_logger_name(logger, method_name, event_dict):
    """Safe logger-name injector that works with both PrintLogger and stdlib logging."""
    record = event_dict.get("_record")
    if record is not None:
        event_dict["logger"] = record.name
    elif hasattr(logger, "name"):
        event_dict["logger"] = logger.name
    elif hasattr(logger, "_logger") and hasattr(logger._logger, "name"):
        event_dict["logger"] = logger._logger.name
    # If none of the above, omit the key silently (no crash)
    return event_dict


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        _add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup → yield → shutdown."""

    # --- Startup ---
    log.info("compliance_leader_startup", version=settings.APP_VERSION)

    # Initialise database & seed default data
    try:
        init_db()
        seed_guideline_versions()
    except Exception as exc:
        log.error("db_init_failed", error=str(exc))

    # Initialise runtime LLM config store from .env / pydantic settings
    llm_config_store.init_from_settings(settings)
    log.info(
        "llm_config_store_initialised",
        provider=llm_config_store.provider,
        model=llm_config_store.model,
        api_key_set=bool(llm_config_store.get_api_key()),
    )

    # --- LLM config diagnostic (visible in console at startup) ---
    _api_key_set = bool(settings.GEMINI_API_KEY)
    _model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
    log.info(
        "llm_config",
        provider=settings.LLM_PROVIDER,
        model=_model,
        gemini_api_key_loaded=_api_key_set,
        gemini_api_key_preview=(
            f"{settings.GEMINI_API_KEY[:8]}..." if _api_key_set else "NOT SET"
        ),
    )
    if not _api_key_set:
        log.warning(
            "gemini_api_key_missing",
            hint="Set GEMINI_API_KEY in d:\\WirePaymentAssistance\\.env and restart uvicorn",
        )

    # Create data directories
    dirs = [
        settings.AUDIT_DIR,
        settings.UPLOAD_DIR,
        settings.XSD_DIR,
        settings.CHROMA_PERSIST_DIR,
    ]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        log.debug("directory_ensured", path=d)

    # Log startup audit event
    try:
        await audit_logger.log(
            event_type="SYSTEM_STARTUP",
            module="system",
            status="SUCCESS",
            details={
                "version": settings.APP_VERSION,
                "llm_provider": settings.LLM_PROVIDER,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as exc:
        log.error("startup_audit_failed", error=str(exc))

    log.info("compliance_leader_ready", host=settings.HOST, port=settings.PORT)

    yield

    # --- Shutdown ---
    log.info("compliance_leader_shutdown")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_TITLE,
        version=settings.APP_VERSION,
        description=(
            "Enterprise-grade ISO 20022 / SWIFT MT translation, validation, "
            "domain learning, and multi-format document intelligence platform. "
            "All operations are immutably audited with a tamper-evident SHA-256 chain."
        ),
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(translate_router, prefix="/api/v1")
    app.include_router(mx_translate_router, prefix="/api/v1")
    app.include_router(prompt_engineering_router, prefix="/api/v1")
    app.include_router(learn_router, prefix="/api/v1")
    app.include_router(documents_router, prefix="/api/v1")
    app.include_router(audit_router, prefix="/api/v1")
    app.include_router(llm_config_router, prefix="/api/v1")
    app.include_router(guidelines_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(ws_router)  # WebSocket router (no /api/v1 prefix)

    # --- Global exception handler ---
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled_exception",
            path=str(request.url),
            method=request.method,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        # Never expose stack traces in API responses
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please check the audit log for details.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # --- Health endpoint ---
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="Platform health check",
    )
    async def health_check() -> HealthResponse:
        """
        Returns the health status of the API and all sub-modules.
        """
        module_status: Dict[str, Any] = {}

        # Translation module
        try:
            from services.mt_parser import SAMPLE_MT103, mt_parser
            _ = mt_parser.parse(SAMPLE_MT103, "MT103")
            module_status["translate"] = {"status": "healthy", "detail": "MT parser operational"}
        except Exception as exc:
            module_status["translate"] = {"status": "degraded", "detail": str(exc)}

        # Validator module
        try:
            from services.validator import iso20022_validator
            module_status["validate"] = {"status": "healthy", "detail": "ISO 20022 validator operational"}
        except Exception as exc:
            module_status["validate"] = {"status": "degraded", "detail": str(exc)}

        # LLM router (reads from runtime config store)
        try:
            provider = llm_config_store.provider
            model = llm_config_store.model
            has_key = bool(llm_config_store.get_api_key()) or provider == "ollama"
            module_status["learn"] = {
                "status": "healthy",
                "detail": f"{provider}/{model}",
                "api_key_configured": has_key,
                "mock_mode": not has_key,
            }
        except Exception as exc:
            module_status["learn"] = {"status": "degraded", "detail": str(exc)}

        # RAG / ChromaDB
        try:
            from services.rag_pipeline import _get_collection
            col = _get_collection()
            doc_count = col.count()
            module_status["documents"] = {
                "status": "healthy",
                "detail": f"ChromaDB operational, {doc_count} chunks indexed",
            }
        except Exception as exc:
            module_status["documents"] = {"status": "degraded", "detail": str(exc)}

        # Audit logger
        try:
            audit_path = Path(settings.AUDIT_DIR)
            module_status["audit"] = {
                "status": "healthy" if audit_path.exists() else "degraded",
                "detail": f"Audit dir: {settings.AUDIT_DIR}",
            }
        except Exception as exc:
            module_status["audit"] = {"status": "degraded", "detail": str(exc)}

        # MX → MT Reverse Translator
        try:
            from services.mx_parser import mx_parser
            from services.mt_builder import mt_builder
            module_status["mx_translate"] = {
                "status": "healthy",
                "detail": "MX parser + MT builder operational (CBPR+/LYNX)",
            }
        except Exception as exc:
            module_status["mx_translate"] = {"status": "degraded", "detail": str(exc)}

        # Prompt Engineering module
        try:
            from routers.prompt_engineering import PROMPT_TOPICS
            module_status["prompt_engineering"] = {
                "status": "healthy",
                "detail": f"{len(PROMPT_TOPICS)} topics available",
            }
        except Exception as exc:
            module_status["prompt_engineering"] = {"status": "degraded", "detail": str(exc)}

        # Telemetry bus
        module_status["telemetry"] = {
            "status": "healthy",
            "detail": f"WebSocket clients connected: {len(telemetry_bus._clients)}",
        }

        overall = (
            "healthy"
            if all(m.get("status") == "healthy" for m in module_status.values())
            else "degraded"
        )

        return HealthResponse(
            status=overall,
            version=settings.APP_VERSION,
            modules=module_status,
        )

    return app


app = create_app()
