"""
LLM Router — multi-provider financial domain query service.

Reads the currently active config from llm_config_store (set at startup from
env vars, then overrideable at runtime via the /api/v1/llm-config endpoint).

Providers: gemini | groq | openai | ollama
Implements retry with exponential backoff (3 attempts).
Falls back gracefully to a diagnostic mock if no API key is configured.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import httpx
import structlog

from services.llm_config_store import llm_config_store

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Financial domain system prompt
# ---------------------------------------------------------------------------

FINANCIAL_SYSTEM_PROMPT = (
    "You are an expert financial systems educator specializing in ISO 20022, "
    "SWIFT messaging, global clearing and settlement, and cross-border payment law. "
    "You provide precise, structured, zero-fluff explanations to compliance officers, "
    "payment engineers, and financial analysts. "
    "IMPORTANT: The current authoritative standard is SWIFT CBPR+ R2025. "
    "As of November 22, 2025 the coexistence period ended: MT103, MT202, MT202 COV "
    "are retired from SWIFT FINplus and MUST be translated to ISO 20022 pacs.008 / pacs.009. "
    "CBPR+ R2025 key rules you must always apply: "
    "(1) PmtTpInf/SvcLvl/Cd = 'SDVA' is mandatory for same-day value. "
    "(2) PostalAddress: TownName and Country are mandatory in all structured or hybrid "
    "addresses; fully unstructured free-text-only address is deprecated (forbidden from Nov 2026). "
    "(3) UETR (UUID4) is mandatory in PmtId/UETR in every pacs message. "
    "(4) ChrgBr must be SHAR for pacs.008 under CBPR+ (never DEBT or CRED in interbank). "
    "(5) LEI is optional at CBPR+ network level but may be locally mandated. "
    "When explaining message fields, always reference the exact XML element path. "
    "When explaining flows, describe the full settlement chain. "
    "Always clearly flag R2025 vs R2024 differences when they are relevant to the question. "
    "Always distinguish between MT (legacy SWIFT) and MX (ISO 20022) concepts clearly."
)


def _build_system_prompt(version_context: Optional[List[str]] = None) -> str:
    """Build a system prompt with optional version-awareness instructions."""
    base = FINANCIAL_SYSTEM_PROMPT
    if version_context and len(version_context) > 0:
        versions_str = ", ".join(version_context)
        base += (
            f" The user is working with the following guideline version(s): {versions_str}. "
            "When answering, always specify which version a rule or requirement applies to. "
            "If answering about multiple versions, clearly note differences using: "
            "'\u26a0\ufe0f Changed in [VERSION]: ...' format for any rule that changed between versions. "
            "Reference the most recent selected version as the authoritative source. "
            "If CBPR+ R2025 is among the selected versions, apply R2025 rules with full strictness: "
            "structured/hybrid PostalAddress with mandatory TownName+Country, mandatory UETR, "
            "SHAR ChrgBr for interbank, and rejection of pure free-text addresses."
        )
    return base

# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

async def _retry_async(coro_fn, max_attempts: int = 3, base_delay: float = 1.0):
    """Call *coro_fn()* up to *max_attempts* times with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                wait = base_delay * (2 ** attempt)
                log.warning(
                    "llm_retry",
                    attempt=attempt + 1,
                    wait_seconds=wait,
                    error=str(exc),
                )
                await asyncio.sleep(wait)
    raise last_exc  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Mock fallback
# ---------------------------------------------------------------------------

_MOCK_SNIPPETS = {
    "pacs.008": (
        "pacs.008.001.08 (FI-to-FI Customer Credit Transfer) is the ISO 20022 "
        "equivalent of the SWIFT MT103. It carries the full chain: <DbtrAgt> "
        "(ordering bank BIC), <Dbtr> (ordering customer with IBAN in "
        "<DbtrAcct><Id><IBAN>), <CdtrAgt> (beneficiary bank BIC), and <Cdtr> "
        "(beneficiary customer). The <IntrBkSttlmAmt> element holds the interbank "
        "settlement amount and currency, while <InstdAmt> optionally carries the "
        "original instructed amount in case of FX conversion."
    ),
    "pacs.009": (
        "pacs.009.001.08 (FI-to-FI Credit Transfer) is the ISO 20022 equivalent of "
        "the SWIFT MT202/MT202COV. In CORE variant, only financial institution "
        "counterparties appear (<InstgAgt>, <InstdAgt>, <Cdtr>). In COV variant, "
        "the <UndrlygCstmrCdtTrf> block carries the underlying retail customer "
        "credit transfer details, including <Dbtr> and <Cdtr> of the original "
        "pacs.008 transaction."
    ),
    "pacs.004": (
        "pacs.004.001.09 is the ISO 20022 Payment Return message, equivalent to "
        "SWIFT MT103 return flows. It must always reference the original transaction "
        "via <OrgnlUETR> and <OrgnlMsgId>, and include a return reason in "
        "<Rsn><Cd> using external codes such as AM09 (wrong amount), AGNT (agent "
        "decision), DUPL (duplicate), UPAY (undue payment), or CUST (customer "
        "request)."
    ),
    "uetr": (
        "The UETR (Unique End-to-end Transaction Reference) is a UUID4 identifier "
        "mandated by SWIFT gpi (global payments innovation) since 2018. It appears "
        "in SWIFT MT messages in block 3 field {121:} and in ISO 20022 messages "
        "in <PmtId><UETR>. Every bank in the payment chain must preserve it "
        "unchanged, enabling end-to-end tracking via the SWIFT gpi Tracker."
    ),
    "nostro": (
        "A Nostro account is an account that Bank A holds at Bank B in Bank B's "
        "domestic currency (e.g., HSBC's USD account at JP Morgan Chase). "
        "Conversely, Bank B views the same account as a Vostro account. "
        "In correspondent banking, debits/credits to Nostro accounts represent "
        "the actual movement of funds across the settlement chain."
    ),
}


