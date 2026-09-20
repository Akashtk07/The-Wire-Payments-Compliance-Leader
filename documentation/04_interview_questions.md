# The Compliance Leader — Interview Questions & Model Answers

> **Document Type:** Interview Preparation Guide  
> **Audience:** Engineers, Architects, PMs presenting or interviewed about this project  
> **Version:** 1.0.0 | May 2026

---

## 📋 Table of Contents

1. [Project Overview Questions](#1-project-overview-questions)
2. [System Design & Architecture](#2-system-design--architecture)
3. [Backend Engineering (FastAPI / Python)](#3-backend-engineering-fastapi--python)
4. [Frontend Engineering (Next.js / React)](#4-frontend-engineering-nextjs--react)
5. [ISO 20022 & SWIFT Domain Questions](#5-iso-20022--swift-domain-questions)
6. [AI / LLM Integration Questions](#6-ai--llm-integration-questions)
7. [Security & Compliance Questions](#7-security--compliance-questions)
8. [Database & Persistence Questions](#8-database--persistence-questions)
9. [Real-Time & WebSocket Questions](#9-real-time--websocket-questions)
10. [DevOps & Deployment Questions](#10-devops--deployment-questions)
11. [Scenario-Based Questions](#11-scenario-based-questions)
12. [Behavioral / Leadership Questions](#12-behavioral--leadership-questions)

---

## 1. Project Overview Questions

### Q1: Can you describe The Compliance Leader in one sentence?

**Answer:**  
The Compliance Leader is a production-grade enterprise platform that automates SWIFT MT to ISO 20022 MX message translation with CBPR+ validation, provides an AI-powered financial domain knowledge assistant, RAG-based document intelligence, and maintains a tamper-evident hash-chained audit trail with real-time telemetry.

---

### Q2: What problem does this platform solve?

**Answer:**  
The global banking industry is mandated by SWIFT to migrate from legacy MT messages (MT103, MT202) to ISO 20022 MX format (pacs.008, pacs.009) by November 2025 under the CBPR+ framework. Banks face three challenges:

1. **Manual translation** is error-prone and expensive
2. **Compliance teams** lack deep ISO 20022 expertise  
3. **Audit requirements** demand tamper-evident logs of all operations

The platform addresses all three: automated translation engine, AI knowledge assistant, and cryptographic audit logging.

---

### Q3: Who are the target users?

**Answer:**  
- **Compliance Officers** → TX Engine + Audit (verify messages are CBPR+ compliant)
- **Payment Engineers** → TX Engine + Knowledge (understand field mappings, debug issues)
- **Financial Analysts** → Knowledge + Documents (research standards, generate reports)
- **System Administrators** → Dashboard + LLM Config (monitor health, manage AI providers)

---

### Q4: What is your technology stack and why did you choose it?

**Answer:**

| Layer | Choice | Reasoning |
|-------|--------|-----------|
| Backend | FastAPI + Python 3.13 | Native async/await, Pydantic v2 validation, automatic OpenAPI docs, fastest Python ASGI framework |
| Frontend | Next.js 14 + TypeScript | App Router for per-page routing, type safety, excellent DX, React component model |
| CSS | Vanilla CSS | Maximum control, no Tailwind dependency, custom design system with CSS custom properties |
| LLM calls | httpx REST | Avoids heavy SDK dependencies (grpcio, google-generativeai) that cause Windows compilation failures |
| Vector DB | ChromaDB | Embedded, no separate server needed, Python-native, supports persistence |
| Audit | NDJSON files | Append-only, human-readable, tamper-evident with hash chain, no DB dependency |
| Real-time | WebSocket | Low-latency, bidirectional, native browser support, perfect for telemetry streaming |

---

## 2. System Design & Architecture Questions

### Q5: Walk me through the system architecture.

**Answer:**  
The system has three layers:

1. **Frontend (Next.js 14)** — 5 pages served from port 3000. Communicates with backend via `fetch` (REST) and native WebSocket. The `LLMConfigPanel` uses React Portal to render the modal at document.body level (outside sidebar DOM) preventing clipping.

2. **Backend (FastAPI)** — 5 REST routers + 1 WebSocket router. Each router delegates to one or more services. The app factory pattern (`create_app()`) handles CORS, lifespan (startup/shutdown), and exception handling.

3. **Service Layer** — 8 focused services each with a single responsibility: parsing, translation, validation, LLM routing, RAG, audit logging, telemetry broadcasting, and runtime config management.

Key architectural principles: async-first, zero-dependency AI (pure httpx), lazy-loading for heavy ML, graceful degradation on LLM failure.

---

### Q6: How does the translation pipeline work end-to-end?

**Answer:**  
```
POST /api/v1/translate
  │
  ├── MTParser.parse(raw_str, source_type)
  │     • Regex-extract blocks {1:}{2:}{3:}{4:}
  │     • Parse tagged fields (:20:, :32A:, :50K:, :57A:, :59:)
  │     • Extract UETR from block 3 {121:}
  │     • Returns: {uetr, amount, ccy, debtor, creditor, ...}
  │
  ├── MXTranslator.translate(parsed, source_type, target_type)
  │     • Route: MT103→pacs.008, MT202→pacs.009.CORE, MT202COV→pacs.009.COV
  │     • Build ISO 20022 XML with proper namespace
  │     • ValidationException if CBPR+ mutation rules are violated
  │     • Returns: (xml_string, message_type)
  │
  ├── ISO20022Validator.validate(xml, message_type)
  │     • XSD validation (if schema file present)
  │     • CBPR+ business rules (UETR format, BIC length, mandatory fields)
  │     • Returns: (is_valid, [error_list])
  │
  ├── AuditLogger.log(TRANSLATION, status, uetr, ...)
  │     • Hash chain entry, PII masking, NDJSON append
  │
  └── TelemetryBus.broadcast(TRANSLATION_COMPLETE event)
        • Push to all connected WebSocket clients
```

---

### Q7: Why did you choose async programming throughout?

**Answer:**  
Financial compliance platforms are I/O-bound workloads, not CPU-bound. The bottlenecks are:
- HTTP calls to external LLM APIs (60s+ timeout possible)
- File writes for audit logging
- ChromaDB vector queries

Using Python's `asyncio` with `async/await` means the server can handle hundreds of concurrent requests without blocking threads. A single uvicorn worker can serve multiple concurrent LLM calls because while one request awaits the Gemini API, others are being processed.

Specifically: `aiofiles` for non-blocking file I/O, `httpx.AsyncClient` for non-blocking HTTP, asyncio.Lock for thread-safe audit log writes.

---

### Q8: How does the LLM Config hot-swap work without restarting the server?

**Answer:**  
The `llm_config_store` is an in-memory singleton (module-level instance). It stores:
```python
_provider: str
_model: str  
_api_keys: Dict[str, Optional[str]]  # per-provider
_history: deque(maxlen=25)
```

When `POST /api/v1/llm-config` is called:
1. `update()` method modifies the in-memory state immediately
2. Next call to `llm_router.query()` reads from the store — sees the new config
3. No restart, no re-initialization, no file writes

The key insight: `llm_router.py` imports `llm_config_store` (the singleton object), so it always reads the current state, not a snapshot.

---

### Q9: What design patterns are used in this project?

**Answer:**

| Pattern | Where Used |
|---------|-----------|
| **Factory Pattern** | `create_app()` in `main.py` — creates FastAPI instance with all config |
| **Singleton** | `audit_logger`, `telemetry_bus`, `llm_config_store`, `llm_router` — one instance shared across requests |
| **Strategy Pattern** | `llm_router` — different provider implementations, same interface |
| **Chain of Responsibility** | Translation pipeline: Parser → Translator → Validator |
| **Observer Pattern** | `telemetry_bus` — broadcasts events to all registered WebSocket clients |
| **Repository Pattern** | `audit_logger` — abstracts NDJSON file persistence |
| **Lazy Loading** | RAG pipeline — ChromaDB and torch imported only on first use |
| **Portal Pattern** | `LLMConfigPanel` — React Portal renders modal outside sidebar DOM |

---

## 3. Backend Engineering (FastAPI / Python)

### Q10: How do you handle configuration management securely?

**Answer:**  
Two-layer approach:

**Layer 1 — Built-in dotenv loader (`config.py`):**
```python
def _load_dotenv(path: Path) -> None:
    # Reads .env, sets os.environ for each key
    # Only sets if not already in environment (respects real env vars)
    if key not in os.environ:
        os.environ[key] = value
```

**Layer 2 — Pydantic-Settings:**
```python
class Settings(BaseSettings):
    GEMINI_API_KEY: Optional[str] = None
    # Reads from os.environ (already populated by layer 1)
```

Why two layers? `pydantic-settings` had Windows path resolution issues with `env_file`. Pre-loading via `os.environ` guarantees loading regardless of OS.

---

### Q11: How does the SHA-256 hash chain in the audit logger work?

**Answer:**  
```python
# Genesis hash
last_hash = SHA256("") = "e3b0c44298..."

# Entry 1
entry_json = json.dumps({audit_id, timestamp, event_type, ...})
entry_hash = SHA256(SHA256(last_hash) + SHA256(entry_json))
# Store entry with hash → last_hash = entry_hash

# Entry 2  
entry_hash = SHA256(SHA256(last_hash) + SHA256(entry_json))
```

Tamper detection: If someone modifies entry 1's data, `entry_hash` for entry 1 changes. Entry 2 used entry 1's hash as input, so entry 2's hash is now invalid. Entry 3 used entry 2's hash, so entry 3 is also invalid. The entire chain breaks — tamper is immediately detectable.

Additional security: PII (IBAN, account numbers) is masked via regex before the JSON is hashed — so even the hash doesn't contain cleartext PII.

---

### Q12: How do you handle the retry logic for LLM calls?

**Answer:**  
```python
async def _retry_async(coro_fn, max_attempts=3, base_delay=1.0):
    for attempt in range(max_attempts):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_attempts - 1:
                wait = base_delay * (2 ** attempt)  # 1s, 2s, 4s
                await asyncio.sleep(wait)
    raise last_exc
```

This is exponential backoff: 1s → 2s → 4s. Handles transient network failures, rate limit 429s (short burst), and temporary service unavailability. After 3 failures, the exception propagates and is caught by the router's error handler, which returns an informative error message to the user.

---

### Q13: Why is ChromaDB lazy-loaded?

**Answer:**  
ChromaDB imports `torch`, `sentence-transformers`, and other heavy ML dependencies. These:
1. Take 10-30 seconds to import (slow startup)
2. Required C++ compilation on Windows (caused build failures)
3. Are only needed when a user actually uploads a document or runs a RAG query

By using lazy loading:
```python
def _get_collection():
    try:
        import chromadb  # Only imported here, first call
        ...
    except ImportError:
        raise RuntimeError("ChromaDB not installed. Run: pip install -r requirements-ml.txt")
```

The server starts in ~2 seconds even without ChromaDB installed. The feature degrades gracefully with a clear error message rather than crashing on startup.

---

### Q14: Explain the CORS configuration.

**Answer:**  
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,  # ["http://localhost:3000", ...]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

`allow_origins` is a computed property that deduplicates and includes `FRONTEND_ORIGIN` from `.env` plus `http://localhost:3000` and `http://127.0.0.1:3000` as defaults. In production, this would be replaced with the actual domain (e.g., `https://compliance.bank.com`).

---

## 4. Frontend Engineering (Next.js / React)

### Q15: Why use Vanilla CSS instead of Tailwind?

**Answer:**  
- **Maximum control** — CSS custom properties enable a consistent design system without build-time constraints
- **Performance** — No purge step, no JIT compilation, single CSS file
- **Customization** — Complex components (glassmorphism, animated gradients, custom scrollbars) are easier in vanilla CSS
- **No breaking changes** — Tailwind version upgrades often break utility class names; vanilla CSS is stable
- **Team alignment** — The custom design system with tokens (`--color-primary`, `--sidebar-width`) is self-documenting

The `globals.css` is ~44KB and defines a complete enterprise design system with tokens, animations, buttons, cards, tables, and layout utilities.

---

### Q16: Why does the LLMConfigPanel use React Portal?

**Answer:**  
The `LLMConfigPanel` trigger button lives inside the `Sidebar` component. In React, when a component is nested inside another with CSS properties like `position: fixed`, `overflow: hidden`, or `transform`, it creates a **new stacking context** that constrains the child.

Without Portal:
```
Sidebar (overflow: hidden, position: fixed)
  └── LLMConfigPanel modal (position: fixed → constrained to sidebar bounds!)
```

With Portal:
```jsx
createPortal(<div className="modal">...</div>, document.body)
```
```
document.body
  ├── Sidebar
  └── [Portal] LLMConfigPanel modal (truly position: fixed over full viewport)
```

Portal renders the modal into `document.body` DOM node, completely escaping the sidebar's stacking context. The modal is now free to cover 100% of the viewport.

---

### Q17: How does the TelemetryFeed component maintain the WebSocket connection?

**Answer:**  
```typescript
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/ws/telemetry');
  
  ws.onopen = () => { setConnected(true); };
  ws.onmessage = (e) => {
    const event = JSON.parse(e.data);
    setEvents(prev => [event, ...prev].slice(0, 50)); // keep last 50
  };
  ws.onclose = () => {
    setConnected(false);
    // Auto-reconnect after 3s
    setTimeout(() => { /* re-establish */ }, 3000);
  };
  
  return () => ws.close(); // cleanup on unmount
}, []);
```

Key: the cleanup function in `useEffect` closes the WebSocket when the component unmounts (user navigates away), preventing memory leaks and orphaned connections.

---

### Q18: How do you prevent memory leaks in React components?

**Answer:**  
Several patterns used throughout the codebase:

1. **useRef for animations:**
```typescript
const rafRef = useRef<number | null>(null);
useEffect(() => {
  rafRef.current = requestAnimationFrame(animate);
  return () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); };
}, []);
```

2. **AbortSignal for fetch:**
```typescript
fetch(url, { signal: AbortSignal.timeout(3000) })
```

3. **Interval cleanup:**
```typescript
const interval = setInterval(fn, 30000);
return () => clearInterval(interval);
```

4. **WebSocket cleanup:**
```typescript
return () => ws.close();
```

---

## 5. ISO 20022 & SWIFT Domain Questions

### Q19: What is the difference between MT and MX messages?

**Answer:**

| Aspect | MT (Legacy SWIFT) | MX (ISO 20022) |
|--------|------------------|----------------|
| Format | Tagged fields (:20:, :32A:) | XML with namespace |
| Standard | SWIFT proprietary | International ISO standard |
| Data richness | Limited structured data | Rich, extensible data model |
| Example | MT103 (customer payment) | pacs.008.001.08 |
| Ambiguity | High (free-text fields) | Low (strict schema) |
| Compliance | Being retired | Mandated by 2025 (CBPR+) |

---

### Q20: What is CBPR+ and why does it matter?

**Answer:**  
CBPR+ (Cross-Border Payments and Reporting Plus) is SWIFT's rulebook for how ISO 20022 must be used in cross-border payments. It defines:
- Which fields are mandatory vs. optional
- Prohibited field combinations (e.g., retail fields in bank-to-bank messages)
- Specific code lists that must be used
- Format requirements (UETR must be UUID4)
- Migration timeline

It matters because compliance failures can result in message rejection, regulatory penalties, and transaction delays. The platform implements CBPR+ rules programmatically.

---

### Q21: Explain the difference between pacs.008 and pacs.009.

**Answer:**

| Aspect | pacs.008 | pacs.009 |
|--------|----------|----------|
| Legacy equivalent | MT103 | MT202 / MT202COV |
| Purpose | Customer credit transfer | FI credit transfer |
| Contains customer data | Yes (`<Dbtr>`, `<Cdtr>`) | CORE: No / COV: Yes (in `<UndrlygCstmrCdtTrf>`) |
| Debtor agent | `<DbtrAgt>` | `<InstgAgt>` |
| When to use | Retail customer sends money | Bank covers a customer payment or makes FI transfer |

The `pacs.009 COV` variant includes the `<UndrlygCstmrCdtTrf>` block which carries the original pacs.008 details — this is required when a correspondent bank is covering a customer payment.

---

### Q22: What is a UETR and how is it used?

**Answer:**  
UETR (Unique End-to-end Transaction Reference) is a UUID4 identifier mandated by SWIFT gpi since 2018.

- **Format:** `550e8400-e29b-41d4-a716-446655440000` (UUID4 — 36 characters)
- **MT location:** Block 3, field `{121:}`
- **MX location:** `<PmtId><UETR>` in the credit transfer XML
- **Rule:** Every bank in the chain MUST preserve it unchanged
- **Purpose:** End-to-end tracking via SWIFT gpi Tracker

The platform extracts UETR from MT messages, preserves it in the MX output, validates UUID4 format, and stores it in the audit log for traceability.

---

### Q23: What CBPR+ validation rules have you implemented?

**Answer:**

| Rule | Description |
|------|-------------|
| `RULE-001` | pacs.009 CORE must NOT contain `<InstructedAmt>` or retail customer fields |
| `RULE-002` | pacs.009 COV MUST contain `<UndrlygCstmrCdtTrf>` block |
| `RULE-003` | UETR must be valid UUID4 format (`[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-...`) |
| `RULE-004` | `<IntrBkSttlmAmt>` currency must be valid ISO 4217 code |
| `RULE-005` | BIC codes must be exactly 8 or 11 characters |
| `RULE-006` | pacs.004 must reference `<OrgnlUETR>` and `<OrgnlMsgId>` |
| `RULE-007` | Return reason code must be from CBPR+ external code set |

---

## 6. AI / LLM Integration Questions

### Q24: Why do you use httpx instead of the official Google AI SDK?

**Answer:**  
Three reasons:

1. **Dependency complexity:** `google-generativeai` requires `grpcio` which needs C++ Build Tools to compile on Windows. This caused complete build failures on Python 3.13.

2. **Size:** The SDK pulls in ~50 transitive dependencies. httpx is already in our requirements and adds zero overhead.

3. **Simplicity:** The Gemini REST API is just a POST request:
```python
POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}
Body: {"contents": [{"role": "user", "parts": [{"text": query}]}]}
```
No SDK needed. Direct REST is more transparent, debuggable, and stable against SDK version changes.

---

### Q25: How does the RAG pipeline prevent hallucinations?

**Answer:**  
RAG (Retrieval-Augmented Generation) is specifically designed to reduce hallucinations:

1. **Retrieval first:** Before generating, the system retrieves the top-k most similar chunks from the vector database (actual document content)
2. **Grounded context:** The retrieved chunks are prepended to the LLM prompt as authoritative context
3. **Instruction:** The system prompt tells the model to answer based on the provided context
4. **Citations:** Responses include source document references (filename, chunk index)

The model is anchored to your actual documents rather than its training data. If the answer isn't in the documents, the model should say so rather than invent content.

---

### Q26: How does the financial system prompt reduce hallucinations in the Knowledge module?

**Answer:**  
```
"You are an expert financial systems educator specializing in ISO 20022,
SWIFT messaging, global clearing and settlement, and cross-border payment law.
You provide precise, structured, zero-fluff explanations...
When explaining message fields, always reference the exact XML element path.
When explaining flows, describe the full settlement chain.
Always distinguish between MT (legacy SWIFT) and MX (ISO 20022) concepts clearly."
```

Key anti-hallucination instructions:
- **"Exact XML element path"** — Forces specific, verifiable claims (not vague descriptions)
- **"Distinguish MT from MX clearly"** — Prevents mixing up the two systems
- **"Zero-fluff"** — Discourages padding that often contains inaccuracies
- **Low temperature (0.2)** — Less random generation = more factual, less creative

---

### Q27: Explain the multi-provider LLM strategy.

**Answer:**  
The `llm_config_store` decouples the LLM choice from the application code. Benefits:

1. **Failover:** When Gemini hits quota, switch to Groq in 5 clicks — no restart
2. **Cost optimization:** Use Groq (free tier) for development, Gemini for production
3. **Privacy:** Ollama for sensitive documents (runs locally, no data leaves the network)
4. **Quality testing:** Compare responses across providers for the same question
5. **Provider independence:** If a provider changes pricing or availability, switch instantly

The `LLMRouter.query()` method always reads from the live config store — there's no caching of the provider choice.

---

## 7. Security & Compliance Questions

### Q28: How is PII (Personal Identifiable Information) handled?

**Answer:**  
Three-layer approach:

**Layer 1 — Masking before persistence:**
```python
_IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4,}\b")
_ACCOUNT_RE = re.compile(r"\b\d{8,}\b")

def _mask_pii(text: str) -> str:
    text = _IBAN_RE.sub("[MASKED]", text)   # IBANs
    text = _ACCOUNT_RE.sub("[MASKED]", text) # Account numbers
    return text
```

Applied to the entire JSON string before writing to the audit log — a "belt and suspenders" approach that catches PII even in nested fields.

**Layer 2 — API key masking:**
LLM config history stores: `key[:8] + "*" * (len-12) + key[-4:]`

**Layer 3 — Error sanitization:**
Global exception handler returns generic messages — no stack traces exposed to clients.

---

### Q29: How do you prevent API key exposure?

**Answer:**
1. **Never written to disk from frontend overrides** — Runtime API keys stay in `llm_config_store._api_keys` dict (RAM only)
2. **Masked in all API responses** — `api_key_preview` field only shows `AIzaSyAh****gmhg`
3. **`.env` in `.gitignore`** — Never committed to version control
4. **Transport** — localhost only in dev; HTTPS required for production
5. **No logging of full keys** — structlog only logs `api_key_loaded: true/false`

---

### Q30: How do you ensure the audit log is tamper-evident?

**Answer:**  
Hash chain + append-only file design:

1. **Append-only:** File is opened with `mode="a"` — no overwrite possible through the API
2. **Hash chain:** Each entry's hash depends on all previous entries
3. **Async lock:** `asyncio.Lock()` prevents concurrent writes that could corrupt the chain
4. **Daily rotation:** New file each day — easier to audit specific date ranges
5. **Verification:** To verify integrity, re-compute the chain from genesis and compare

For production: the daily files should be immediately copied to write-once storage (S3 with object lock, WORM storage) after creation.

---

## 8. Database & Persistence Questions

### Q31: Why use NDJSON files instead of a relational database for audit logs?

**Answer:**

| Concern | NDJSON | Database |
|---------|--------|---------|
| Append-only guarantee | ✅ Native (mode="a") | ❌ Requires application enforcement |
| Tamper evidence | ✅ Hash chain on file | ❌ Needs triggers + external verification |
| Portability | ✅ Human-readable, no DB server | ❌ Requires DB server, migrations |
| Regulatory compliance | ✅ Line-by-line GDPR deletion (comment out line) | ❌ Complex with referential integrity |
| Export | ✅ Already in standard format | ❌ Export step required |
| Simplicity | ✅ `aiofiles.open(path, "a")` | ❌ ORM, migrations, connection pooling |

For a financial audit log, NDJSON is actually the better choice because the regulatory requirement is immutability and human-inspectability — not complex querying.

---

### Q32: How does ChromaDB store and retrieve vectors?

**Answer:**  
ChromaDB uses HNSW (Hierarchical Navigable Small World) algorithm for approximate nearest-neighbor search:

1. **Ingestion:** Each text chunk is converted to a 384-dimensional embedding vector by `sentence-transformers/all-MiniLM-L6-v2`
2. **Storage:** Vectors stored in a local HNSW index in `data/chroma/`
3. **Retrieval:** Query text → query embedding → cosine similarity search → top-k chunks
4. **Metadata:** Each chunk stores `doc_id`, `filename`, `chunk_index`, `page_num` for source citation

The index is persistent — survives server restarts. ChromaDB is "embedded" — no separate server process needed.

---

## 9. Real-Time & WebSocket Questions

### Q33: How does the WebSocket telemetry system work?

**Answer:**  
```python
# Server side — TelemetryBus singleton
class TelemetryBus:
    _clients: Set[WebSocket] = set()
    
    async def connect(self, ws): await ws.accept(); _clients.add(ws)
    async def disconnect(self, ws): _clients.discard(ws)
    
    async def broadcast(self, event: dict):
        payload = json.dumps(event)
        dead = set()
        for client in list(_clients):
            try:
                if client.state == CONNECTED:
                    await client.send_text(payload)
                else: dead.add(client)
            except: dead.add(client)
        _clients -= dead  # Remove dead clients
```

The singleton is imported by all routers. After any significant operation (translation, learn query, document upload), the router calls `await telemetry_bus.broadcast(event)` which pushes to all connected browser tabs simultaneously.

---

### Q34: What happens when a WebSocket client disconnects unexpectedly?

**Answer:**  
Two mechanisms:

1. **FastAPI's `WebSocketDisconnect` exception:** Caught in the endpoint handler, triggers `telemetry_bus.disconnect(ws)`

2. **Dead client pruning during broadcast:** `send_text()` raises an exception for dead connections. These are collected in a `dead_clients` set and removed after the broadcast loop (avoids modifying a set during iteration).

The combination ensures the `_clients` set stays clean — no memory leak from disconnected clients.

---

## 10. DevOps & Deployment Questions

### Q35: How would you deploy this to production?

**Answer:**  
Production architecture changes needed:

1. **HTTPS:** Put uvicorn behind nginx with SSL termination
2. **Authentication:** Add JWT middleware (skeleton already in config: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`)
3. **API key management:** Move to secrets manager (AWS Secrets Manager, Azure Key Vault)
4. **Audit log storage:** Copy NDJSON files to WORM S3 bucket (immutable storage)
5. **ChromaDB:** Consider upgrading to hosted vector DB (Pinecone, Weaviate) for scale
6. **Process management:** Use `gunicorn -k uvicorn.workers.UvicornWorker` for multiple workers
7. **Monitoring:** Plug structlog JSON output into ELK Stack or Datadog

Docker Compose is already provided for containerized deployment.

---

### Q36: How do you handle dependency management for Windows?

**Answer:**  
Split into two requirements files:

**`requirements-core.txt`** — Pure Python wheels (no C compilation):
```
fastapi, uvicorn, pydantic, httpx, aiofiles, structlog, python-multipart
```
Install with: `pip install -r requirements-core.txt`

**`requirements-ml.txt`** — Heavy ML packages:
```
chromadb, sentence-transformers, torch, lxml
```
Install with: `pip install -r requirements-ml.txt --prefer-binary`

`--prefer-binary` downloads pre-compiled wheels instead of source packages, avoiding the requirement for Microsoft C++ Build Tools (which caused `chroma-hnswlib` build failure).

---

## 11. Scenario-Based Questions

### Q37: An MT202 message is submitted but should be MT202COV. What happens?

**Answer:**  
1. `mt_parser.parse()` extracts the fields and detects retail customer fields present
2. `mx_translator.translate()` detects this is a mutation violation
3. `ValidationException` is raised with `field_name`, `message_type`, `message`, `action`
4. Router catches `ValidationException` → returns HTTP 422 with `ValidationExceptionResponse`
5. Response includes: `"Submit this message as MT202COV to include the UndrlygCstmrCdtTrf block"`
6. Audit logged with `status=VALIDATION_EXCEPTION`, `error_code=SWIFT_ISO_MUTATION_DENIED`
7. Frontend displays the error explanation and remediation action

---

### Q38: The Gemini API returns a 429 quota error during a live demo. What do you do?

**Answer:**  
1. Click **"LLM Config"** in the sidebar
2. Select **"⚡ Groq"** provider
3. Choose **"Llama 3.3 70B Versatile"**
4. Paste the Groq API key (`gsk_...`)
5. Click **"Test Connection"** — verify ✅
6. Click **"Apply Configuration"**
7. Return to Knowledge tab — next question uses Groq

Total time: ~20 seconds. No server restart needed. History tab shows the switch was recorded.

---

### Q39: A compliance officer asks you to prove the audit log hasn't been tampered with. What do you show them?

**Answer:**  
1. Navigate to **Audit & Telemetry page**
2. Click **"Export Bundle"** — downloads the full NDJSON file
3. Open the file and show the `hash` field in each entry
4. Explain: "Each hash is derived from the previous hash and the entry data. If any entry was modified, its hash would no longer match, invalidating all subsequent hashes."
5. (Advanced) Run a hash chain verification script:
   ```python
   prev_hash = sha256("")
   for entry in entries:
       expected = sha256(sha256(prev_hash) + sha256(entry_without_hash))
       assert expected == entry["hash"], f"Tampered at {entry['audit_id']}"
       prev_hash = entry["hash"]
   print("All", len(entries), "entries verified - chain intact")
   ```

---

## 12. Behavioral / Leadership Questions

### Q40: What was the hardest technical challenge and how did you solve it?

**Answer:**  
**Challenge:** On Windows with Python 3.13, `pip install chromadb` failed because it requires `chroma-hnswlib` which needs Microsoft C++ Build Tools 14.0+ to compile from source. This completely blocked the application from starting.

**Solution (multi-layered):**
1. **Immediate:** Replaced `google-generativeai` SDK with direct `httpx` REST calls — eliminated `grpcio` compilation requirement
2. **Dependencies:** Split into `requirements-core.txt` (pure Python wheels) and `requirements-ml.txt` (heavy ML, use `--prefer-binary`)
3. **Architecture:** Made ChromaDB a lazy import — application starts cleanly even if ChromaDB isn't installed, failing gracefully only when the Documents feature is used
4. **Structlog:** Fixed `add_logger_name` incompatibility with `PrintLoggerFactory` by replacing with a custom `_add_logger_name` processor

**Lesson:** Production dependencies on Windows require explicit wheel strategy — never assume pip can compile from source in any environment.

---

### Q41: How did you handle the "MOCK MODE" issue that persisted despite having an API key in .env?

**Answer:**  
**Root cause:** `pydantic-settings` had a Windows path resolution issue with the `env_file` parameter — the path was computed as `D:\WirePaymentAssistance\.env` (backslashes) but the check was using forward slashes.

**Diagnosis:** Added startup diagnostic logging:
```python
log.info("llm_config", 
    gemini_api_key_loaded=bool(settings.GEMINI_API_KEY),
    gemini_api_key_preview=f"{settings.GEMINI_API_KEY[:8]}..." if key_set else "NOT SET"
)
```
This showed `gemini_api_key_loaded: false` despite the key being in `.env`.

**Fix:** Added a built-in `_load_dotenv()` function in `config.py` that pre-loads `.env` into `os.environ` before pydantic-settings reads it. This bypasses any path resolution issues since `open(path)` uses Python's native OS path handling.

**Result:** Key confirmed loaded on next startup → Gemini returned real 429 quota error (not MOCK MODE) — proving the key loaded correctly.

---

*Prepared for engineering interviews, technical presentations, and architecture reviews.*  
*Update this document after each significant feature addition.*
