# 🏦 The Compliance Leader — Project Analysis

> **Full-stack financial compliance platform** for ISO 20022 / SWIFT MT processing, built for banks, payment engineers, and compliance officers.

---

## 🎯 Project Objective

The core business problem this project solves is the **SWIFT CBPR+ R2025 mandate** (effective November 22, 2025) — legacy SWIFT MT103/MT202/MT202COV messages were retired from SWIFT FINplus and must now be expressed in **ISO 20022 XML** format. Banks and financial institutions worldwide need tooling to perform this migration accurately and in a compliant, auditable way.

---

## 🏗️ Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│             FRONTEND — Next.js 14 (TypeScript)           │
│   /dashboard │ /translate │ /learn │ /documents │ /audit │
│         + Auth: /login  /register  /verify-otp           │
└─────────────────────┬────────────────────────────────────┘
                      │ REST API + WebSocket
┌─────────────────────▼────────────────────────────────────┐
│             BACKEND — FastAPI (Python 3.12)              │
│   Routers → Services → SQLite / ChromaDB / NDJSON Audit  │
└──────────┬──────────────────────┬────────────────────────┘
           │                      │
    External LLMs          ISO 20022 XSD Schemas
  (Gemini / OpenAI /       CBPR+ validation rules
   Groq / Ollama)