def _mock_response(query: str, reason: str = "No API key configured") -> str:
    """Return a domain-relevant mock response based on keywords in the query."""
    q_lower = query.lower()
    for keyword, snippet in _MOCK_SNIPPETS.items():
        if keyword.lower() in q_lower:
            return snippet
    return (
        f"[MOCK MODE — {reason}] "
        f"Your query '{query[:100]}' relates to ISO 20022 / SWIFT financial messaging. "
        "Configure an API key in the ⚙ LLM Config panel (top-right of sidebar) "
        "to receive real expert answers from the AI model."
    )


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------

async def _query_gemini(
    user_message: str,
    context: Optional[str],
    api_key: str,
    model: str,
    version_context: Optional[List[str]] = None,
) -> str:
    """Call Gemini via the REST API (v1beta) using httpx."""
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    user_text = user_message
    if context:
        user_text = f"Context from compliance documents:\n{context}\n\nQuestion:\n{user_message}"

    payload = {
        "system_instruction": {"parts": [{"text": _build_system_prompt(version_context)}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }

    async def _call() -> str:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Unexpected Gemini response structure: {data}") from exc

    return await _retry_async(_call)


async def _query_groq(
    user_message: str,
    context: Optional[str],
    api_key: str,
    model: str,
    version_context: Optional[List[str]] = None,
) -> str:
    """Call Groq via their OpenAI-compatible REST API."""
    user_text = user_message
    if context:
        user_text = f"Context from compliance documents:\n{context}\n\nQuestion:\n{user_message}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _build_system_prompt(version_context)},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }

    async def _call() -> str:
        async with httpx.AsyncClient(
            timeout=60.0,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        ) as client:
            resp = await client.post("https://api.groq.com/openai/v1/chat/completions", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Unexpected Groq response structure: {data}") from exc

    return await _retry_async(_call)


async def _query_openai(
    user_message: str,
    context: Optional[str],
    api_key: str,
    model: str,
    version_context: Optional[List[str]] = None,
) -> str:
    """Call OpenAI chat completions API."""
    user_text = user_message
    if context:
        user_text = f"Context from compliance documents:\n{context}\n\nQuestion:\n{user_message}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _build_system_prompt(version_context)},
            {"role": "user", "content": user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }

    async def _call() -> str:
        async with httpx.AsyncClient(
            timeout=60.0,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        ) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as exc:
                raise RuntimeError(f"Unexpected OpenAI response structure: {data}") from exc

    return await _retry_async(_call)


async def _query_ollama(user_message: str, context: Optional[str], base_url: str, model: str) -> str:
    """Call local Ollama instance."""
    user_text = user_message
    if context:
        user_text = f"Context from compliance documents:\n{context}\n\nQuestion:\n{user_message}"

    full_prompt = f"{FINANCIAL_SYSTEM_PROMPT}\n\n{user_text}"
    payload = {"model": model, "prompt": full_prompt, "stream": False}

    async def _call() -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{base_url}/api/generate", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text[:300]}")
            return resp.json().get("response", "")

    return await _retry_async(_call)


# ---------------------------------------------------------------------------
# LLM Router class — reads from runtime config store
# ---------------------------------------------------------------------------

class LLMRouter:
    """Routes LLM queries to the currently configured provider."""

    async def query(
        self,
        user_message: str,
        context: Optional[str] = None,
        version_context: Optional[List[str]] = None,
    ) -> str:
        """
        Send *user_message* to the active LLM provider.
        Reads provider/model/key from the runtime llm_config_store.
        Falls back to informative mock if no API key is set.
        version_context: list of guideline version labels to inject into system prompt.
        """
        provider = llm_config_store.provider
        model = llm_config_store.model
        api_key = llm_config_store.get_api_key(provider)

        log.info("llm_query", provider=provider, model=model, message_preview=user_message[:80])

        try:
            if provider == "gemini":
                if not api_key:
                    log.warning("gemini_no_api_key")
                    return _mock_response(user_message, "No Gemini API key — set one in ⚙ LLM Config")
                return await _query_gemini(user_message, context, api_key, model, version_context)

            elif provider == "groq":
                if not api_key:
                    log.warning("groq_no_api_key")
                    return _mock_response(user_message, "No Groq API key — set one in ⚙ LLM Config")
                return await _query_groq(user_message, context, api_key, model, version_context)

            elif provider == "openai":
                if not api_key:
                    log.warning("openai_no_api_key")
                    return _mock_response(user_message, "No OpenAI API key — set one in ⚙ LLM Config")
                return await _query_openai(user_message, context, api_key, model, version_context)

            elif provider == "ollama":
                return await _query_ollama(
                    user_message, context, llm_config_store.ollama_base_url, model
                )

            else:
                log.warning("unknown_llm_provider", provider=provider)
                return _mock_response(user_message, f"Unknown provider '{provider}'")

        except Exception as exc:
            import traceback
            log.error(
                "llm_query_failed",
                provider=provider,
                model=model,
                error=str(exc),
                traceback=traceback.format_exc(),
            )
            return (
                f"[LLM ERROR — {provider}/{model}]\n"
                f"Error: {str(exc)[:300]}\n\n"
                "💡 Tip: Switch to a different provider or API key via the ⚙ LLM Config panel."
            )


# Module-level singleton
llm_router = LLMRouter()
