# The Compliance Leader — Comprehensive Project Documentation

> **"Enterprise-grade ISO 20022 / SWIFT MT translation, validation, domain learning, and multi-format document intelligence platform. All operations are immutably audited with a tamper-evident SHA-256 chain."**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [System Architecture](#2-system-architecture)
3. [Tech Stack](#3-tech-stack)
4. [Module 1 — TX Translation & Validation Engine (Data Flow)](#4-module-1--tx-translation--validation-engine-data-flow)
5. [Module 2 — Interactive Learning System (Data Flow)](#5-module-2--interactive-learning-system-data-flow)
6. [Module 3 — Document Intelligence / RAG Pipeline (Data Flow)](#6-module-3--document-intelligence--rag-pipeline-data-flow)
7. [Module 4 — Audit & Real-Time Telemetry (Data Flow)](#7-module-4--audit--real-time-telemetry-data-flow)
8. [Authentication & Authorization Flow](#8-authentication--authorization-flow)
9. [Multi-Provider LLM Router](#9-multi-provider-llm-router)
10. [Service Layer — Core Functionality Deep Dive](#10-service-layer--core-functionality-deep-dive)
11. [Frontend Architecture & Component Flow](#11-frontend-architecture--component-flow)
12. [Database & Persistence Design](#12-database--persistence-design)
13. [Security Design Decisions](#13-security-design-decisions)
14. [API Endpoint Reference](#14-api-endpoint-reference)
15. [Deployment — Docker Compose](#15-deployment--docker-compose)
16. [Resume Description](#16-resume-description)

---

## 1. Project Overview

**The Compliance Leader** is a production-grade, full-stack financial compliance platform designed for banks, payment engineers, and compliance officers. It solves the real-world problem of SWIFT MT-to-ISO 20022 migration under the **CBPR+ R2025** mandate (effective November 22, 2025), where legacy SWIFT MT103/MT202/MT202COV messages were retired from SWIFT FINplus and must be expressed in ISO 20022 XML format.

The platform provides four tightly integrated capabilities:

| # | Module | Core Problem Solved |
|---|--------|---------------------|
| 1 | **TX Translation & Validation Engine** | Deterministically converts any raw SWIFT MT message string into a validated ISO 20022 XML document, enforcing CBPR+ R2025 compliance rules |
| 2 | **Interactive Learning System** | AI-powered Q&A (RAG + LLM) for compliance education — explains ISO 20022 schemas, CBPR+ rules, settlement chains, and UETR tracking |
| 3 | **Document Intelligence (RAG)** | Ingests compliance PDFs/PPTs/DOCXs, chunks and embeds them, stores them in a vector database, and lets users ask natural-language questions against them |
| 4 | **Audit & Telemetry** | Every operation generates a SHA-256 hash-chained, PII-masked, append-only audit log entry; real-time WebSocket telemetry feeds the live dashboard |

---

## 2. System Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js 14)                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐  │
│  │ /translate │ │  /learn    │ │ /documents │ │  /audit    │  │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘  │
│        │               │               │               │         │
│        └───────────────┴───────────────┴───────────────┘        │
│                              │ REST API calls                    │
│                         WebSocket (/ws/telemetry)               │
└────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────┐
│                   BACKEND (FastAPI / Python 3.12)              │
│                                                                │
│   CORS Middleware → Routers → Services → DB / Vector Store     │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      ROUTERS                             │  │
│  │  auth.py │ translate.py │ learn.py │ documents.py │      │  │
│  │  audit.py │ admin.py │ llm_config.py │ guidelines.py     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                            │                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                     SERVICES                             │  │
│  │  mt_parser  │  mx_translator  │  validator               │  │
│  │  llm_router │  rag_pipeline   │  audit_logger            │  │
│  │  auth_service │ telemetry_bus │ email_service            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │  SQLite (Users) │  │ ChromaDB (Vecs) │  │ NDJSON Audit │  │
│  └─────────────────┘  └─────────────────┘  └──────────────┘  │
└────────────────────────────────────────────────────────────────┘
                              │
                  ┌───────────┴────────────┐
                  │   External LLM APIs    │
                  │  Gemini │ OpenAI │     │
                  │  Groq   │ Ollama │     │
                  └────────────────────────┘
```

---

## 3. Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend Framework** | FastAPI (Python 3.12) | Async REST + WebSocket API |
| **Backend Runtime** | Uvicorn (ASGI) | Production ASGI server |
| **Database (User Auth)** | SQLite + SQLAlchemy | Async ORM for user management |
| **Vector Database** | ChromaDB (persistent) | Stores document embeddings for RAG |
| **Embedding Model** | `all-MiniLM-L6-v2` (sentence-transformers) | Creates 384-dim vectors for text chunks |
| **XML Processing** | lxml | Builds and validates ISO 20022 XML |
| **LLM Providers** | Gemini, OpenAI, Groq, Ollama | Multi-provider AI query routing |
| **Auth** | JWT (HS256) + bcrypt (cost 12) | Banking-grade stateless auth |
| **Email** | Gmail SMTP (aiosmtplib) | OTP delivery |
| **Logging** | structlog (JSON structured) | Production-grade structured logs |
| **Frontend Framework** | Next.js 14 (App Router, TypeScript) | Server-side + client-side rendering |
| **Frontend State** | React Hooks (`useState`, `useEffect`, `useRef`) | Component-level state |
| **Styling** | Vanilla CSS (custom design system) | Premium dark theme with glassmorphism |
| **Containerization** | Docker + Docker Compose | One-command full-stack deployment |
| **Audit Storage** | NDJSON files (append-only) | SHA-256 hash-chained tamper-evident logs |

---

## 4. Module 1 — TX Translation & Validation Engine (Data Flow)

This is the core technical module. It translates raw SWIFT MT message strings into ISO 20022 XML per the CBPR+ R2025 standard.

### 4.1 Complete Data Flow: `POST /api/v1/translate`

```
User submits raw MT message string
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 1: MTParser.parse(raw_mt, source_type)                │
│                                                             │
│  1a. _extract_blocks(raw_mt)                                │
│      ├── Regex: \{(\d):(.*?)\}  → extracts blocks 1-5      │
│      └── Returns: { "1": "F01BANKGB2L...", "4": ":20:...", │
│                      "5": "{CHK:...}" }                     │
│                                                             │
│  1b. _extract_block4_tags(block4)                           │
│      ├── Splits on :TAG: boundaries using regex             │
│      ├── Collapses multi-line values into single strings     │
│      └── Returns: { "20": "TXREF001", "32A": "260523USD..."}│
│                                                             │
│  1c. _resolve_fields(raw_tags, field_map)                   │
│      ├── Maps tag codes to semantic field names             │
│      │   e.g. "50K" → "ordering_customer"                  │
│      │        "59"  → "beneficiary_customer"               │
│      │        "32A" → "value_date_currency_amount"          │
│      └── Returns: { "ordering_customer": {tag:"50K",       │
│                       value:"/GB29... ACME CORP"} }         │
│                                                             │
│  1d. _extract_sender_bic(block1)                            │
│      └── Extracts 12-char LT address from block1 pos [3:15] │
│                                                             │
│  1e. Extract UETR from block3 field {121:} if present       │
└─────────────────────────────────────────────────────────────┘
             │
             │   parsed = { source_type, sender_bic, blocks,
             │               fields, raw_tags }
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 2: MXTranslator.translate(parsed, source_type)        │
│                                                             │
│  2a. Auto-detect target_type                                │
│      MT103 → pacs.008.001.08                                │
│      MT202 → pacs.009.001.08 (CORE)                         │
│      MT202COV → pacs.009.001.08 (COV)                       │
│      MT204 → pacs.009.001.08 (ADV)                          │
│      MT103RETURN / MT202RETURN → pacs.004.001.09            │
│                                                             │
│  2b. _check_prohibited_fields() — CBPR+ R2025 Guards        │
│      ├── MT202 + pacs.009: MUST NOT have retail_customer    │
│      │   fields → raises ValidationException (HTTP 422)     │
│      ├── MT202COV + pacs.009: MUST have underlying_customer │
│      │   block → raises ValidationException if absent       │
│      └── pacs.008: Currency consistency check (32A vs 33B)  │
│                                                             │
│  2c. UETR generation / validation                           │
│      ├── Preserve existing UETR from parsed["uetr"]         │
│      ├── Validate it is a valid UUID4 format                │
│      └── Generate new UUID4 if missing or invalid           │
│                                                             │
│  2d. XML Builder (lxml)                                     │
│      _build_pacs008(parsed, uetr)                           │
│       ├── Document root: urn:iso:std:iso:20022:tech:...     │
│       ├── GrpHdr: MsgId, CreDtTm, NbOfTxs, SttlmInf        │
│       ├── CdtTrfTxInf                                       │
│       │   ├── PmtId: InstrId, EndToEndId, UETR (mandatory!) │
│       │   ├── PmtTpInf: SvcLvl/Cd = "SDVA"                 │
│       │   ├── IntrBkSttlmAmt (from :32A: parsed)            │
│       │   ├── IntrBkSttlmDt                                 │
│       │   ├── InstdAmt (from :33B: if present)              │
│       │   ├── ChrgBr: SHA→SHAR, OUR→SHAR, BEN→SHAR          │
│       │   ├── DbtrAgt: FinInstnId/BICFI (from :52A:)         │
│       │   ├── Dbtr: Nm + PstlAdr (hybrid R2025)             │
│       │   │   └── _add_postal_address_r2025()               │
│       │   │       ├── TwnNm (mandatory in R2025)            │
│       │   │       ├── Ctry (mandatory in R2025)             │
│       │   │       └── AdrLine (up to 2 free-text lines)      │
│       │   ├── DbtrAcct: Id/IBAN or Othr/Id                  │
│       │   ├── IntrmyAgt1 (from :56A: if present)             │
│       │   ├── CdtrAgt (from :57A:)                          │
│       │   ├── Cdtr: Nm + PstlAdr                            │
│       │   ├── CdtrAcct: IBAN or Othr                        │
│       │   ├── RmtInf: Ustrd (from :70:)                     │
│       │   └── Purp: Cd (from :26T: if CBPR+ purpose code)   │
│       └── Returns XML string (UTF-8, with declaration)      │
└─────────────────────────────────────────────────────────────┘
             │
             │   xml_output (ISO 20022 XML string)
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 3: ISO20022Validator.validate(xml_output, msg_type)   │
│                                                             │
│  3a. etree.fromstring(xml_bytes) — parse XML structure      │
│                                                             │
│  3b. XSD validation (if .xsd file found in data/xsd/)      │
│      ├── _load_xsd(message_type) — cached per process       │
│      └── etree.XMLSchema.validate(root) — schema check      │
│                                                             │
│  3c. CBPR+ R2025 Business Rule Checks                       │
│      For pacs.008:                                          │
│        ├── [RULE] Dbtr, Cdtr, DbtrAgt, CdtrAgt required     │
│        ├── [RULE] PmtId/UETR must be valid UUID4            │
│        ├── [RULE] ChrgBr must be "SHAR"                     │
│        ├── [RULE] PstlAdr/TwnNm mandatory                   │
│        ├── [RULE] PstlAdr/Ctry must be ISO 2-letter code    │
│        └── [WARN] PmtTpInf/SvcLvl recommended               │
│      For pacs.009 CORE:                                     │
│        ├── [RULE] No UltmtDbtr/UltmtCdtr at top level       │
│        ├── [RULE] UETR mandatory                            │
│        └── [RULE] ChrgBr = SHAR                             │
│      For pacs.009 COV:                                      │
│        ├── [RULE] UndrlygCstmrCdtTrf block required         │
│        ├── [RULE] Underlying Dbtr required                  │
│        └── [RULE] Underlying Cdtr required                  │
│      For pacs.004:                                          │
│        ├── [RULE] OrgnlUETR (UUID4) required                │
│        ├── [RULE] OrgnlMsgId required                       │
│        ├── [RULE] RtrId required                            │
│        └── [RULE] RtrRsnInf/Rsn/Cd must be valid code       │
│                                                             │
│  3d. Returns (is_valid: bool, errors: List[str])            │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 4: audit_logger.log(event_type="TRANSLATION", ...)    │
│      ├── Generates UUID4 audit_id                           │
│      ├── Serialises entry to JSON, masks PII (IBANs)        │
│      ├── Computes SHA-256: hash(prev_hash + entry_json)     │
│      ├── Appends to compliance_audit_YYYY-MM-DD.ndjson      │
│      └── Returns audit_id                                   │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│  Step 5: telemetry_bus.broadcast(TRANSLATION_COMPLETE)      │
│      └── Sends JSON event to all connected WebSocket clients │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
         HTTP 200 → TranslationResponse
         { status, message_type, xml_output,
           uetr, validation_errors, audit_id, timestamp }
```

### 4.2 CBPR+ R2025 Key Rules Enforced

| Rule | Enforcement Point | Consequence |
|------|------------------|-------------|
| UETR (UUID4) mandatory | `mx_translator.py` + `validator.py` | HTTP 422 if absent/invalid |
| ChrgBr = SHAR only | `mx_translator.py` (map SHA/OUR/BEN → SHAR) | Auto-corrected in output |
| Hybrid PostalAddress (TwnNm + Ctry) | `_add_postal_address_r2025()` | Injected in every party element |
| pacs.009 CORE: no retail customer data | `_check_prohibited_fields()` | HTTP 422 SWIFT_ISO_MUTATION_DENIED |
| pacs.009 COV: UndrlygCstmrCdtTrf required | `_check_prohibited_fields()` | HTTP 422 |
| Currency consistency (32A vs 33B) | `_check_prohibited_fields()` | HTTP 422 |
| Return reason codes validated | `validator.py + mx_translator.py` | Error appended to validation list |

---

## 5. Module 2 — Interactive Learning System (Data Flow)

### 5.1 Complete Data Flow: `POST /api/v1/learn`

```
User submits query + optional context + guideline versions
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  Auth check: get_current_user (JWT Bearer token required)  │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  Decision: Are documents indexed in ChromaDB?              │
│                                                            │
│  _get_collection().count() > 0?                            │
│         │                       │                          │
│        YES                      NO                         │
│         ▼                       ▼                          │
│  Use RAG Pipeline          Pure LLM Query                  │
│  (document-grounded)       (system prompt only)            │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  RAG Path:                                                 │
│                                                            │
│  Option A: Single version or no version filter             │
│    rag_pipeline.query(question, top_k=5, version_filter)   │
│    ├── Embed question: all-MiniLM-L6-v2 → 384-dim vector   │
│    ├── ChromaDB cosine similarity search (HNSW index)      │
│    │   └── Optional WHERE: guideline_version = "CBPR+..."  │
│    ├── Retrieve top-k chunks + metadata                    │
│    ├── Build context string:                               │
│    │   "[Source 1 — filename, Page X, Chunk Y]\n{text}"    │
│    └── Pass context to LLM router                          │
│                                                            │
│  Option B: Cross-version compare (2+ versions selected)    │
│    rag_pipeline.query_cross_version(question, versions)    │
│    ├── For each version: run independent query             │
│    ├── Collect per-version answers                         │
│    ├── Build combined context of all version answers        │
│    ├── Prompt LLM: "Compare how versions answer..."        │
│    │   Format: "⚠️ Changed in [VERSION]: ..."              │
│    └── Return unified_comparison + per_version answers     │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  LLM Router (llm_router.query)                             │
│                                                            │
│  Reads active config from llm_config_store:                │
│    provider = "gemini" | "groq" | "openai" | "ollama"      │
│    model = "gemini-2.0-flash" | "gpt-4o" | "llama3" | ..  │
│                                                            │
│  System Prompt = FINANCIAL_SYSTEM_PROMPT                   │
│    + version-awareness instructions (if versions selected) │
│    "⚠️ Changed in [VERSION]: ..." format instruction       │
│                                                            │
│  User Text = context (from RAG chunks) + question          │
│                                                            │
│  Retry: up to 3 attempts with exponential backoff          │
│    attempt 1 → wait 1s → attempt 2 → wait 2s → attempt 3  │
│                                                            │
│  Fallback: _mock_response() if no API key configured       │
│    Returns keyword-matched snippets for pacs.008/009/etc   │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  Post-processing:                                          │
│    ├── Heuristic msg_type_ref detection                    │
│    │   (scan answer for "pacs.008", "MT103", etc.)         │
│    └── Set sources: filenames if RAG, else LLM labels      │
│                                                            │
│  Audit log: LEARN_QUERY event                              │
│  Telemetry: LEARN_QUERY_COMPLETE broadcast                 │
└────────────────────────────────────────────────────────────┘
             │
             ▼
         HTTP 200 → LearnResponse
         { answer, sources, message_type_referenced, audit_id }
```

---

## 6. Module 3 — Document Intelligence / RAG Pipeline (Data Flow)

### 6.1 Document Ingestion Flow: `POST /api/v1/documents/upload`

```
User uploads file (PDF / PPTX / DOCX / XML / TXT)
  + guideline_version label + category + tags
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  File saved to data/uploads/{uuid}_{filename}              │
│  doc_id generated (UUID4)                                  │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  rag_pipeline.ingest(file_path, filename, doc_id, ...)     │
│                                                            │
│  Step 1: Text Extraction (_extract_text)                   │
│    .pdf  → fitz (PyMuPDF): page-by-page text + page_num   │
│    .pptx → python-pptx: slide-by-slide text + slide_num   │
│    .docx → python-docx: all paragraphs (single page)      │
│    .txt/.xml → raw UTF-8 read                              │
│    Returns: [(text, page_num), ...]                        │
│                                                            │
│  Step 2: Chunking (_chunk_text)                            │
│    chunk_tokens = 512 words                                │
│    overlap_tokens = 64 words                               │
│    step = 512 - 64 = 448 words                             │
│    Returns: [{text, page_num, chunk_index}, ...]           │
│                                                            │
│  Step 3: Embedding                                         │
│    all-MiniLM-L6-v2.encode(texts) → 384-dim float vectors  │
│    (lazy-loaded singleton, CPU-based)                      │
│                                                            │
│  Step 4: ChromaDB Upsert                                   │
│    Collection: "compliance_docs" (cosine similarity space) │
│    IDs: "{doc_id}_chunk_{idx}_page_{page_num}"             │
│    Embeddings: [...float arrays...]                        │
│    Documents: [...text strings...]                         │
│    Metadatas: { doc_id, filename, chunk_index, page_num,   │
│                 guideline_version, guideline_category, tags}│
│    Batch size: 256 (avoids payload limits)                 │
│                                                            │
│  Returns: chunks_indexed count                             │
└────────────────────────────────────────────────────────────┘
             │
             ▼
         HTTP 200 → DocumentUploadResponse
         { doc_id, filename, chunks_indexed, status }
```

### 6.2 Document Query Flow: `POST /api/v1/documents/query`

```
User submits question + top_k + optional version filter
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  Embed question                                            │
│    all-MiniLM-L6-v2.encode([question]) → 384-dim vector    │
│                                                            │
│  ChromaDB query                                            │
│    n_results = min(top_k, collection.count())              │
│    query_embeddings = [question_vector]                    │
│    include = ["documents", "metadatas", "distances"]       │
│    WHERE (optional):                                       │
│      Single version: { guideline_version: {$eq: v} }       │
│      Multi version:  { guideline_version: {$in: [v1, v2]} }│
│                                                            │
│  Returns top-k semantically similar chunks                 │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  Build context for LLM                                     │
│    "[Source 1 — {filename}, Page {n}, Chunk {n}]\n{text}"  │
│    "---" separator between sources                         │
│                                                            │
│  LLM synthesis: llm_router.query(question, context=ctx)    │
└────────────────────────────────────────────────────────────┘
             │
             ▼
         HTTP 200 → DocumentQueryResponse
         { answer, sources (metadata list), audit_id }
```

---

## 7. Module 4 — Audit & Real-Time Telemetry (Data Flow)

### 7.1 Audit Logger Data Flow (Every Operation)

```
Any router calls: await audit_logger.log(event_type, module, status, details)
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  AuditLogger.log()                                         │
│                                                            │
│  1. Acquire asyncio.Lock() — serialise concurrent writes   │
│                                                            │
│  2. _ensure_initialised()                                  │
│     ├── On first write: _seed_last_hash()                  │
│     │   Read today's NDJSON file from the bottom           │
│     │   Extract last entry's "hash" field                  │
│     │   Set self._last_hash = that value                   │
│     │   (ensures chain continuity after restart)           │
│     └── Mark initialised = True                            │
│                                                            │
│  3. Build entry dict:                                      │
│     { audit_id (UUID4), timestamp (ISO 8601),              │
│       event_type, module, status, uetr, message_type,      │
│       details }                                            │
│                                                            │
│  4. PII Masking:                                           │
│     entry_json = json.dumps(entry)                         │
│     _mask_pii(entry_json):                                 │
│       IBAN regex: [A-Z]{2}[0-9]{2}[A-Z0-9]{4,} → [MASKED] │
│       Account regex: \b\d{8,}\b → [MASKED]                 │
│                                                            │
│  5. Hash chaining:                                         │
│     new_hash = SHA256(self._last_hash + entry_json_no_hash) │
│     entry["hash"] = new_hash                               │
│                                                            │
│  6. Append to file:                                        │
│     data/audit/compliance_audit_YYYY-MM-DD.ndjson          │
│     (aiofiles async append mode)                           │
│                                                            │
│  7. self._last_hash = new_hash                             │
│                                                            │
│  8. Return audit_id                                        │
└────────────────────────────────────────────────────────────┘
```

### 7.2 Real-Time Telemetry — WebSocket Data Flow

```
Any operation completes (translate, learn, document upload, validation)
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  TelemetryBus.make_event(event_type, module, severity, ...) │
│    Returns: { event_id (UUID4), timestamp,                 │
│               event_type, module (1-4), severity,          │
│               summary, data: { audit_id, ... } }           │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  telemetry_bus.broadcast(event)                            │
│    ├── Serialise to JSON string                            │
│    ├── For each connected WebSocket client:                │
│    │   ├── Check client.client_state == CONNECTED          │
│    │   ├── await client.send_text(payload)                 │
│    │   └── On error: mark client as dead                   │
│    └── Remove dead clients from _clients set               │
└────────────────────────────────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  Frontend TelemetryFeed component                          │
│    ├── useEffect: new WebSocket(ws://localhost:8000/ws/...  │
│    ├── ws.onmessage: parse JSON, prepend to events array   │
│    ├── maxEvents=10: slice array to latest 10              │
│    └── Renders real-time feed with color-coded severity    │
└────────────────────────────────────────────────────────────┘
```

### 7.3 Audit Log Read Flow: `GET /api/v1/audit/logs`

```
Query params: page, page_size, event_type filter, module filter,
              from_date, to_date
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  audit_logger.get_logs(page, page_size, filters)           │
│                                                            │
│  1. Glob all: compliance_audit_*.ndjson                    │
│  2. Sort chronologically by filename date                  │
│  3. Skip files outside [from_date, to_date] range          │
│  4. Read each file line-by-line with aiofiles              │
│  5. Parse JSON, apply event_type/module filters            │
│  6. Collect all matching entries                           │
│  7. Paginate: total, start=(page-1)*page_size, end=start+n │
│  8. Return { total, page, page_size, entries }             │
└────────────────────────────────────────────────────────────┘
```

---

## 8. Authentication & Authorization Flow

### 8.1 Registration Flow

```
POST /api/v1/auth/register
  { username, email, password, full_name }
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  1. validate_password(password)                            │
│     ├── min 8 chars                                        │
│     ├── at least 1 uppercase                               │
│     ├── at least 1 lowercase                               │
│     ├── at least 1 digit                                   │
│     └── at least 1 special char (!@#$%^&*...)             │
│     → HTTP 422 if violations                               │
│                                                            │
│  2. Check username uniqueness in DB                        │
│     → HTTP 409 USERNAME_TAKEN if exists                    │
│                                                            │
│  3. Check email uniqueness                                 │
│     → If unverified account exists: resend OTP             │
│     → HTTP 409 EMAIL_TAKEN if verified                     │
│                                                            │
│  4. Generate 6-digit OTP: secrets.choice(digits) × 6      │
│     (cryptographically secure, not random.randint)         │
│                                                            │
│  5. hash_otp(otp) using bcrypt (cost 12)                   │
│                                                            │
│  6. Create User record:                                    │
│     role="analyst", is_active=True, is_verified=False       │
│     otp_expires_at = now + OTP_EXPIRE_MINUTES (10 min)     │
│                                                            │
│  7. email_service.send_otp(email, username, otp)           │
│     (Gmail SMTP, aiosmtplib)                               │
│                                                            │
│  8. Audit: USER_REGISTERED                                 │
└────────────────────────────────────────────────────────────┘
```

### 8.2 Login Flow

```
POST /api/v1/auth/login { username, password }
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  1. Lookup user by username OR email (flexible login)      │
│  2. is_account_locked(user)?                               │
│     locked_until > datetime.utcnow() → HTTP 423            │
│  3. is_active? → HTTP 403 ACCOUNT_DISABLED                 │
│  4. is_verified? → HTTP 403 EMAIL_NOT_VERIFIED             │
│  5. verify_password(plain, hashed) — bcrypt compare        │
│     FAIL: failed_login_attempts += 1                       │
│     If attempts >= MAX_LOGIN_ATTEMPTS (5):                 │
│       locked_until = now + LOCKOUT_MINUTES (30 min)        │
│       Audit: ACCOUNT_LOCKED                                │
│       → HTTP 423 ACCOUNT_LOCKED                            │
│  6. SUCCESS: reset failed_login_attempts = 0               │
│     Update last_login, last_active                         │
│  7. create_access_token(user_id, username, role)           │
│     Payload: { sub, username, role, exp, type, jti }       │
│     HS256 signed, expires in ACCESS_TOKEN_EXPIRE_MINUTES   │
│  8. create_refresh_token(user_id)                          │
│     Expires in REFRESH_TOKEN_EXPIRE_DAYS (7 days)          │
│  9. Audit: USER_LOGIN                                      │
│  Return: TokenResponse { access_token, refresh_token,      │
│                           expires_in, user_profile }       │
└────────────────────────────────────────────────────────────┘
```

### 8.3 Request Authentication Flow (Every Protected Endpoint)

```
HTTP Request with Authorization: Bearer <token>
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  get_current_user (FastAPI Dependency)                     │
│  1. HTTPBearer extracts token from header                  │
│  2. decode_token(token):                                   │
│     jwt.decode(token, SECRET_KEY, HS256)                   │
│     → HTTP 401 on JWTError                                 │
│  3. Check payload["type"] == "access"                      │
│  4. DB lookup: User.id == payload["sub"]                   │
│  5. user.is_active? user.is_verified? is_account_locked?   │
│  6. Return User ORM object to route handler                │
└────────────────────────────────────────────────────────────┘
```

### 8.4 Frontend Session Management (Next.js Middleware)

```
Every browser request to /*.tsx page
             │
             ▼
┌────────────────────────────────────────────────────────────┐
│  middleware.ts                                             │
│  1. Is path in PUBLIC_PATHS? (/login, /register, /verify-otp│
│     → NextResponse.next() (allow through)                  │
│  2. Is Next.js internal? (/_next, /favicon, ...)           │
│     → NextResponse.next()                                  │
│  3. Read cookies.get("access_token")                       │
│     → No token: redirect to /login?redirect={pathname}     │
│  4. Path starts with /admin?                               │
│     → Read cookies.get("user_role")                        │
│     → Not "admin": redirect to /?unauthorized=1            │
│  5. Attach x-user and x-role headers to request            │
│  6. NextResponse.next()                                    │
└────────────────────────────────────────────────────────────┘
```

---

## 9. Multi-Provider LLM Router

The LLM Router is a key architectural component that abstracts away provider differences and reads configuration from a runtime-editable store (not just env vars).

### 9.1 Provider Routing Logic

```python
Provider Selection (at query time):
  llm_config_store.provider → "gemini" | "groq" | "openai" | "ollama"
  llm_config_store.model    → e.g. "gemini-2.0-flash"
  llm_config_store.get_api_key() → key from runtime store

  if provider == "gemini":
    POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}
    Payload: { system_instruction, contents, generationConfig: {temp:0.2, maxTokens:2048} }

  elif provider == "groq":
    POST https://api.groq.com/openai/v1/chat/completions
    OpenAI-compatible format with Bearer auth

  elif provider == "openai":
    POST https://api.openai.com/v1/chat/completions
    Standard chat completions format

  elif provider == "ollama":
    POST http://localhost:11434/api/generate
    System prompt prepended to user prompt (no chat format)

  Fallback: _mock_response() with keyword-matched SWIFT snippets
```

### 9.2 Retry Mechanism

```python
async def _retry_async(coro_fn, max_attempts=3, base_delay=1.0):
    for attempt in range(3):
        try:
            return await coro_fn()
        except Exception:
            wait = 1.0 * (2 ** attempt)  # 1s, 2s, 4s
            await asyncio.sleep(wait)
    raise last_exc
```

### 9.3 System Prompt Capabilities

The `FINANCIAL_SYSTEM_PROMPT` bakes in:
- CBPR+ R2025 mandatory rules (UETR, ChrgBr, PostalAddress, SvcLvl)
- MT vs MX terminology distinctions
- Reference to exact XML element paths in answers
- Version-awareness: when `selected_versions` provided, instructs the LLM to clearly flag R2025 vs R2024 differences using `"⚠️ Changed in [VERSION]: ..."` format

---

## 10. Service Layer — Core Functionality Deep Dive

### 10.1 `mt_parser.py` — SWIFT MT Field Parser

**Core Design**: Deterministic regex-based parsing, no ML needed.

- **Block extraction**: Regex `\{(\d):(.*?)\}` finds SWIFT blocks 1–5
- **Tag extraction**: Regex `^:(\d{1,2}[A-Z]?C?):` split positions, reads values between tag starts
- **Field resolution**: Dict mapping of tag codes → semantic field names (per MT type)
- **Supported types**: MT103, MT103STP, MT202, MT202COV, MT204, MT103RETURN, MT202RETURN
- **Key CBPR+ field**: Extracts UETR from Block 3 field `{121:}` if present

### 10.2 `mx_translator.py` — MT to MX Translator

**Core Design**: Deterministic rule-based XML generation using lxml.

Key functions:
- `_parse_32a(value)` — Parses `:32A:` format `YYMMDDCCCAMOUNT,CENTS` → `(iso_date, currency, decimal_amount)`
- `_add_postal_address_r2025(parent, raw_address)` — Parses free-text address, extracts ISO country code, emits TwnNm + Ctry + AdrLine (hybrid mode)
- `_bic_from_field(value)` — Extracts BIC from first whitespace-delimited token, strips leading `/`
- `_PACS008_CHRGBR_MAP` — Maps SHA→SHAR, OUR→SHAR, BEN→SHAR (R2025 rule)

### 10.3 `validator.py` — ISO 20022 Validator

**Two-tier validation**:
1. **XSD structural**: Loads `.xsd` files from `data/xsd/` directory, cached per process. Falls back to structural-only if XSD not found.
2. **CBPR+ R2025 Business Rules**: XPath-based checks using `lxml.etree` namespace-aware queries

**Error taxonomy**:
- `[XSD]` — Schema violations
- `[RULE:CBPR+R2025]` — Hard compliance violations (counted as errors)
- `[WARN:CBPR+R2025]` — Recommendations (appended but not counted as errors)

### 10.4 `rag_pipeline.py` — RAG Pipeline

**Design**: Two independent lazy singletons (embed model + ChromaDB client) initialized on first use to avoid startup latency.

- **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` — 384-dim, runs on CPU, ~80MB
- **ChromaDB**: Persistent client, HNSW cosine space, collection: `compliance_docs`
- **Chunking strategy**: 512-word chunks with 64-word overlap (word-level approximation of tokens)
- **Batch upsert**: 256 chunks per ChromaDB batch (avoids payload size limits)
- **Version filtering**: ChromaDB `where` clause with `$eq` (single) or `$in` (multiple versions)

### 10.5 `audit_logger.py` — Hash-Chained Audit Logger

**Design**: Singleton with per-write file append (no open file handles kept persistent). Chain is re-seeded from disk on first write after restart.

- **Genesis hash**: `SHA256("")` = `e3b0c44298fc1c149...`
- **Chain formula**: `SHA256(prev_hash + entry_json_no_hash)`
- **PII masking regexes**: IBAN pattern + 8+ digit account numbers
- **File rotation**: One file per calendar day (`compliance_audit_YYYY-MM-DD.ndjson`)
- **Export**: Concatenates all daily files into `audit_export_YYYYMMDDTHHMMSSZ.ndjson`

### 10.6 `telemetry_bus.py` — WebSocket Pub-Sub Hub

- **Client set**: `Set[WebSocket]` — in-memory, process-scoped
- **Dead client cleanup**: Checked on every broadcast, stale connections removed
- **Event schema**: `event_id` (UUID4), `timestamp`, `event_type`, `module` (1-4), `severity` (INFO/WARN/ERROR), `summary`, `data`
- **Module codes**: 1=Translate, 2=Learn, 3=Documents, 4=Audit

---

## 11. Frontend Architecture & Component Flow

### 11.1 Page Structure

```
/app/
├── layout.tsx          ← Root layout: Sidebar + TopBar + children
├── page.tsx            ← Dashboard: stats, quick translate, live telemetry, audit preview
├── translate/          ← Full MT→MX translation UI
├── learn/              ← LLM Q&A + topic explorer
├── documents/          ← Document upload + query
├── audit/              ← Full audit log viewer + export
├── admin/              ← User management (admin only)
├── login/              ← Login form
├── register/           ← Registration form
└── verify-otp/         ← OTP verification
```

### 11.2 Key Components

| Component | Purpose |
|-----------|---------|
| `Sidebar.tsx` | Navigation: module links, active route highlighting, LLM config panel toggle |
| `TopBar.tsx` | User profile, logout, system status indicator |
| `TelemetryFeed.tsx` | WebSocket consumer: renders live event stream with severity colors |
| `AuditTable.tsx` | Paginated, filterable audit log table |
| `DocumentUploader.tsx` | Drag-and-drop + file picker, upload progress, indexed chunk display |
| `ValidationBadge.tsx` | Color-coded validation status badge with error detail popover |
| `LLMConfigPanel.tsx` | Runtime LLM provider/model/API key editor (slide-in panel) |
| `GuidelineSelector.tsx` | Multi-select guideline version picker with cross-compare toggle |

### 11.3 Auth State (Frontend)

Token management uses **HTTP cookies** (not localStorage):
- `access_token` — JWT access token (read by middleware)
- `refresh_token` — stored for token refresh
- `user_role` — "admin" | "analyst" (used by middleware for /admin protection)
- `username` — current user identifier

The Next.js middleware reads these cookies on every navigation to guard routes.

---

## 12. Database & Persistence Design

### 12.1 SQLite User Database

**Location**: `data/compliance.db`
**Engine**: SQLAlchemy (sync for DDL, async for queries via aiosqlite)

**Users Table Schema**:

| Column | Type | Description |
|--------|------|-------------|
| `id` | String (UUID4) | Primary key |
| `username` | String (unique) | Lowercased, 3-30 chars |
| `email` | String (unique) | Validated EmailStr |
| `full_name` | String (nullable) | Display name |
| `hashed_password` | String | bcrypt (cost 12) hash |
| `role` | String | "admin" or "analyst" |
| `is_active` | Boolean | Can be disabled by admin |
| `is_verified` | Boolean | Email OTP verified |
| `otp_code` | String (nullable) | bcrypt-hashed OTP (not plaintext!) |
| `otp_expires_at` | DateTime | OTP expiry (10 min window) |
| `otp_attempts` | Integer | Wrong OTP counter (max 3) |
| `otp_resend_count` | Integer | Resend counter (max 3) |
| `failed_login_attempts` | Integer | Login fail counter (max 5) |
| `locked_until` | DateTime | Account lockout expiry |
| `must_change_password` | Boolean | Force password change flag |
| `password_changed_at` | DateTime | Last password change time |
| `created_at` | DateTime | Account creation UTC |
| `last_login` | DateTime | Last successful login UTC |
| `last_active` | DateTime | Last activity UTC |
| `created_by` | String | "self" or admin username |

### 12.2 ChromaDB Vector Store

**Location**: `data/chroma/`
**Collection**: `compliance_docs`
**Distance metric**: Cosine similarity (HNSW index)

**Chunk metadata stored per vector**:
- `doc_id` — UUID4 document identifier
- `filename` — Original uploaded filename
- `chunk_index` — Position within document
- `page_num` — Source page/slide number
- `guideline_version` — e.g., "CBPR+ R2025", "CBPR+ R2024"
- `guideline_category` — e.g., "SWIFT Standards", "Regulatory"
- `tags` — Free-text tags for additional filtering

### 12.3 Audit Log Files

**Location**: `data/audit/`
**Format**: NDJSON (Newline-Delimited JSON)
**Naming**: `compliance_audit_YYYY-MM-DD.ndjson`

Each line is a complete JSON object with this structure:
```json
{
  "audit_id": "uuid4",
  "timestamp": "2026-07-19T18:00:00.000000+00:00",
  "event_type": "TRANSLATION",
  "module": "translate",
  "status": "SUCCESS",
  "uetr": "uuid4-or-null",
  "message_type": "pacs.008.001.08",
  "details": { "source_type": "MT103", "validation_errors": [] },
  "hash": "sha256hex"
}
```

---

## 13. Security Design Decisions

| Security Control | Implementation | Rationale |
|-----------------|----------------|-----------|
| **Password hashing** | bcrypt, cost factor 12 | Industry standard for password storage; cost 12 = ~250ms on modern hardware |
| **OTP hashing** | bcrypt (same context) | OTPs are also stored hashed — not in plaintext |
| **JWT signing** | HS256, configurable SECRET_KEY | Stateless session management; JTI (JWT ID) included for future revocation |
| **Token types** | Separate access (60min) + refresh (7d) tokens | Limits exposure window of stolen access tokens |
| **Account lockout** | 5 failed attempts → 30 minute lockout | Prevents brute-force attacks |
| **OTP rate limits** | Max 3 attempts, max 3 resends | Prevents OTP brute force and spam |
| **PII masking** | Regex on full JSON before write | Belt-and-suspenders approach; IBANs and account numbers never appear in audit logs |
| **SHA-256 hash chain** | Each entry chains from previous | Makes retroactive tampering detectable without a central authority |
| **CORS** | Explicit origin whitelist | Prevents unauthorized cross-origin requests |
| **Admin seeding** | must_change_password=True | Forces admin to set a new password on first login |
| **Middleware guard** | Cookie-based auth check on every Next.js route | Prevents browser-side route bypassing |
| **No stack traces in API** | Global exception handler returns generic message | Prevents information leakage |

---

## 14. API Endpoint Reference

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/auth/register` | None | Register new user, send OTP |
| `POST` | `/api/v1/auth/verify-otp` | None | Verify email OTP |
| `POST` | `/api/v1/auth/resend-otp` | None | Resend OTP (max 3) |
| `POST` | `/api/v1/auth/login` | None | Login → access + refresh tokens |
| `POST` | `/api/v1/auth/refresh` | None | Exchange refresh → access token |
| `POST` | `/api/v1/auth/logout` | User | Logout (audit log entry) |
| `GET` | `/api/v1/auth/me` | User | Current user profile |
| `POST` | `/api/v1/auth/change-password` | User | Change own password |
| `POST` | `/api/v1/translate` | Public | MT → ISO 20022 XML translation |
| `POST` | `/api/v1/validate` | Public | Validate ISO 20022 XML |
| `GET` | `/api/v1/translate/sample/{type}` | Public | Get sample MT message |
| `POST` | `/api/v1/learn` | User | LLM domain Q&A |
| `GET` | `/api/v1/learn/topics` | Public | List learning topics |
| `POST` | `/api/v1/documents/upload` | User | Upload compliance document |
| `POST` | `/api/v1/documents/query` | User | Query indexed documents |
| `GET` | `/api/v1/documents/list` | User | List all indexed documents |
| `DELETE` | `/api/v1/documents/{doc_id}` | Admin | Delete document from vector store |
| `GET` | `/api/v1/audit/logs` | User | Paginated audit log |
| `GET` | `/api/v1/audit/export` | Admin | Export full audit bundle |
| `GET` | `/api/v1/llm-config` | Admin | Get current LLM config |
| `PUT` | `/api/v1/llm-config` | Admin | Update LLM provider/model/key |
| `GET` | `/api/v1/guidelines` | User | List guideline versions |
| `POST` | `/api/v1/admin/users` | Admin | Create user |
| `GET` | `/api/v1/admin/users` | Admin | List all users |
| `PATCH` | `/api/v1/admin/users/{id}` | Admin | Update user |
| `DELETE` | `/api/v1/admin/users/{id}` | Admin | Delete user |
| `WS` | `/ws/telemetry` | Public | Real-time telemetry stream |
| `GET` | `/health` | Public | System health check |
| `GET` | `/api/docs` | Public | Swagger UI |

---

## 15. Deployment — Docker Compose

```yaml
# docker-compose.yml
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    volumes:
      - ./data:/app/data    ← Persists SQLite, ChromaDB, audit logs, uploads
    healthcheck:
      test: curl -f http://localhost:8000/health
      interval: 30s

  frontend:
    build: ./frontend
    ports: ["3000:3000"]
    depends_on: [backend]
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
      NEXT_PUBLIC_WS_URL: ws://localhost:8000

networks:
  compliance_net: { driver: bridge }
```

**Environment Configuration** (`.env`):
```bash
LLM_PROVIDER=gemini                    # gemini | openai | groq | ollama
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-2.0-flash
SECRET_KEY=your-256bit-random-key
SMTP_USERNAME=your@gmail.com
SMTP_PASSWORD=16char-app-password
ADMIN_USERNAME=admin
ADMIN_PASSWORD=ChangeMe@123
```

---

## 16. Resume Description

### Short Version (1–2 lines)

> Built **The Compliance Leader**, a full-stack ISO 20022 / SWIFT compliance platform (FastAPI + Next.js) featuring deterministic MT→MX message translation enforcing CBPR+ R2025 rules, a RAG-powered document intelligence system using ChromaDB + sentence-transformers, multi-provider LLM routing (Gemini/OpenAI/Groq/Ollama), and a tamper-evident SHA-256 hash-chained audit logger with real-time WebSocket telemetry.

---

### Medium Version (3–5 lines for Resume Bullet Points)

> - Architected a production-grade **SWIFT-to-ISO 20022 compliance platform** (FastAPI, Next.js 14, Python 3.12) serving compliance officers and payment engineers during the CBPR+ R2025 migration mandate.
> - Built a **deterministic MT→MX translator** enforcing 7+ CBPR+ R2025 rules: mandatory UETR (UUID4), ChrgBr=SHAR normalization, hybrid PostalAddress, and prohibited-field guards — returns structured HTTP 422 `SWIFT_ISO_MUTATION_DENIED` on violations.
> - Implemented a **multi-format RAG pipeline** (PDF/PPTX/DOCX/XML ingestion → sentence-transformers embedding → ChromaDB vector store → LLM synthesis) with version-aware filtering and cross-version comparison mode across guideline standards.
> - Designed a **banking-grade auth system** (bcrypt cost 12, JWT access + refresh tokens, bcrypt-hashed OTP, 5-attempt lockout) with a SHA-256 hash-chained, PII-masked, append-only audit logger and real-time WebSocket telemetry dashboard.
> - Built a **multi-provider LLM router** (Gemini, OpenAI, Groq, Ollama) with exponential-backoff retry logic, runtime config swap without restart, and graceful mock fallback for development without API keys.

---

### Full Version (LinkedIn / Portfolio Description)

**The Compliance Leader** is an enterprise-grade compliance automation platform I built in response to the SWIFT CBPR+ R2025 mandate (effective November 22, 2025), which retired legacy SWIFT MT103/MT202/MT202COV messages from SWIFT FINplus and required migration to ISO 20022 XML format across global interbank payment networks.

**What it does:**

The platform provides four deeply integrated modules:

1. **TX Translation & Validation Engine**: A deterministic, rule-based SWIFT MT → ISO 20022 XML translator that enforces CBPR+ R2025 compliance at every stage. It parses raw SWIFT MT message block structures (blocks 1–5) using regex, resolves tagged fields (`:20:`, `:32A:`, `:50K:`, etc.) by message type, then generates standards-compliant lxml XML trees enforcing mandatory UETR (UUID4), SHAR charge bearer normalization, hybrid postal address formatting, and prohibited-field guards. All generated XML is then run through a two-tier validator (XSD schema + CBPR+ business rules) and returns structured error messages prefixed by rule category.

2. **Interactive Learning System**: An AI-powered Q&A engine that routes questions about ISO 20022, SWIFT messaging, clearing systems, and CBPR+ rules to any of four LLM providers (Gemini, OpenAI, Groq, Ollama). When compliance documents are indexed, it uses a RAG (Retrieval-Augmented Generation) pipeline — embedding questions with `all-MiniLM-L6-v2`, querying ChromaDB with cosine similarity, and synthesizing grounded answers. It also supports cross-version comparison mode that queries each guideline version independently and produces a unified comparison highlighting differences.

3. **Document Intelligence (RAG Pipeline)**: A multi-format document ingestion system that extracts text from PDFs (PyMuPDF), PowerPoints (python-pptx), Word documents (python-docx), and XML/TXT files, chunks them into 512-word overlapping windows, embeds them with sentence-transformers, and stores them in ChromaDB with rich metadata (guideline version, category, tags, page numbers). Users can query their document corpus with natural language and receive LLM-synthesized answers with source citations.

4. **Audit & Telemetry**: Every operation generates a SHA-256 hash-chained audit log entry written to append-only NDJSON files (one per day). Each entry chains from the previous entry's hash, making retroactive tampering detectable. PII (IBANs, account numbers) is masked via regex before any write. A real-time WebSocket telemetry bus broadcasts events to all connected dashboard clients instantly.

**Technical highlights:**
- FastAPI async architecture with structured logging (structlog JSON)
- Banking-grade authentication: bcrypt (cost 12), OTP hashing, JWT with JTI, account lockout, forced password rotation
- Multi-provider LLM abstraction with exponential-backoff retry (3 attempts) and graceful degradation to mock mode
- Next.js 14 App Router frontend with cookie-based auth guards in middleware
- Docker Compose one-command deployment with health checks and shared data volumes
- Full CBPR+ R2025 compliance coverage: 24 return reason codes, 7+ translation guards, hybrid PostalAddress enforcement

---

*This document was generated from a complete codebase analysis. Last updated: 2026-07-19.*