```

---

## 🧩 Four Core Modules

### 📦 Module 1 — TX Translation & Validation Engine

**What it does:** Converts raw SWIFT MT messages into ISO 20022 XML deterministically.

**Supported message types:**

| MT Format | ISO 20022 (MX) | Description |
|---|---|---|
| MT103 | `pacs.008.001.08` | FI-to-FI Customer Credit Transfer |
| MT103 STP | `pacs.008.001.08` | Straight-Through Processing variant |
| MT202 | `pacs.009.001.08` | FI-to-FI Credit Transfer (CORE) |
| MT202 COV | `pacs.009.001.08` | Cover Payment |
| MT204 | `pacs.009.001.08` | Financial Institution Debit Transfer |
| MT103/202 Return | `pacs.004.001.09` | Payment Return |

**Translation pipeline:**
1. **MT Parser** → Extracts blocks 1–5, resolves field tags to semantic names (e.g., `:50K:` → `ordering_customer`)
2. **CBPR+ Guard** → Enforces prohibited field rules (e.g., pacs.009 CORE must NOT contain retail customer fields)
3. **UETR Handling** → Preserves existing UUID4 UETR or generates a new one
4. **XML Builder (lxml)** → Builds valid ISO 20022 XML with mandatory R2025 postal address fields
5. **XSD Validator** → Validates output against official ISO 20022 XSD schemas

**Key validation constraint examples:**
- `pacs.009 CORE` (MT202): No retail customer fields, no `<InstructedAmt>`
- `pacs.009COV` (MT202COV): Must wrap `<UndrlygCstmrCdtTrf>` block
- `pacs.004` (Return): Must contain `<OrgnlUETR>`, `<OrgnlMsgId>`, valid return reason code

---

### 🎓 Module 2 — Interactive Learning System (LLM Q&A)

**What it does:** AI-powered domain Q&A for ISO 20022 / SWIFT compliance education.

- Users can ask natural-language questions about CBPR+ rules, settlement chains, UETR tracking, message schemas, etc.
- The backend uses an **LLM Router** that abstracts over multiple providers:
  - **Gemini** (Google AI — default)
  - **OpenAI** (GPT-4o, etc.)
  - **Groq** (ultra-fast inference)
  - **Ollama** (local/on-premise)
- The provider and model can be hot-swapped at runtime via admin panel without restarting the server
- Built-in topic browser lists curated learning topics

---

### 📄 Module 3 — Document Intelligence (RAG Pipeline)

**What it does:** Upload compliance documents and query them with natural language.

**Pipeline:**
1. **Ingest** → Accepts PDF, PPTX, DOCX, TXT formats
2. **Chunk** → Splits text into overlapping semantic chunks
3. **Embed** → Uses `all-MiniLM-L6-v2` (sentence-transformers) to generate 384-dim vectors
4. **Store** → Persists in **ChromaDB** (persistent vector store)
5. **Query** → On user question: embed query → ANN search → retrieve top-k chunks → send to LLM with context → return grounded answer

---

### 🔍 Module 4 — Audit & Real-Time Telemetry

**What it does:** Every operation on the platform generates a tamper-evident audit log entry, streamed live via WebSocket.

**Audit log design:**
- **SHA-256 hash chaining** — each entry's hash includes the previous entry's hash, making retrospective tampering detectable
- **PII Masking** — IBANs and account numbers masked before write
- **Append-only NDJSON** — audit files opened in append mode only
- **Data Minimisation** — audit `details` field stripped of customer PII

**WebSocket Telemetry:**
- `/ws/telemetry` broadcasts real-time events to any connected frontend clients
- Dashboard shows live feed of translation, validation, query, and audit events

---

## 🔐 Authentication & Authorization

Banking-grade auth system:

| Feature | Implementation |
|---|---|
| Password hashing | bcrypt (cost 12) |
| Tokens | JWT HS256 (access + refresh) |
| Email OTP | Gmail SMTP via `aiosmtplib` |
| Account lockout | 5 failed attempts → 30 min lock |
| Role-based access | `user` / `admin` roles |
| Admin panel | User management, LLM config, guideline management |

**Auth flow:** Register → OTP Email Verification → Login → JWT Token → Protected routes via `Authorization: Bearer` header

---

## 🖥️ Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI (Python 3.12) + Uvicorn (ASGI) |
| **Frontend** | Next.js 14 (App Router, TypeScript) |
| **Styling** | Vanilla CSS — dark premium design with glassmorphism |
| **User Database** | SQLite + SQLAlchemy ORM |
| **Vector Database** | ChromaDB (persistent) |
| **Embedding Model** | `all-MiniLM-L6-v2` (384-dim vectors) |
| **XML Processing** | `lxml` |
| **LLM Providers** | Gemini, OpenAI, Groq, Ollama |
| **Logging** | `structlog` (structured JSON logs) |
| **Containerization** | Docker + Docker Compose |
| **Audit Storage** | NDJSON (append-only, SHA-256 hash chained) |

---

## 📁 Project Structure

```
WirePaymentAssistance/
├── backend/                    ← FastAPI Python backend
│   ├── main.py                 ← App factory, lifespan, health check
│   ├── config.py               ← Pydantic settings
│   ├── models/schemas.py       ← Pydantic request/response models
│   ├── routers/                ← API route handlers (9 routers)
│   │   ├── auth.py             ← Register, login, OTP, refresh
│   │   ├── translate.py        ← MT→MX translation
│   │   ├── learn.py            ← LLM Q&A
│   │   ├── documents.py        ← RAG upload/query
│   │   ├── audit.py            ← Audit logs + WebSocket
│   │   ├── admin.py            ← Admin panel operations
│   │   ├── llm_config.py       ← Runtime LLM provider config
│   │   └── guidelines.py       ← CBPR+ guideline versions
│   └── services/               ← Business logic
│       ├── mt_parser.py        ← SWIFT MT field parser
│       ├── mx_translator.py    ← MT→MX deterministic translator
│       ├── validator.py        ← XSD + CBPR+ validator
│       ├── llm_router.py       ← Multi-provider LLM abstraction
│       ├── rag_pipeline.py     ← Document RAG pipeline
│       ├── audit_logger.py     ← SHA-256 chained audit logger
│       ├── telemetry_bus.py    ← WebSocket broadcast bus
│       ├── auth_service.py     ← JWT + bcrypt + OTP + lockout
│       ├── email_service.py    ← Gmail SMTP OTP delivery
│       ├── guideline_registry.py ← CBPR+ guideline version store
│       └── llm_config_store.py ← Runtime LLM config store
├── frontend/                   ← Next.js 14 TypeScript frontend
│   ├── app/
│   │   ├── page.tsx            ← Dashboard (module overview)
│   │   ├── translate/          ← Module 1 UI
│   │   ├── learn/              ← Module 2 UI
│   │   ├── documents/          ← Module 3 UI
│   │   ├── audit/              ← Module 4 UI
│   │   ├── admin/              ← Admin panel
│   │   ├── login/              ← Auth pages
│   │   ├── register/
│   │   └── verify-otp/
│   └── components/
│       ├── Sidebar.tsx
│       ├── TelemetryFeed.tsx
│       ├── ValidationBadge.tsx
│       ├── DocumentUploader.tsx
│       └── AuditTable.tsx
├── data/
│   ├── xsd/                    ← ISO 20022 XSD schema files
│   ├── audit/                  ← Append-only compliance audit logs
│   ├── uploads/                ← Uploaded compliance documents
│   └── chroma/                 ← ChromaDB vector store
├── documentation/              ← 6 detailed docs + presentation
│   ├── 01_HLD_LLD.md           ← High/Low Level Design
│   ├── 02_file_hierarchy.md
│   ├── 03_user_manual.md
│   ├── 04_interview_questions.md
│   └── 05_presentation.html    ← Interactive HTML presentation
├── docker-compose.yml          ← One-command full-stack deployment
└── .env / .env.example         ← Environment config
```

---

## 🔑 Key API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | User registration |
| `POST` | `/api/v1/auth/login` | JWT login |
| `POST` | `/api/v1/auth/verify-otp` | Email OTP verification |
| `POST` | `/api/v1/translate` | MT → ISO 20022 XML translation |
| `POST` | `/api/v1/validate` | Validate XML against XSD + CBPR+ |
| `GET`  | `/api/v1/translate/sample/{type}` | Fetch sample MT message |
| `POST` | `/api/v1/learn` | LLM domain Q&A |
| `POST` | `/api/v1/documents/upload` | Upload document for RAG |
| `POST` | `/api/v1/documents/query` | Query indexed documents |
| `GET`  | `/api/v1/audit/logs` | Paginated audit log retrieval |
| `GET`  | `/api/v1/audit/export` | Tamper-evident audit bundle export |
| `WS`   | `/ws/telemetry` | Real-time WebSocket telemetry |
| `GET`  | `/health` | System health check (all modules) |

---

## 📄 Documentation

The project has rich documentation in the `documentation/` folder:

| File | Content |
|---|---|
| [`01_HLD_LLD.md`](file:///e:/D%20Drive/WirePaymentAssistance/documentation/01_HLD_LLD.md) | High-Level & Low-Level Design diagrams |
| [`02_file_hierarchy.md`](file:///e:/D%20Drive/WirePaymentAssistance/documentation/02_file_hierarchy.md) | Complete file structure with descriptions |
| [`03_user_manual.md`](file:///e:/D%20Drive/WirePaymentAssistance/documentation/03_user_manual.md) | Full user manual |
| [`04_interview_questions.md`](file:///e:/D%20Drive/WirePaymentAssistance/documentation/04_interview_questions.md) | Interview Q&A for the project |
| [`05_presentation.html`](file:///e:/D%20Drive/WirePaymentAssistance/documentation/05_presentation.html) | Interactive HTML presentation |
| [`PROJECT_DEEP_DIVE.md`](file:///e:/D%20Drive/WirePaymentAssistance/documentation/PROJECT_DEEP_DIVE.md) | 1036-line comprehensive technical deep dive |
