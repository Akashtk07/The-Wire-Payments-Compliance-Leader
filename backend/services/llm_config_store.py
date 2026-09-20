"""
Runtime LLM Configuration Store.

Holds the currently active provider, model and API key in memory.
Changes take effect immediately for all subsequent LLM queries.
Persists a rolling history of the last 25 configuration changes.
"""

from __future__ import annotations

import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

# ---------------------------------------------------------------------------
# Supported providers and their available models
# ---------------------------------------------------------------------------

PROVIDER_MODELS: Dict[str, List[Dict[str, str]]] = {
    "gemini": [
        # Current stable models as of Sep 2026
        {"id": "gemini-2.0-flash",              "label": "Gemini 2.0 Flash (Current Default)"},
        {"id": "gemini-2.5-flash",              "label": "Gemini 2.5 Flash"},
        {"id": "gemini-3.5-flash",              "label": "Gemini 3.5 Flash (Latest Stable)"},
        {"id": "gemini-3.8-flash",              "label": "Gemini 3.8 Flash (Frontier)"},
        {"id": "gemini-3.5-flash-lite",         "label": "Gemini 3.5 Flash-Lite (High Volume)"},
    ],
    "groq": [
        # Current active Groq models — checked Sep 2026
        # Note: llama3-70b-8192 and llama3-8b-8192 are DECOMMISSIONED
        {"id": "llama-3.3-70b-versatile",       "label": "Llama 3.3 70B Versatile (Recommended)"},
        {"id": "llama-3.1-8b-instant",          "label": "Llama 3.1 8B Instant (Fast)"},
        {"id": "meta-llama/llama-4-scout-17b-16e-instruct", "label": "Llama 4 Scout 17B (Newest)"},
        {"id": "openai/gpt-oss-120b",           "label": "OpenAI GPT-OSS 120B (via Groq)"},
        {"id": "openai/gpt-oss-20b",            "label": "OpenAI GPT-OSS 20B (via Groq)"},
        {"id": "gemma2-9b-it",                  "label": "Gemma 2 9B Instruct"},
    ],
    "openai": [
        {"id": "gpt-4o",           "label": "GPT-4o (Recommended)"},
        {"id": "gpt-4o-mini",      "label": "GPT-4o Mini"},
        {"id": "gpt-4-turbo",      "label": "GPT-4 Turbo"},
        {"id": "gpt-3.5-turbo",    "label": "GPT-3.5 Turbo"},
    ],
    "ollama": [
        {"id": "llama3",       "label": "Llama 3 (8B)"},
        {"id": "llama3.1",     "label": "Llama 3.1 (8B)"},
        {"id": "llama3:70b",   "label": "Llama 3 (70B)"},
        {"id": "mistral",      "label": "Mistral 7B"},
        {"id": "codellama",    "label": "Code Llama"},
        {"id": "custom",       "label": "Custom (specify model name)"},
    ],
}

HISTORY_LIMIT = 25


# ---------------------------------------------------------------------------
# Config entry dataclass (plain dict for simplicity / JSON serialisability)
# ---------------------------------------------------------------------------

def _make_history_entry(
    provider: str,
    model: str,
    api_key: Optional[str],
    changed_by: str = "frontend",
) -> dict:
    masked_key = None
    if api_key:
        masked_key = f"{api_key[:8]}{'*' * max(0, len(api_key) - 12)}{api_key[-4:]}"
    return {
        "change_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider": provider,
        "model": model,
        "api_key_preview": masked_key,
        "changed_by": changed_by,
    }


# ---------------------------------------------------------------------------
# Runtime config store (singleton)
# ---------------------------------------------------------------------------

class LLMConfigStore:
    """In-memory runtime LLM configuration with rolling change history."""

    def __init__(self) -> None:
        # Current active config — initialised from settings at startup
        self._provider: str = "gemini"
        self._model: str = "gemini-2.0-flash"
        self._api_keys: Dict[str, Optional[str]] = {
            "gemini": None,
            "groq": None,
            "openai": None,
            "ollama": None,
        }
        self._ollama_base_url: str = "http://localhost:11434"
        self._history: Deque[dict] = deque(maxlen=HISTORY_LIMIT)

    # ------------------------------------------------------------------
    # Initialise from pydantic settings (called at startup)
    # ------------------------------------------------------------------

    def init_from_settings(self, settings) -> None:  # type: ignore[type-arg]
        self._provider = settings.LLM_PROVIDER.lower()
        self._model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")
        self._api_keys["gemini"] = settings.GEMINI_API_KEY
        self._api_keys["openai"] = settings.OPENAI_API_KEY
        self._api_keys["groq"]   = getattr(settings, "GROQ_API_KEY", None)
        self._ollama_base_url = settings.OLLAMA_BASE_URL

        # Adjust default model for provider
        if self._provider == "openai":
            self._model = getattr(settings, "OPENAI_MODEL", "gpt-4o")
        elif self._provider == "groq":
            self._model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")
        elif self._provider == "ollama":
            self._model = getattr(settings, "OLLAMA_MODEL", "llama3")

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def model(self) -> str:
        return self._model

    @property
    def ollama_base_url(self) -> str:
        return self._ollama_base_url

    def get_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        return self._api_keys.get(provider or self._provider)

    def get_current_config(self) -> dict:
        key = self.get_api_key()
        masked = None
        if key:
            masked = f"{key[:8]}{'*' * max(0, len(key) - 12)}{key[-4:]}"
        return {
            "provider": self._provider,
            "model": self._model,
            "api_key_preview": masked,
            "api_key_set": bool(key),
            "ollama_base_url": self._ollama_base_url,
            "available_providers": list(PROVIDER_MODELS.keys()),
            "available_models": PROVIDER_MODELS.get(self._provider, []),
        }

    def get_history(self) -> List[dict]:
        return list(reversed(self._history))  # Most recent first

    def get_all_models(self) -> Dict[str, List[Dict[str, str]]]:
        return PROVIDER_MODELS

    # ------------------------------------------------------------------
    # Update config
    # ------------------------------------------------------------------

    def update(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        ollama_base_url: Optional[str] = None,
        changed_by: str = "frontend",
    ) -> dict:
        """Apply a config change and record it in history. Returns new config."""
        if provider is not None:
            provider = provider.lower()
            if provider not in PROVIDER_MODELS:
                raise ValueError(f"Unknown provider '{provider}'. Valid: {list(PROVIDER_MODELS)}")
            self._provider = provider
            # Auto-select first model if model not specified or wrong provider
            if model is None or not any(m["id"] == model for m in PROVIDER_MODELS[provider]):
                model = PROVIDER_MODELS[provider][0]["id"]

        if model is not None:
            self._model = model

        if api_key is not None and api_key.strip():
            self._api_keys[self._provider] = api_key.strip()

        if ollama_base_url is not None:
            self._ollama_base_url = ollama_base_url.strip()

        entry = _make_history_entry(
            provider=self._provider,
            model=self._model,
            api_key=self.get_api_key(),
            changed_by=changed_by,
        )
        self._history.append(entry)
        return self.get_current_config()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

llm_config_store = LLMConfigStore()
