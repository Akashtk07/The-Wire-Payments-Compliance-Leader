# The Compliance Leader
## Cross-Border Regulatory Lineage, Translation Validation, Document Intelligence & Real-Time Telemetry Platform

> **Production-grade institutional platform** for ISO 20022 / SWIFT MT processing, compliance audit, and payment domain education.

---

## Architecture

```
frontend/   ← Next.js 14 (TypeScript, dark premium UI)
backend/    ← FastAPI (Python 3.12)
data/       ← Persistent volumes (audit logs, vector DB, XSD schemas, uploads)
```

## Four Core Modules

| # | Module | Purpose |
|---|---|---|
| 1 | **TX Translation & Validation Engine** | MT→MX deterministic translation with XSD + CBPR+ validation |
| 2 | **Interactive Learning System** | LLM-powered domain Q&A for ISO 20022 / SWIFT education |
| 3 | **Document Intelligence (RAG)** | Multi-format PDF/PPT/DOC ingestion + semantic query |
| 4 | **Audit & Telemetry** | SHA-256 chained audit logs + real-time WebSocket telemetry |

---

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- Node.js 20+
- A Gemini API key (or OpenAI API key)

### 1. Configure Environment
```bash
cp .env.example .env
# Edit .env and set your LLM_PROVIDER and API key
```

### 2. Start the Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Start the Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

---

## Quick Start (Docker Compose)

```bash
cp .env.example .env
# Edit .env with your API key
docker-compose up --build
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs (Swagger UI)

---

## Supported Message Types

| MT Format | ISO 20022 (MX) | Description |
|---|---|---|
| MT103 | pacs.008.001.08 | FI-to-FI Customer Credit Transfer |
| MT103 STP | pacs.008.001.08 | Straight-Through Processing variant |
| MT202 | pacs.009.001.08 | FI-to-FI Credit Transfer (CORE) |
| MT202 COV | pacs.009.001.08 | Cover Payment variant |
| MT204 | pacs.009.001.08 | Financial Institution Debit Transfer |
| MT103/202 Return | pacs.004.001.09 | Payment Return |

---

## Validation Rules

### MT→MX Prohibited Field Guard
The translation engine enforces strict SWIFT CBPR+ rules. Violations return:

```json
{
  "status": "VALIDATION_EXCEPTION",
  "error_code": "SWIFT_ISO_MUTATION_DENIED",
  "message": "[Field] is not permitted within [MessageType] as per SWIFT Guidelines.",
  "action": "Please check with your BA for more details regarding the updated schema layout specification sheets."
}
```

### Key Constraints
- `pacs.009 CORE` (MT202): Must NOT contain retail customer fields or `<InstructedAmt>`
- `pacs.009COV` (MT202COV): Must wrap `<UndrlygCstmrCdtTrf>` block
- `pacs.004` (Return): Must contain `<OrgnlUETR>`, `<OrgnlMsgId>`, valid return reason code

---

## Security & Compliance

- **PII Masking**: IBANs and account numbers are masked in all audit log entries before write
- **SHA-256 Hash Chaining**: Each audit entry's hash covers the previous entry, making retrospective tampering detectable
- **Append-Only Logs**: Audit NDJSON files are opened in append mode only
- **Data Minimisation**: Audit log `details` field is stripped of customer PII before persistence

---

## API Reference

Swagger UI available at http://localhost:8000/docs after starting the backend.

### Key Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/translate` | Translate raw MT → ISO 20022 XML |
| POST | `/api/v1/validate` | Validate an ISO 20022 XML against XSD + CBPR+ rules |
| GET | `/api/v1/translate/sample/{type}` | Fetch a sample MT message |
| POST | `/api/v1/learn` | Submit a domain knowledge query |
| GET | `/api/v1/learn/topics` | List available learning topics |
| POST | `/api/v1/documents/upload` | Upload a compliance document for RAG indexing |
| POST | `/api/v1/documents/query` | Query indexed documents |
| GET | `/api/v1/audit/logs` | Retrieve paginated audit log entries |
| GET | `/api/v1/audit/export` | Export tamper-evident audit bundle |
| WS | `/ws/telemetry` | Real-time telemetry WebSocket stream |
| GET | `/health` | System health check |

---

## Project Structure

```
WirePaymentAssistance/
├── .env.example           ← Environment template
├── docker-compose.yml     ← Container orchestration
├── README.md
├── backend/
│   ├── main.py            ← FastAPI app entry point
│   ├── config.py          ← Pydantic settings
│   ├── requirements.txt
│   ├── Dockerfile
│   ├── models/
│   │   └── schemas.py     ← Pydantic request/response models
│   ├── routers/
│   │   ├── translate.py   ← Module 1 endpoints
│   │   ├── learn.py       ← Module 2 endpoints
│   │   ├── documents.py   ← Module 3 endpoints
│   │   └── audit.py       ← Module 4 endpoints + WebSocket
│   ├── services/
│   │   ├── mt_parser.py        ← SWIFT MT field parser
│   │   ├── mx_translator.py    ← MT→MX deterministic translator
│   │   ├── validator.py        ← XSD + CBPR+ validator
│   │   ├── llm_router.py       ← LLM provider abstraction
│   │   ├── rag_pipeline.py     ← Document RAG pipeline
│   │   ├── audit_logger.py     ← SHA-256 chained audit logger
│   │   └── telemetry_bus.py    ← WebSocket broadcast bus
│   └── tests/
│       ├── test_translator.py
│       └── test_audit.py
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.js
│   ├── Dockerfile
│   ├── app/
│   │   ├── globals.css    ← Full dark design system
│   │   ├── layout.tsx     ← Root layout + sidebar
│   │   ├── page.tsx       ← Dashboard (Module overview)
│   │   ├── translate/page.tsx   ← Module 1
│   │   ├── learn/page.tsx       ← Module 2
│   │   ├── documents/page.tsx   ← Module 3
│   │   └── audit/page.tsx       ← Module 4
│   └── components/
│       ├── Sidebar.tsx
│       ├── TelemetryFeed.tsx
│       ├── ValidationBadge.tsx
│       ├── DocumentUploader.tsx
│       └── AuditTable.tsx
└── data/
    ├── xsd/               ← ISO 20022 XSD schema files
    ├── audit/             ← Append-only compliance audit logs
    ├── uploads/           ← Uploaded compliance documents
    └── chroma/            ← ChromaDB vector store
```
