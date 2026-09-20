"""
LLM Configuration router.

Endpoints:
  GET  /api/v1/llm-config              — Get current active config (key masked)
  POST /api/v1/llm-config              — Update provider / model / API key live
  GET  /api/v1/llm-config/history      — Last 25 config changes
  GET  /api/v1/llm-config/models       — All providers and their model lists
  POST /api/v1/llm-config/test         — Test current config with a ping query
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from services.llm_config_store import PROVIDER_MODELS, llm_config_store

log = structlog.get_logger(__name__)

router = APIRouter(tags=["LLM Configuration"])


# ---------------------------------------------------------------------------
# Request / response schemas (local — not in main schemas.py)
# ---------------------------------------------------------------------------


class LLMConfigUpdateRequest(BaseModel):
    provider: Optional[str] = Field(
        default=None,
        description="Provider: gemini | groq | openai | ollama",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model ID (must be valid for the selected provider)",
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for the selected provider (sent over HTTPS only)",
    )
    ollama_base_url: Optional[str] = Field(
        default=None,
        description="Ollama server URL (only for ollama provider)",
    )


# ---------------------------------------------------------------------------
# GET /llm-config
# ---------------------------------------------------------------------------


@router.get(
    "/llm-config",
    summary="Get current active LLM configuration",
)
async def get_llm_config() -> Dict[str, Any]:
    """Returns the current provider, model, and masked API key."""
    return llm_config_store.get_current_config()


# ---------------------------------------------------------------------------
# POST /llm-config
# ---------------------------------------------------------------------------


@router.post(
    "/llm-config",
    summary="Update LLM provider / model / API key at runtime",
)
async def update_llm_config(body: LLMConfigUpdateRequest) -> Dict[str, Any]:
    """
    Applies a new LLM configuration immediately. Changes take effect for all
    subsequent queries without restarting the server.
    """
    try:
        new_config = llm_config_store.update(
            provider=body.provider,
            model=body.model,
            api_key=body.api_key,
            ollama_base_url=body.ollama_base_url,
            changed_by="frontend",
        )
        log.info(
            "llm_config_updated",
            provider=new_config["provider"],
            model=new_config["model"],
            api_key_set=new_config["api_key_set"],
        )
        return {"status": "ok", "config": new_config}
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "INVALID_CONFIG", "message": str(exc)},
        )


# ---------------------------------------------------------------------------
# GET /llm-config/history
# ---------------------------------------------------------------------------


@router.get(
    "/llm-config/history",
    summary="Get history of last 25 LLM configuration changes",
)
async def get_llm_config_history() -> Dict[str, Any]:
    """Returns the rolling history of config changes (most recent first)."""
    history = llm_config_store.get_history()
    return {"total": len(history), "history": history}


# ---------------------------------------------------------------------------
# GET /llm-config/models
# ---------------------------------------------------------------------------


@router.get(
    "/llm-config/models",
    summary="Get all supported providers and their model lists",
)
async def get_llm_models() -> Dict[str, Any]:
    """Returns the full catalogue of providers and available models."""
    return {"providers": PROVIDER_MODELS}


# ---------------------------------------------------------------------------
# POST /llm-config/test
# ---------------------------------------------------------------------------


@router.post(
    "/llm-config/test",
    summary="Test current LLM configuration with a lightweight ping",
)
async def test_llm_config() -> Dict[str, Any]:
    """
    Sends a minimal test query to the currently configured LLM.
    Returns success/error to validate the API key and model before use.
    """
    provider = llm_config_store.provider
    model = llm_config_store.model
    api_key = llm_config_store.get_api_key()

    if provider in ("gemini", "groq", "openai") and not api_key:
        return {
            "status": "error",
            "provider": provider,
            "model": model,
            "message": f"No API key configured for {provider}. Set one in LLM Config.",
        }

    test_prompt = "Reply with exactly: COMPLIANCE_LEADER_OK"

    try:
        if provider == "gemini":
            url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{model}:generateContent?key={api_key}"
            )
            payload = {
                "contents": [{"role": "user", "parts": [{"text": test_prompt}]}],
                "generationConfig": {"maxOutputTokens": 32},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return {"status": "error", "provider": provider, "model": model,
                        "message": f"API error {resp.status_code}: {resp.text[:200]}"}
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]

        elif provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": test_prompt}],
                "max_tokens": 32,
            }
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return {"status": "error", "provider": provider, "model": model,
                        "message": f"API error {resp.status_code}: {resp.text[:200]}"}
            text = resp.json()["choices"][0]["message"]["content"]

        elif provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": test_prompt}],
                "max_tokens": 32,
            }
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"Authorization": f"Bearer {api_key}"},
            ) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return {"status": "error", "provider": provider, "model": model,
                        "message": f"API error {resp.status_code}: {resp.text[:200]}"}
            text = resp.json()["choices"][0]["message"]["content"]

        elif provider == "ollama":
            url = f"{llm_config_store.ollama_base_url}/api/generate"
            payload = {"model": model, "prompt": test_prompt, "stream": False}
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                return {"status": "error", "provider": provider, "model": model,
                        "message": f"Ollama error {resp.status_code}: {resp.text[:200]}"}
            text = resp.json().get("response", "")

        else:
            return {"status": "error", "message": f"Unknown provider: {provider}"}

        return {
            "status": "ok",
            "provider": provider,
            "model": model,
            "response_preview": text[:100].strip(),
            "message": "API key and model verified successfully.",
        }

    except Exception as exc:
        return {
            "status": "error",
            "provider": provider,
            "model": model,
            "message": str(exc)[:300],
        }
