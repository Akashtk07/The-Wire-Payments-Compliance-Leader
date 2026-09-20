"""
Prompt Engineering Learning Router.

Endpoints:
  GET  /api/v1/prompts/topics               — List all prompt engineering topics
  GET  /api/v1/prompts/examples/{topic_id}  — Get curated examples for a topic
  POST /api/v1/prompts/try                  — Try a prompt live via LLM router

Topics cover 9 areas of prompt engineering with domain-specific
financial / ISO 20022 / CBPR+ / LYNX examples throughout.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog
from fastapi import APIRouter, HTTPException, status

from models.schemas import PromptTryRequest, PromptTryResponse
from services.audit_logger import audit_logger
from services.llm_config_store import llm_config_store
from services.llm_router import llm_router
from services.telemetry_bus import TelemetryBus, telemetry_bus

log = structlog.get_logger(__name__)

router = APIRouter(tags=["Prompt Engineering"])

# ---------------------------------------------------------------------------
# Topic catalogue
# ---------------------------------------------------------------------------

PROMPT_TOPICS: List[Dict[str, Any]] = [
    {
        "id": "intro",
        "title": "What Is Prompt Engineering?",
        "icon": "🧠",
        "badge_color": "#00D4FF",
        "short_desc": "The science of communicating with AI models effectively",
        "description": (
            "Prompt engineering is the practice of designing and refining inputs (prompts) "
            "to AI language models to elicit accurate, reliable, and useful outputs. "
            "In the financial domain, well-engineered prompts can automate compliance checks, "
            "explain complex ISO 20022 schemas, and generate structured payment data."
        ),
        "why_it_matters": (
            "Poor prompts → hallucinated field names, incorrect ISO codes, wrong CBPR+ rules. "
            "Well-engineered prompts → deterministic, auditable, compliance-grade AI responses."
        ),
        "technique_tags": ["Fundamentals"],
    },
    {
        "id": "zero_shot",
        "title": "Zero-Shot Prompting",
        "icon": "🎯",
        "badge_color": "#00E5A0",
        "short_desc": "Ask directly — no examples provided",
        "description": (
            "Zero-shot prompting asks the model to perform a task without any examples. "
            "Best for well-defined, unambiguous questions where the model has strong prior knowledge."
        ),
        "when_to_use": "Simple factual lookups, definitions, standard compliance rules.",
        "technique_tags": ["Zero-Shot"],
    },
    {
        "id": "few_shot",
        "title": "Few-Shot Prompting",
        "icon": "📋",
        "badge_color": "#FFB800",
        "short_desc": "Teach by example — show Input→Output pairs",
        "description": (
            "Few-shot prompting provides 2–5 examples of the desired input/output format "
            "before asking the model to process a new input. Dramatically improves consistency "
            "for structured tasks like MT field extraction or ISO code mapping."
        ),
        "when_to_use": "Field mapping, format conversion, structured data extraction.",
        "technique_tags": ["Few-Shot"],
    },
    {
        "id": "chain_of_thought",
        "title": "Chain-of-Thought (CoT)",
        "icon": "🔗",
        "badge_color": "#A855F7",
        "short_desc": "Guide the model through step-by-step reasoning",
        "description": (
            "Chain-of-Thought prompting asks the model to reason step by step before "
            "giving a final answer. Essential for complex compliance rule analysis, "
            "multi-hop settlement chain tracing, or UETR reconciliation scenarios."
        ),
        "when_to_use": "Complex rule analysis, multi-step validation, return reason determination.",
        "technique_tags": ["Chain-of-Thought", "Reasoning"],
    },
    {
        "id": "role_prompting",
        "title": "Role & Persona Prompting",
        "icon": "🎭",
        "badge_color": "#FF6B35",
        "short_desc": "Assign the model an expert identity",
        "description": (
            "Role prompting assigns a specific expert persona to the model (e.g. 'Act as a "
            "senior CBPR+ compliance officer') to focus its knowledge domain and response style. "
            "Dramatically improves depth and accuracy for domain-specific questions."
        ),
        "when_to_use": "Expert Q&A, compliance advisory, technical explanation generation.",
        "technique_tags": ["Role", "Persona"],
    },
    {
        "id": "structured_output",
        "title": "Structured Output Prompting",
        "icon": "📊",
        "badge_color": "#00D4FF",
        "short_desc": "Force JSON, XML, or table output reliably",
        "description": (
            "Structured output prompting instructs the model to respond in a specific machine-readable "
            "format (JSON, XML, Markdown table). Critical for automated pipelines where the LLM output "
            "needs to be parsed programmatically."
        ),
        "when_to_use": "API integrations, automated compliance checks, data extraction pipelines.",
        "technique_tags": ["Structured Output", "JSON", "XML"],
    },
    {
        "id": "rag_prompting",
        "title": "RAG-Augmented Prompting",
        "icon": "📚",
        "badge_color": "#00E5A0",
        "short_desc": "Ground the LLM in retrieved document chunks",
        "description": (
            "Retrieval-Augmented Generation (RAG) augments the LLM prompt with relevant chunks "
            "retrieved from a vector database (like our ChromaDB store). This grounds the model's "
            "response in actual compliance documents rather than training-time knowledge."
        ),
        "when_to_use": "Document Q&A, compliance policy lookup, LYNX/CBPR+ guideline queries.",
        "technique_tags": ["RAG", "Grounding", "Documents"],
    },
    {
        "id": "anti_patterns",
        "title": "Prompt Anti-Patterns",
        "icon": "⚠️",
        "badge_color": "#FF4444",
        "short_desc": "Common mistakes and how to fix them",
        "description": (
            "Prompt anti-patterns are common mistakes that lead to unreliable, hallucinated, or "
            "unusable LLM responses. Understanding what NOT to do is as important as knowing best practices."
        ),
        "when_to_use": "Debugging poor LLM responses, reviewing prompt quality, team training.",
        "technique_tags": ["Anti-Patterns", "Debugging"],
    },
    {
        "id": "financial_domain",
        "title": "CBPR+ / LYNX Domain Templates",
        "icon": "🏦",
        "badge_color": "#FFB800",
        "short_desc": "Ready-to-use templates for financial compliance AI",
        "description": (
            "Production-ready prompt templates specifically designed for ISO 20022, CBPR+, "
            "and Canada LYNX payment compliance workflows. Copy and adapt for your use case."
        ),
        "when_to_use": "Production compliance workflows, regulatory reporting, payment analysis.",
        "technique_tags": ["Templates", "CBPR+", "LYNX", "ISO 20022"],
    },
]

# ---------------------------------------------------------------------------
# Example catalogue
# ---------------------------------------------------------------------------

PROMPT_EXAMPLES: Dict[str, List[Dict[str, Any]]] = {
    "intro": [
        {
            "id": "intro_01",
            "title": "Basic Prompt vs. Engineered Prompt",
            "technique": "Comparison",
            "bad_prompt": "Tell me about MT103.",
            "good_prompt": (
                "Explain the SWIFT MT103 message type in the context of ISO 20022 CBPR+ migration. "
                "Cover: (1) what MT103 represents, (2) its ISO 20022 equivalent (pacs.008), "
                "(3) three key CBPR+ R2025 rules that apply, and (4) one real-world example. "
                "Keep the response under 300 words."
            ),
            "why_better": (
                "The engineered prompt specifies scope, structure (numbered list), constraint (300 words), "
                "and domain context (CBPR+ migration). The model has clear guardrails."
            ),
        },
    ],
    "zero_shot": [
        {
            "id": "zs_01",
            "title": "UETR Definition",
            "technique": "Zero-Shot",
            "prompt": (
                "What is a UETR in ISO 20022 payments? "
                "Explain its format, who generates it, and why it is mandatory in CBPR+ R2025."
            ),
            "expected_answer_hint": "UUID4, mandatory in pacs.008/009/004 PmtId block, end-to-end tracking",
        },
        {
            "id": "zs_02",
            "title": "Return Reason Code Lookup",
            "technique": "Zero-Shot",
            "prompt": (
                "In ISO 20022 pacs.004 (Payment Return), what does return reason code 'AM09' mean? "
                "When should a bank use it versus 'AC04'?"
            ),
            "expected_answer_hint": "AM09=wrong amount; AC04=account closed",
        },
        {
            "id": "zs_03",
            "title": "LYNX vs CBPR+ Key Difference",
            "technique": "Zero-Shot",
            "prompt": (
                "What is the most important difference between the LYNX (Canada) and CBPR+ schemes "
                "when processing a pacs.009 COV (cover payment)? Focus specifically on the UETR rule."
            ),
            "expected_answer_hint": "LYNX propagates same UETR; CBPR+ generates new UETR for cover leg",
        },
    ],
    "few_shot": [
        {
            "id": "fs_01",
            "title": "MT Field → ISO 20022 XML Element Mapping",
            "technique": "Few-Shot",
            "prompt": (
                "Map the following SWIFT MT fields to their ISO 20022 XML elements.\n\n"
                "Examples:\n"
                "MT field :20: → <MsgId> in GrpHdr\n"
                "MT field :32A: → <IntrBkSttlmAmt Ccy=''> + <IntrBkSttlmDt>\n"
                "MT field :50K: → <Dbtr><Nm> + <DbtrAcct><Id><IBAN>\n\n"
                "Now map these:\n"
                "MT field :52A: → ?\n"
                "MT field :57A: → ?\n"
                "MT field :59: → ?\n"
                "MT field :71A: → ?"
            ),
            "expected_answer_hint": ":52A:→DbtrAgt; :57A:→CdtrAgt; :59:→Cdtr+CdtrAcct; :71A:→ChrgBr",
        },
        {
            "id": "fs_02",
            "title": "Payment Type Classification",
            "technique": "Few-Shot",
            "prompt": (
                "Classify the following payment scenarios by ISO 20022 message type.\n\n"
                "Examples:\n"
                "Customer wire transfer from Bank A to Bank B → pacs.008.001.08\n"
                "Bank funds its correspondent account → pacs.009.001.08 (CORE)\n"
                "Bank covers a customer payment through a correspondent → pacs.009.001.08 (COV)\n\n"
                "Now classify:\n"
                "1. Royal Bank of Canada sends CAD 500,000 to TD Bank via LYNX for its own account.\n"
                "2. A beneficiary's account was closed; the bank reverses a received pacs.008.\n"
                "3. HSBC Toronto receives a customer payment from HSBC London.\n"
                "4. Scotiabank covers a USD customer payment through a US correspondent."
            ),
            "expected_answer_hint": "1→pacs.009 CORE (LYNX); 2→pacs.004; 3→pacs.008; 4→pacs.009 COV",
        },
    ],
    "chain_of_thought": [
        {
            "id": "cot_01",
            "title": "CBPR+ Prohibited Field Analysis",
            "technique": "Chain-of-Thought",
            "prompt": (
                "I have an MT202 message that contains field :50K: (ordering customer) and :59: (beneficiary). "
                "Think step by step: Can this message be translated to pacs.009.001.08 CORE? "
                "Walk through the CBPR+ rules, identify any violations, and state what action should be taken."
            ),
            "expected_answer_hint": (
                "Step 1: MT202→pacs.009 CORE; Step 2: :50K:/:59: are retail customer fields; "
                "Step 3: pacs.009 CORE MUST NOT contain retail fields; Step 4: Violation → must use MT202COV"
            ),
        },
        {
            "id": "cot_02",
            "title": "Cover Payment Reconciliation",
            "technique": "Chain-of-Thought",
            "prompt": (
                "Bank B received a pacs.008 with UETR 'aaaa-1111' (announcement). "
                "Later it received a pacs.009 COV with UETR 'bbbb-2222'. "
                "Think step by step: Is this a CBPR+ or LYNX payment? How should Bank B reconcile the two messages? "
                "What field links them?"
            ),
            "expected_answer_hint": (
                "Different UETRs → likely CBPR+ (LYNX would have same UETR). "
                "Link via UndrlygCstmrCdtTrf data (Dbtr/Cdtr/Amount) rather than UETR."
            ),
        },
    ],
    "role_prompting": [
        {
            "id": "rp_01",
            "title": "CBPR+ Compliance Officer",
            "technique": "Role Prompting",
            "system_prompt": (
                "You are a senior SWIFT CBPR+ compliance officer with 15 years of experience "
                "in ISO 20022 migration projects at Tier 1 global banks. "
                "You provide precise, regulatory-grade answers citing specific CBPR+ R2025 rules."
            ),
            "prompt": (
                "Our bank is processing a pacs.008 that has ChrgBr=DEBT (Debtor pays all charges). "
                "Is this compliant under CBPR+ R2025? What are the consequences if we send this?"
            ),
            "expected_answer_hint": (
                "DEBT (DEBT code) is not permitted at interbank level under CBPR+ R2025. "
                "Only SHAR is valid. DEBT maps to OUR in MT103 which is also remapped to SHAR."
            ),
        },
        {
            "id": "rp_02",
            "title": "Payments Canada LYNX Specialist",
            "technique": "Role Prompting",
            "system_prompt": (
                "You are a certified Payments Canada LYNX technical integration specialist. "
                "You have implemented LYNX ISO 20022 connectivity for 5 Canadian Schedule I banks. "
                "You answer in precise technical terms referencing Payments Canada's LYNX Usage Guidelines."
            ),
            "prompt": (
                "A Canadian bank's internal system still uses MT205 for domestic interbank transfers. "
                "What is the exact pacs.009 configuration they need for LYNX? "
                "What Business Application Header (BAH) Business Service value is required?"
            ),
            "expected_answer_hint": "pacs.009 CORE with BizSvc=paymentsca.lynx.03; CLRG only; single payment",
        },
    ],
    "structured_output": [
        {
            "id": "so_01",
            "title": "Extract Payment Fields as JSON",
            "technique": "Structured Output",
            "prompt": (
                "Extract the following payment fields from this MT103 message and return them as valid JSON. "
                "Return ONLY the JSON object, no explanation.\n\n"
                "Required fields: transaction_ref, value_date, currency, amount, ordering_customer_name, "
                "beneficiary_name, charge_bearer, uetr (if present)\n\n"
                "MT103 message:\n"
                "{1:F01BANKGB2LAXXX0000000000}{2:I103BANKUS33XXXXN}"
                "{3:{108:TXREF001}{121:f9e4a3b2-1c5d-4e7f-8a9b-0d1e2f3a4b5c}}"
                "{4:\n:20:TXREF001\n:32A:260523USD10000,00\n:50K:ACME CORP\n:59:JOHN DOE\n:71A:SHA\n-}"
            ),
            "expected_answer_hint": '{"transaction_ref":"TXREF001","value_date":"2026-05-23",...}',
        },
        {
            "id": "so_02",
            "title": "Generate ISO 20022 Validation Report",
            "technique": "Structured Output",
            "prompt": (
                "Validate the following ISO 20022 pacs.008 fields against CBPR+ R2025 rules "
                "and return the result as a JSON object with the structure:\n"
                '{"is_valid": boolean, "violations": [{"field": string, "rule": string, "severity": "ERROR"|"WARN"}]}\n\n'
                "Fields to validate:\n"
                "- UETR: present ✓\n"
                "- ChrgBr: DEBT\n"
                "- PostalAddress: AdrLine only (no TwnNm/Ctry)\n"
                "- IntrBkSttlmAmt currency: USD\n"
                "- InstdAmt currency: GBP"
            ),
            "expected_answer_hint": (
                'is_valid:false; violations: ChrgBr=DEBT(ERROR), PostalAddress missing TwnNm/Ctry(WARN), currency mismatch(ERROR)'
            ),
        },
    ],
    "rag_prompting": [
        {
            "id": "rag_01",
            "title": "RAG vs. Direct Prompt — Why Context Matters",
            "technique": "RAG",
            "prompt": (
                "Without any context documents, answer: What are the exact field-level rules for "
                "<PostalAddress> in CBPR+ R2025 pacs.008?\n\n"
                "Then explain how providing a retrieved chunk from the CBPR+ Usage Guidelines would "
                "improve this answer and reduce hallucination risk."
            ),
            "expected_answer_hint": (
                "Without RAG: general answer. With RAG: exact field constraints from official spec. "
                "RAG grounds the LLM in authoritative, current documentation."
            ),
        },
        {
            "id": "rag_02",
            "title": "Using Document Context in a Prompt",
            "technique": "RAG",
            "prompt": (
                "Using the following retrieved context, answer the question.\n\n"
                "[CONTEXT CHUNK — CBPR+ Usage Guidelines §3.4.2]\n"
                "PostalAddress: From November 2026, fully unstructured addresses (AdrLine only) "
                "will be rejected by SWIFT FINplus. Participants must use Hybrid (TwnNm + Ctry "
                "mandatory, max 2 AdrLine elements) or Fully Structured format.\n\n"
                "[QUESTION]\n"
                "My bank sends pacs.008 messages with only AdrLine elements and no TwnNm/Ctry. "
                "What do we need to change, and when is the deadline?"
            ),
            "expected_answer_hint": "Add TwnNm + Ctry; hybrid mode; deadline November 2026",
        },
    ],
    "anti_patterns": [
        {
            "id": "ap_01",
            "title": "Vague Instructions",
            "technique": "Anti-Pattern",
            "bad_prompt": "Explain ISO 20022.",
            "good_prompt": (
                "Explain how pacs.008.001.08 differs from pacs.009.001.08 in the CBPR+ scheme. "
                "Focus on: (1) use case, (2) mandatory fields unique to each, (3) ChrgBr rules. "
                "Format as a comparison table."
            ),
            "anti_pattern_name": "Vague Instructions",
            "problem": "Too broad — model will give a generic 5000-word essay covering everything.",
            "fix": "Specify exact message types, exact aspects to compare, and output format.",
        },
        {
            "id": "ap_02",
            "title": "Asking Multiple Unrelated Questions",
            "technique": "Anti-Pattern",
            "bad_prompt": (
                "What is UETR? Also explain ChrgBr. And tell me about MT202COV. "
                "Also what is the LYNX system and how does it differ from CBPR+?"
            ),
            "good_prompt": (
                "Focus on one topic: Explain how the UETR (Unique End-to-End Transaction Reference) "
                "is used in the CBPR+ cover payment flow. Specifically:\n"
                "1. Who generates the UETR for the pacs.008?\n"
                "2. What UETR does the pacs.009 COV carry in CBPR+?\n"
                "3. How does the beneficiary bank use the UETR to reconcile the two messages?"
            ),
            "anti_pattern_name": "Question Stacking",
            "problem": "Multiple unrelated questions produce shallow, disorganised answers for each.",
            "fix": "One focused question per prompt with numbered sub-points.",
        },
        {
            "id": "ap_03",
            "title": "No Output Format Specification",
            "technique": "Anti-Pattern",
            "bad_prompt": "Give me the return reason codes for pacs.004.",
            "good_prompt": (
                "List all CBPR+ R2025 approved pacs.004 return reason codes. "
                "Format as a Markdown table with columns: Code | Meaning | When to Use. "
                "Include exactly the 24 codes in the R2025 extended list."
            ),
            "anti_pattern_name": "No Output Format",
            "problem": "Model produces unstructured prose; hard to parse or display.",
            "fix": "Always specify the output format: table, JSON, bullet list, numbered list.",
        },
    ],
    "financial_domain": [
        {
            "id": "fd_01",
            "title": "MT→MX Translation Validation Template",
            "technique": "Domain Template",
            "prompt": (
                "Act as a CBPR+ R2025 compliance validator.\n\n"
                "I have translated an MT{MT_TYPE} message to {PACS_TYPE}. "
                "The generated XML contains the following fields:\n"
                "{FIELD_LIST}\n\n"
                "Step by step:\n"
                "1. Verify UETR is present and UUID4 format\n"
                "2. Check ChrgBr value is SHAR for interbank\n"
                "3. Verify PostalAddress has TwnNm + Ctry (R2025 hybrid)\n"
                "4. Check for any prohibited fields for this message type\n"
                "5. Provide a PASS/FAIL verdict with specific issues found\n\n"
                "Return as JSON: {\"verdict\": \"PASS\"|\"FAIL\", \"issues\": [...]}"
            ),
            "is_template": True,
            "template_vars": ["MT_TYPE", "PACS_TYPE", "FIELD_LIST"],
        },
        {
            "id": "fd_02",
            "title": "LYNX Payment Routing Decision",
            "technique": "Domain Template",
            "prompt": (
                "Act as a Payments Canada LYNX routing specialist.\n\n"
                "A Canadian bank needs to send a {AMOUNT} CAD payment from {SENDER_BANK} to {RECEIVER_BANK}. "
                "The banks {HAVE_OR_DONT} a direct nostro/vostro relationship.\n\n"
                "Determine:\n"
                "1. Should this use pacs.008 (Direct) or pacs.009 COV (Cover) method?\n"
                "2. What Business Application Header Business Service value is required?\n"
                "3. What UETR rule applies?\n"
                "4. Is SttlmMtd=CLRG enforced?\n"
                "5. Provide the recommended message flow diagram in ASCII."
            ),
            "is_template": True,
            "template_vars": ["AMOUNT", "SENDER_BANK", "RECEIVER_BANK", "HAVE_OR_DONT"],
        },
        {
            "id": "fd_03",
            "title": "Return Reason Analysis Template",
            "technique": "Domain Template",
            "prompt": (
                "Act as an ISO 20022 payment operations specialist.\n\n"
                "A pacs.004 return was received with:\n"
                "- OrgnlUETR: {ORIGINAL_UETR}\n"
                "- OrgnlMsgNmId: {ORIGINAL_MSG_TYPE}\n"
                "- Return reason code: {RETURN_CODE}\n"
                "- Amount: {AMOUNT} {CURRENCY}\n\n"
                "Provide:\n"
                "1. What the return reason code means\n"
                "2. What the original message type was (pacs.008 or pacs.009)\n"
                "3. Which MT type this return maps to (MT103RETURN, MT202RETURN, or MT205RETURN)\n"
                "4. Next action the receiving bank should take\n"
                "5. Any SLA/regulatory deadline for processing this return"
            ),
            "is_template": True,
            "template_vars": ["ORIGINAL_UETR", "ORIGINAL_MSG_TYPE", "RETURN_CODE", "AMOUNT", "CURRENCY"],
        },
    ],
}


# ---------------------------------------------------------------------------
# GET /prompts/topics
# ---------------------------------------------------------------------------


@router.get(
    "/prompts/topics",
    summary="List all prompt engineering topics",
)
async def list_topics() -> Dict[str, Any]:
    """Returns the full prompt engineering topic catalogue."""
    return {
        "total": len(PROMPT_TOPICS),
        "topics": PROMPT_TOPICS,
    }


# ---------------------------------------------------------------------------
# GET /prompts/examples/{topic_id}
# ---------------------------------------------------------------------------


@router.get(
    "/prompts/examples/{topic_id}",
    summary="Get curated prompt examples for a topic",
)
async def get_examples(topic_id: str) -> Dict[str, Any]:
    """
    Returns the curated prompt examples for the requested topic ID.

    Available topic IDs:
    intro, zero_shot, few_shot, chain_of_thought, role_prompting,
    structured_output, rag_prompting, anti_patterns, financial_domain
    """
    examples = PROMPT_EXAMPLES.get(topic_id)
    if examples is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "TOPIC_NOT_FOUND",
                "message": f"No examples found for topic_id '{topic_id}'",
                "available": list(PROMPT_EXAMPLES.keys()),
            },
        )
    return {
        "topic_id": topic_id,
        "count": len(examples),
        "examples": examples,
    }


# ---------------------------------------------------------------------------
# POST /prompts/try  — Live LLM execution
# ---------------------------------------------------------------------------


@router.post(
    "/prompts/try",
    response_model=PromptTryResponse,
    summary="Try a prompt live — send to the configured LLM and get a response",
)
async def try_prompt(body: PromptTryRequest) -> Any:
    """
    Executes the provided prompt through the platform's configured LLM
    (Gemini, OpenAI, Groq, or Ollama — set in Admin Console).

    If a `system_prompt` is provided, it is prepended as role context.
    All prompt attempts are audit-logged for compliance.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    # Compose final prompt with optional system role prefix
    final_prompt = body.prompt
    if body.system_prompt:
        final_prompt = (
            f"[SYSTEM ROLE]\n{body.system_prompt.strip()}\n\n"
            f"[USER PROMPT]\n{body.prompt.strip()}"
        )

    try:
        response_text = await llm_router.query(
            user_message=final_prompt,
            context=f"Prompt Engineering — Technique: {body.technique or 'general'}"
        )
    except Exception as exc:
        log.error("prompt_engineering_llm_error", error=str(exc))
        audit_id = await audit_logger.log(
            event_type="PROMPT_ENGINEERING",
            module="prompt_engineering",
            status="ERROR",
            details={
                "error": str(exc),
                "technique": body.technique,
                "topic_id": body.topic_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "LLM_UNAVAILABLE",
                "message": f"LLM query failed: {str(exc)}",
                "audit_id": audit_id,
            },
        )

    audit_id = await audit_logger.log(
        event_type="PROMPT_ENGINEERING",
        module="prompt_engineering",
        status="SUCCESS",
        details={
            "technique": body.technique,
            "topic_id": body.topic_id,
            "prompt_length": len(body.prompt),
            "response_length": len(response_text),
        },
    )

    # Telemetry
    event = TelemetryBus.make_event(
        event_type="PROMPT_TRIED",
        module=2,
        severity="INFO",
        summary=f"Prompt Engineering [{body.technique or 'general'}] — {len(body.prompt)} chars",
        data={"audit_id": audit_id, "topic_id": body.topic_id},
    )
    await telemetry_bus.broadcast(event)

    # Get model info from config store
    model_used = f"{llm_config_store.provider}/{llm_config_store.model}"

    return PromptTryResponse(
        response=response_text,
        technique=body.technique,
        topic_id=body.topic_id,
        model_used=model_used,
        audit_id=audit_id,
        timestamp=timestamp,
    )
