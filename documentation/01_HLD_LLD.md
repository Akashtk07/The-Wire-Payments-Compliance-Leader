# The Compliance Leader — High-Level Design (HLD) & Low-Level Design (LLD)

> **Document Type:** Technical Architecture Document  
> **Version:** 1.0.0  
> **Platform:** The Compliance Leader — Cross-Border Regulatory Lineage, Translation Validation, Document Intelligence & Real-Time Telemetry Platform  
> **Date:** May 2026  
> **Classification:** Internal — Engineering

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [High-Level Design (HLD)](#2-high-level-design-hld)
   - 2.1 System Overview
   - 2.2 Architectural Principles
   - 2.3 System Context Diagram
   - 2.4 Module Architecture
   - 2.5 Technology Stack
   - 2.6 Deployment Architecture
3. [Low-Level Design (LLD)](#3-low-level-design-lld)
   - 3.1 Backend Service Decomposition
   - 3.2 API Design
   - 3.3 Data Models
   - 3.4 Translation Engine — Deterministic Processing Pipeline
   - 3.5 Audit Logger — Hash-Chain Design
   - 3.6 LLM Router — Multi-Provider Architecture
   - 3.7 RAG Pipeline — Document Intelligence
   - 3.8 Telemetry Bus — WebSocket Architecture
   - 3.9 LLM Config Store — Runtime Hot-Swap
4. [Sequence Diagrams](#4-sequence-diagrams)
5. [Data Flow Diagrams](#5-data-flow-diagrams)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [Security Architecture](#7-security-architecture)

---

## 1. Executive Summary

**The Compliance Leader** is a production-grade institutional financial compliance platform built to serve the ISO 20022 / SWIFT CBPR+ migration era. It provides four tightly integrated modules:

| Module | Purpose |
|--------|---------|
| **TX Engine** | Deterministic SWIFT MT → ISO 20022 MX translation with CBPR+ validation |
| **Knowledge** | AI-powered LLM Q&A on ISO 20022, SWIFT, clearing and settlement |
| **Documents** | RAG-powered document intelligence (upload PDFs, query with AI) |
| **Audit & Telemetry** | Tamper-evident hash-chained audit log + real-time WebSocket telemetry |

The platform is built on a **FastAPI (Python 3.13)** backend with a **Next.js 14 (TypeScript)** frontend, communicating exclusively over HTTP/JSON REST APIs and WebSocket for real-time events.

---

## 2. High-Level Design (HLD)

### 2.1 System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                     THE COMPLIANCE LEADER                           │
│                   Enterprise Compliance Platform                    │
├─────────────────┬───────────────────────────────────────────────────┤
│   FRONTEND      │                  BACKEND                          │
│  Next.js 14     │  FastAPI 0.115 + Python 3.13                      │
│  TypeScript     │                                                   │
│  Vanilla CSS    │  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────┐  │
│                 │  │  TX Eng  │ │Knowledge │ │  Docs  │ │ Audit │  │
│  5 Pages:       │  │ /translate│ │  /learn  │ │  /docs │ │/audit │  │
│  • Dashboard    │  └──────────┘ └──────────┘ └────────┘ └───────┘  │
│  • TX Engine    │       │            │             │          │     │
│  • Knowledge    │  ┌────▼────────────▼─────────────▼──────────▼──┐ │
│  • Documents    │  │         SERVICE LAYER                        │ │
│  • Audit        │  │  mt_parser  │  mx_translator │  validator    │ │
│                 │  │  llm_router │  rag_pipeline  │  audit_logger │ │
│  6 Components:  │  │  llm_config_store             │  telemetry_bus│ │
│  • Sidebar      │  └────────────────────────────────────────────┘  │
│  • TopBar       │                      │                            │
│  • TelemetryFeed│  ┌───────────────────▼───────────────────────┐   │
│  • AuditTable   │  │         EXTERNAL INTEGRATIONS             │   │
│  • LLMConfigPanel│ │  Gemini REST │ Groq REST │ OpenAI │ Ollama │   │
│  • others...    │  │  ChromaDB    │ aiofiles  │ httpx          │   │
└─────────────────┴──┴───────────────────────────────────────────┴───┘
         │                            │
         └────────── HTTP/WS ─────────┘
              localhost:3000 → :8000
```

### 2.2 Architectural Principles

| Principle | Implementation |
|-----------|---------------|
| **Separation of Concerns** | Router → Service → External — each layer has a single responsibility |
| **Async-First** | All I/O (HTTP, file, ChromaDB) is `async/await` via Python asyncio |
| **Zero-Dependency AI** | All LLM calls via pure `httpx` REST — no `grpcio`, no heavy SDK |
| **Lazy Loading** | Heavy ML dependencies (ChromaDB, torch) loaded only on first use |
| **Tamper-Evidence** | SHA-256 hash chain on every audit entry |
| **PII Safety** | IBAN and account numbers masked before persistence |
| **Runtime Configurability** | LLM provider/model/key hot-swappable without server restart |
| **Graceful Degradation** | Every external call wrapped in try/except with informative fallback |

### 2.3 System Context Diagram

```mermaid
C4Context
    title System Context — The Compliance Leader

    Person(compliance, "Compliance Officer", "Uses TX Engine and Audit module")
    Person(engineer, "Payment Engineer", "Uses Knowledge and TX Engine")
    Person(analyst, "Financial Analyst", "Uses Documents and Knowledge")

    System(platform, "The Compliance Leader", "ISO 20022 compliance, translation, AI knowledge, audit")

    System_Ext(gemini, "Google Gemini API", "LLM inference (gemini-2.0-flash)")
    System_Ext(groq, "Groq Cloud API", "LLM inference (llama-3.3-70b)")
    System_Ext(openai, "OpenAI API", "LLM inference (gpt-4o)")
    System_Ext(ollama, "Ollama (Local)", "On-premise LLM inference")

    Rel(compliance, platform, "Submits MT messages, reviews audit logs")
    Rel(engineer, platform, "Queries knowledge, uploads standards docs")
    Rel(analyst, platform, "Queries uploaded documents, reviews telemetry")

    Rel(platform, gemini, "REST API — generateContent")
    Rel(platform, groq, "REST API — chat/completions")
    Rel(platform, openai, "REST API — chat/completions")
    Rel(platform, ollama, "REST API — /api/generate")
```

### 2.4 Module Architecture

```mermaid
graph TB
    subgraph "Frontend — Next.js 14"
        P1[Command Center<br/>Dashboard]
        P2[TX Engine<br/>Translate + Validate]
        P3[Knowledge<br/>AI Q&A]
        P4[Documents<br/>RAG Intelligence]
        P5[Audit & Telemetry<br/>Logs + LiveFeed]
        CFG[LLM Config Panel<br/>Provider/Model/Key]
    end

    subgraph "Backend — FastAPI"
        R1[translate router<br/>/api/v1/translate]
        R2[learn router<br/>/api/v1/learn]
        R3[documents router<br/>/api/v1/documents]
        R4[audit router<br/>/api/v1/audit]
        R5[llm_config router<br/>/api/v1/llm-config]
        WS[WebSocket<br/>/ws/telemetry]
    end

    subgraph "Service Layer"
        S1[mt_parser]
        S2[mx_translator]
        S3[validator]
        S4[llm_router]
        S5[llm_config_store]
        S6[rag_pipeline]
        S7[audit_logger]
        S8[telemetry_bus]
    end

    P1 & P2 --> R1
    P3 --> R2
    P4 --> R3
    P5 --> R4 & WS
    CFG --> R5

    R1 --> S1 --> S2 --> S3
    R2 --> S4 --> S5
    R3 --> S6
    R4 --> S7
    WS --> S8
    S4 & S6 --> S8
    S1 & S2 & S3 & S4 & S6 --> S7
```

### 2.5 Technology Stack

#### Backend

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Framework | FastAPI | 0.115.x | Async REST API + WebSocket |
| Runtime | Python | 3.13 | Application runtime |
| ASGI Server | Uvicorn | 0.34.x | Production ASGI server with hot-reload |
| Settings | Pydantic-Settings | 2.x | Type-safe configuration from .env |
| HTTP Client | httpx | 0.28.x | Async HTTP for LLM REST calls |
| File I/O | aiofiles | 24.x | Non-blocking file writes for audit log |
| Logging | structlog | 24.x | Structured JSON logging |
| Validation | Pydantic v2 | 2.x | Request/response schema validation |
| ML/Vector DB | ChromaDB | 0.6.x | Vector store (lazy-loaded) |
| Embeddings | sentence-transformers | — | Document chunk embeddings (lazy-loaded) |
| XML | lxml | 5.x | XSD validation of ISO 20022 XML |

#### Frontend

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Framework | Next.js | 14.x | React SSR/CSR hybrid |
| Language | TypeScript | 5.x | Type safety |
| Styling | Vanilla CSS | — | Custom design system (no Tailwind) |
| Icons | Lucide-React | 0.4x | SVG icon library |
| Fonts | Inter + JetBrains Mono | — | Google Fonts |
| HTTP | fetch API | native | API calls from components |
| Real-time | WebSocket (native) | native | Telemetry stream |

### 2.6 Deployment Architecture

```mermaid
graph LR
    subgraph "Developer Machine"
        subgraph "Frontend Container :3000"
            NEXT[Next.js Dev Server<br/>npm run dev]
        end
        subgraph "Backend Container :8000"
            UVCN[Uvicorn<br/>uvicorn main:app --reload]
            subgraph "Data Layer"
                AUDIT[data/audit/<br/>NDJSON files]
                UPLOAD[data/uploads/<br/>PDF files]
                CHROMA[data/chroma/<br/>Vector store]
                XSD[data/xsd/<br/>ISO 20022 XSD]
            end
        end
        subgraph "Config"
            ENV[.env file<br/>API keys + settings]
        end
    end

    BROWSER[Browser<br/>localhost:3000] --> NEXT
    NEXT -->|HTTP /api/v1/*| UVCN
    NEXT -->|WS /ws/telemetry| UVCN
    UVCN --> AUDIT & UPLOAD & CHROMA & XSD
    ENV --> UVCN
```

---

## 3. Low-Level Design (LLD)

### 3.1 Backend Service Decomposition

```
backend/
├── main.py                     ← FastAPI app factory, lifespan, CORS, health endpoint
├── config.py                   ← Pydantic-settings + built-in .env loader
├── models/
│   └── schemas.py              ← All Pydantic v2 request/response models
├── routers/
│   ├── translate.py            ← POST /translate, POST /validate, GET /sample/{type}
│   ├── learn.py                ← POST /learn, GET /learn/topics
│   ├── documents.py            ← POST /documents/upload, POST /documents/query, GET /documents
│   ├── audit.py                ← GET /audit/logs, GET /audit/export, WS /ws/telemetry
│   └── llm_config.py           ← GET/POST /llm-config, GET /llm-config/history, POST /test
└── services/
    ├── mt_parser.py            ← SWIFT MT block/field parser (regex-based, deterministic)
    ├── mx_translator.py        ← ISO 20022 XML generator (pacs.008/009/004)
    ├── validator.py            ← XSD + CBPR+ business rule validator
    ├── llm_router.py           ← Multi-provider LLM dispatcher (Gemini/Groq/OpenAI/Ollama)
    ├── llm_config_store.py     ← In-memory runtime LLM config with 25-entry history
    ├── rag_pipeline.py         ← PDF ingestion → chunking → embedding → ChromaDB
    ├── audit_logger.py         ← Append-only NDJSON, SHA-256 hash chain, PII masking
    └── telemetry_bus.py        ← WebSocket hub, broadcast to all connected clients
```

### 3.2 API Design

#### REST Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | System health check (all modules) |
| `POST` | `/api/v1/translate` | None | MT → MX translation |
| `POST` | `/api/v1/validate` | None | ISO 20022 XML validation |
| `GET` | `/api/v1/translate/sample/{type}` | None | Get sample MT messages |
| `POST` | `/api/v1/learn` | None | LLM domain Q&A |
| `GET` | `/api/v1/learn/topics` | None | List knowledge topics |
| `POST` | `/api/v1/documents/upload` | None | Upload PDF for RAG indexing |
| `POST` | `/api/v1/documents/query` | None | RAG-powered document Q&A |
| `GET` | `/api/v1/documents` | None | List uploaded documents |
| `GET` | `/api/v1/audit/logs` | None | Paginated audit log retrieval |
| `GET` | `/api/v1/audit/export` | None | Export full NDJSON audit bundle |
| `GET` | `/api/v1/llm-config` | None | Get current LLM configuration |
| `POST` | `/api/v1/llm-config` | None | Update LLM provider/model/key |
| `GET` | `/api/v1/llm-config/history` | None | Last 25 config changes |
| `GET` | `/api/v1/llm-config/models` | None | All providers + model catalogues |
| `POST` | `/api/v1/llm-config/test` | None | Test current LLM config |
| `WS` | `/ws/telemetry` | None | Real-time event stream |

#### OpenAPI Documentation
Available at: `http://localhost:8000/api/docs` (Swagger UI)  
ReDoc: `http://localhost:8000/api/redoc`

### 3.3 Data Models

#### Request Models

```python
# Translation Request
MTTranslateRequest:
    mt_raw: str           # Raw SWIFT MT string with block delimiters
    source_type: Literal["MT103", "MT103STP", "MT202", "MT202COV", "MT204",
                          "MT103RETURN", "MT202RETURN"]
    target_type: Optional[str]  # Override auto-detected ISO 20022 target

# Learn (LLM Q&A) Request
LearnRequest:
    query: str            # Financial domain question (min 3 chars)
    context: Optional[str]  # Optional XML snippet to anchor response

# Document Query Request
DocumentQueryRequest:
    query: str            # Natural-language question
    top_k: int            # Number of chunks to retrieve (1–20, default 5)

# LLM Config Update Request
LLMConfigUpdateRequest:
    provider: Optional[str]         # gemini | groq | openai | ollama
    model: Optional[str]            # Model ID
    api_key: Optional[str]          # API key (masked in responses)
    ollama_base_url: Optional[str]  # Ollama server URL
```

#### Response Models

```python
# Translation Response
TranslationResponse:
    status: str                  # SUCCESS | PARTIAL | ERROR
    message_type: str            # e.g. pacs.008.001.08
    xml_output: Optional[str]    # Generated ISO 20022 XML
    uetr: Optional[str]          # Unique End-to-end Transaction Reference
    validation_errors: List[str] # CBPR+ / XSD errors (empty if clean)
    audit_id: str                # Audit log entry ID
    timestamp: str               # ISO 8601

# Audit Log Entry
AuditLogEntry:
    audit_id: str        # UUID4
    timestamp: str       # ISO 8601
    event_type: str      # TRANSLATION | VALIDATION | LEARN_QUERY | DOCUMENT_UPLOAD
    module: str          # translate | learn | documents | audit
    status: str          # SUCCESS | ERROR | PARTIAL
    uetr: Optional[str]  # Payment UETR if applicable
    message_type: Optional[str]
    details: Dict        # PII-masked event details
    hash: str            # SHA-256 hash (chained)
```

### 3.4 Translation Engine — Deterministic Processing Pipeline

```mermaid
sequenceDiagram
    participant Client
    participant TranslateRouter
    participant MTParser
    participant MXTranslator
    participant Validator
    participant AuditLogger
    participant TelemetryBus

    Client->>TranslateRouter: POST /api/v1/translate {mt_raw, source_type}

    TranslateRouter->>MTParser: parse(mt_raw, source_type)
    Note over MTParser: Extract block 1/2/3/4<br/>Parse tagged fields (:20:,:32A:,:50K: etc.)<br/>Extract UETR from {121:}

    MTParser-->>TranslateRouter: parsed dict {uetr, amount, currencies, parties...}

    TranslateRouter->>MXTranslator: translate(parsed, source_type, target_type)
    Note over MXTranslator: Route: MT103→pacs.008<br/>MT202→pacs.009.CORE<br/>MT202COV→pacs.009.COV<br/>MT103RETURN→pacs.004

    alt ValidationException (SWIFT ISO mutation denied)
        MXTranslator-->>TranslateRouter: raise ValidationException
        TranslateRouter->>AuditLogger: log(status=VALIDATION_EXCEPTION)
        TranslateRouter-->>Client: HTTP 422 + remediation action
    end

    MXTranslator-->>TranslateRouter: (xml_string, message_type)

    TranslateRouter->>Validator: validate(xml_string, message_type)
    Note over Validator: XSD validation (if XSD file present)<br/>CBPR+ business rule checks<br/>UETR format check, mandatory fields

    Validator-->>TranslateRouter: (is_valid, [errors])

    TranslateRouter->>AuditLogger: log(TRANSLATION, status, uetr, errors)
    AuditLogger-->>TranslateRouter: audit_id

    TranslateRouter->>TelemetryBus: broadcast(TRANSLATION_COMPLETE event)

    TranslateRouter-->>Client: TranslationResponse {xml_output, uetr, validation_errors, audit_id}
```

#### MT → MX Mapping Table

| Source MT | Target MX | Description |
|-----------|-----------|-------------|
| MT103 | pacs.008.001.08 | Customer Credit Transfer |
| MT103STP | pacs.008.001.08 | Straight-Through Processing variant |
| MT202 | pacs.009.001.08 (CORE) | FI Credit Transfer — no retail fields |
| MT202COV | pacs.009.001.08 (COV) | Includes `<UndrlygCstmrCdtTrf>` block |
| MT204 | pacs.009.001.08 (ADV) | Direct Debit Advice |
| MT103RETURN | pacs.004.001.09 | Payment Return |
| MT202RETURN | pacs.004.001.09 | Payment Return (FI) |

#### CBPR+ Validation Rules Implemented

```
RULE-001: pacs.009 CORE must NOT contain InstructedAmt or retail debtor/creditor fields
RULE-002: pacs.009 COV MUST contain UndrlygCstmrCdtTrf block
RULE-003: UETR must be valid UUID4 format
RULE-004: IntrBkSttlmAmt must have valid ISO 4217 currency code
RULE-005: BIC codes must be 8 or 11 characters
RULE-006: pacs.004 must reference OrgnlUETR and OrgnlMsgId
RULE-007: Return reason code must be from external code set
```

### 3.5 Audit Logger — Hash-Chain Design

```mermaid
graph TD
    W1["Entry 1\nSHA256('')\n→ hash_1"]
    W2["Entry 2\nhash_1\n→ hash_2"]
    W3["Entry 3\nhash_2\n→ hash_3"]
    WN["Entry N\nhash_N-1\n→ hash_N"]

    W1 --> W2 --> W3 --> WN

    subgraph "NDJSON File Structure"
        F1["{audit_id, timestamp, event_type, module,<br/>status, uetr, message_type, details, hash}"]
    end

    subgraph "PII Masking"
        M1["IBAN: GB29NWBK60161331926819\n→ [MASKED]"]
        M2["Account: 40050010006012345678\n→ [MASKED]"]
    end

    subgraph "Daily Rotation"
        D1[compliance_audit_2026-05-24.ndjson]
        D2[compliance_audit_2026-05-25.ndjson]
    end
```

**Hash-Chain Algorithm:**
```
genesis_hash = SHA256("")
entry.hash   = SHA256(SHA256(prev_hash) + SHA256(json_string(entry_without_hash)))
```

This means tampering with **any** historical entry invalidates **all subsequent** entries — providing cryptographic tamper evidence.

### 3.6 LLM Router — Multi-Provider Architecture

```mermaid
graph TD
    QUERY["User Query\n+ Optional Context"] --> ROUTER["LLMRouter.query()"]
    ROUTER --> STORE["llm_config_store\n.provider / .model / .get_api_key()"]

    STORE --> G{Provider?}
    G -->|gemini| GEM["_query_gemini()\nPOST generativelanguage.googleapis.com\n/v1beta/models/{model}:generateContent"]
    G -->|groq| GROQ["_query_groq()\nPOST api.groq.com\n/openai/v1/chat/completions"]
    G -->|openai| OAI["_query_openai()\nPOST api.openai.com\n/v1/chat/completions"]
    G -->|ollama| OLL["_query_ollama()\nPOST localhost:11434\n/api/generate"]
    G -->|no key| MOCK["_mock_response()\nKeyword-matched educational snippet"]

    GEM & GROQ & OAI & OLL --> RETRY["_retry_async()\n3 attempts, exponential backoff\n1s → 2s → 4s"]
    RETRY --> RESP["Text Response"]
    RETRY -->|all fail| ERR["Error message with traceback hint"]
```

**Financial System Prompt (injected for all providers):**
```
"You are an expert financial systems educator specializing in ISO 20022,
SWIFT messaging, global clearing and settlement, and cross-border payment law.
You provide precise, structured, zero-fluff explanations..."
```

### 3.7 RAG Pipeline — Document Intelligence

```mermaid
graph LR
    subgraph "Ingestion"
        PDF[PDF Upload] --> PARSE[Text Extraction\nPyMuPDF / pdfminer]
        PARSE --> CHUNK[Chunking\n512 tokens, 64 overlap]
        CHUNK --> EMBED[Embedding\nsentence-transformers\nall-MiniLM-L6-v2]
        EMBED --> CHROMA[ChromaDB\nVector Store]
    end

    subgraph "Retrieval"
        Q[User Query] --> QEMBED[Query Embedding]
        QEMBED --> SEARCH[Similarity Search\ntop-k chunks]
        CHROMA --> SEARCH
        SEARCH --> CONTEXT[Retrieved Context]
    end

    subgraph "Generation"
        CONTEXT --> LLM[LLM Router\nwith context prepended]
        Q --> LLM
        LLM --> ANS[Grounded Answer\nwith source citations]
    end
```

### 3.8 Telemetry Bus — WebSocket Architecture

```mermaid
graph TD
    subgraph "Backend"
        TB["TelemetryBus\nSingleton"]
        CLIENTS["Set[WebSocket]\nConnected Clients"]
        TB --> CLIENTS
    end

    subgraph "Event Sources"
        E1[Translation Complete] --> TB
        E2[Validation Complete] --> TB
        E3[Learn Query Complete] --> TB
        E4[Document Indexed] --> TB
        E5[System Startup] --> TB
    end

    subgraph "Connected Frontend Clients"
        C1[Browser Tab 1\nTelemetryFeed Component]
        C2[Browser Tab 2]
    end

    TB -->|broadcast JSON| C1 & C2

    subgraph "Event Structure"
        EV["{event_id, timestamp,\nevent_type, module,\nseverity, summary, data}"]
    end
```

**WebSocket lifecycle:**
1. Client connects → `telemetry_bus.connect(ws)` → adds to `_clients` set
2. Server sends `CONNECTED` event with client info
3. On each platform event → `await telemetry_bus.broadcast(event_dict)`
4. Dead clients (disconnected) silently pruned during next broadcast
5. `WebSocketDisconnect` → `telemetry_bus.disconnect(ws)`

### 3.9 LLM Config Store — Runtime Hot-Swap

```mermaid
stateDiagram-v2
    [*] --> Initialised : init_from_settings()\nat application startup

    Initialised --> Active : First query

    Active --> Active : query() reads\ncurrent provider/model/key

    Active --> Updated : POST /api/v1/llm-config\n{provider, model, api_key}

    Updated --> Active : Change applied\nHistory entry recorded

    note right of Updated
        History deque(maxlen=25)
        Masked key stored
        Timestamp recorded
        Changed_by="frontend"
    end note
```

---

## 4. Sequence Diagrams

### 4.1 End-to-End MT103 Translation Flow

```mermaid
sequenceDiagram
    actor User as Compliance Officer
    participant FE as Frontend<br/>TX Engine Page
    participant BE as Backend<br/>/api/v1/translate
    participant MT as MTParser
    participant MX as MXTranslator
    participant VAL as Validator
    participant AUDIT as AuditLogger
    participant WS as WebSocket<br/>TelemetryBus

    User->>FE: Paste MT103, click Translate
    FE->>BE: POST /translate {mt_raw, "MT103"}

    BE->>MT: parse(mt_raw, "MT103")
    MT->>MT: Extract :20:, :32A:, :50K:, :57A:, :59:, :70:, :71A:
    MT->>MT: Extract UETR from block 3 {121:} if present
    MT-->>BE: {uetr, amount, ccy, debtor, creditor, ...}

    BE->>MX: translate(parsed, "MT103", None)
    MX->>MX: Build pacs.008.001.08 XML\nMap fields to ISO 20022 elements
    MX-->>BE: (xml_string, "pacs.008.001.08")

    BE->>VAL: validate(xml_string, "pacs.008.001.08")
    VAL->>VAL: Check XSD schema\nApply CBPR+ rules
    VAL-->>BE: (True, [])  ← clean

    BE->>AUDIT: log(TRANSLATION, SUCCESS, uetr=..., message_type=pacs.008)
    AUDIT->>AUDIT: Hash chain entry\nMask PII\nAppend to NDJSON
    AUDIT-->>BE: audit_id

    BE->>WS: broadcast({TRANSLATION_COMPLETE, module=1})
    WS-->>FE: WebSocket push → TelemetryFeed updates

    BE-->>FE: TranslationResponse {xml_output, uetr, audit_id, status="SUCCESS"}
    FE-->>User: Display XML, UETR, validation badge ✓
```

### 4.2 Knowledge Q&A (LLM) Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Knowledge Page
    participant BE as /api/v1/learn
    participant CFG as LLMConfigStore
    participant LLM as LLMRouter
    participant EXT as External LLM API
    participant AUDIT as AuditLogger

    User->>FE: Ask "Explain pacs.008 settlement chain"
    FE->>BE: POST /learn {query, context: null}

    BE->>LLM: llm_router.query(query, context=None)
    LLM->>CFG: provider, model, api_key
    CFG-->>LLM: "groq", "llama-3.3-70b-versatile", "gsk_..."

    LLM->>EXT: POST api.groq.com/openai/v1/chat/completions
    Note over EXT: system: FINANCIAL_SYSTEM_PROMPT\nuser: query
    EXT-->>LLM: {choices[0].message.content: "pacs.008 is..."}

    LLM-->>BE: answer_text

    BE->>AUDIT: log(LEARN_QUERY, SUCCESS, details={query, msg_type_referenced})
    AUDIT-->>BE: audit_id

    BE-->>FE: LearnResponse {answer, sources, message_type_referenced, audit_id}
    FE-->>User: Render formatted AI answer in chat
```

---

## 5. Data Flow Diagrams

### 5.1 Complete Platform Data Flow

```mermaid
flowchart TD
    USER[👤 User]

    subgraph INPUT["Input Channels"]
        MT[SWIFT MT Raw Text]
        QUESTION[Natural Language Question]
        PDF_FILE[PDF Document]
        CONFIG[LLM Config Change]
    end

    subgraph PROCESSING["Processing Layer"]
        PARSE[MT Parser\nRegex field extraction]
        TRANSLATE[MX Translator\nISO 20022 XML generation]
        VALIDATE[ISO Validator\nXSD + CBPR+ rules]
        LLM[LLM Router\nMulti-provider dispatch]
        RAG[RAG Pipeline\nChunking + embedding + retrieval]
        STORE[LLM Config Store\nRuntime state]
    end

    subgraph STORAGE["Persistence Layer"]
        NDJSON[NDJSON Audit Files\ndata/audit/*.ndjson]
        CHROMA[ChromaDB Vector Store\ndata/chroma/]
        UPLOADS[PDF Files\ndata/uploads/]
    end

    subgraph OUTPUT["Output Channels"]
        XML[ISO 20022 XML]
        ANSWER[AI Answer Text]
        AUDIT_LOGS[Audit Log Entries]
        EVENTS[Real-time Telemetry Events]
    end

    USER --> MT & QUESTION & PDF_FILE & CONFIG

    MT --> PARSE --> TRANSLATE --> VALIDATE --> XML
    QUESTION --> LLM --> ANSWER
    PDF_FILE --> RAG --> CHROMA
    RAG --> LLM
    CONFIG --> STORE --> LLM

    TRANSLATE & VALIDATE & LLM & RAG --> NDJSON --> AUDIT_LOGS
    PDF_FILE --> UPLOADS
    VALIDATE & LLM & RAG --> EVENTS
```

---

## 6. Non-Functional Requirements

| NFR | Requirement | Implementation |
|-----|------------|----------------|
| **Performance** | Translation < 200ms P95 | Fully async, no blocking I/O |
| **LLM Response** | < 10s P90 | 3-attempt retry with 60s timeout per call |
| **Availability** | 99.5% during business hours | Graceful fallback mock on LLM failure |
| **Security** | No PII in logs | Regex IBAN/account masking before write |
| **Auditability** | Tamper-evident trail | SHA-256 hash chain on every entry |
| **Scalability** | Stateless API | All state in files/ChromaDB, not RAM |
| **Observability** | Structured logging | structlog JSON to stdout |
| **Portability** | Cross-platform | Python pathlib, no hardcoded paths |

---

## 7. Security Architecture

```mermaid
graph TD
    subgraph "API Security"
        CORS[CORS Policy\nFrontend origin allowlist]
        RATE[No Auth — Dev Mode\nJWT layer planned]
    end

    subgraph "Data Security"
        PII[PII Masking\nIBAN + account regex]
        HASH[Hash Chain\nTamper detection]
        MASK[API Key Masking\nFirst 8 + last 4 chars shown]
    end

    subgraph "Secret Management"
        ENV[.env file\nNever committed to git]
        RUNTIME[Runtime override\nvia /api/v1/llm-config]
        NOSTORE[API keys NOT stored to disk\nIn-memory only]
    end

    subgraph "Transport Security"
        LOCAL[localhost only — dev\nHTTPS required for production]
    end
```

### Key Security Controls

| Control | Description |
|---------|------------|
| **IBAN Masking** | Regex `[A-Z]{2}[0-9]{2}[A-Z0-9]{4,}` → `[MASKED]` before any write |
| **Account Masking** | 8+ digit numeric strings → `[MASKED]` |
| **Key Masking** | API keys shown as `AIzaSyAh****gmhg` (preview only) |
| **Hash Chain** | Each audit entry linked to previous — tampering detectable |
| **CORS** | Only `http://localhost:3000` and `http://127.0.0.1:3000` allowed |
| **Error Sanitisation** | Global exception handler returns generic errors (no stack traces) |
| **Key in Memory Only** | API keys held in `llm_config_store._api_keys` dict — never written to disk from frontend override |

---

*Document maintained by the Engineering team. Update with each architecture change.*
