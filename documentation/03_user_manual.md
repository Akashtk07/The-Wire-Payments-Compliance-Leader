# The Compliance Leader — Complete User Manual

> **Document Type:** End-User Reference Manual  
> **Audience:** Compliance Officers, Payment Engineers, Financial Analysts — including Non-Technical Users  
> **Version:** 1.0.0  
> **Platform:** The Compliance Leader — ISO 20022 Enterprise Compliance Platform  
> **Date:** May 2026

---

## 📋 Table of Contents

1. [What is The Compliance Leader?](#1-what-is-the-compliance-leader)
2. [Why Was This Platform Built?](#2-why-was-this-platform-built)
3. [Who Uses This Platform?](#3-who-uses-this-platform)
4. [Getting Started — First Launch](#4-getting-started--first-launch)
5. [Understanding the Interface](#5-understanding-the-interface)
6. [Module 1: Command Center (Dashboard)](#6-module-1-command-center-dashboard)
7. [Module 2: TX Engine (Translation Engine)](#7-module-2-tx-engine-translation-engine)
8. [Module 3: Knowledge (AI Learning Assistant)](#8-module-3-knowledge-ai-learning-assistant)
9. [Module 4: Documents (Document Intelligence)](#9-module-4-documents-document-intelligence)
10. [Module 5: Audit & Telemetry](#10-module-5-audit--telemetry)
11. [⚙ LLM Configuration — Switching AI Providers](#11--llm-configuration--switching-ai-providers)
12. [Real-Time Features](#12-real-time-features)
13. [Common Workflows](#13-common-workflows)
14. [Troubleshooting](#14-troubleshooting)
15. [Glossary — Plain English Definitions](#15-glossary--plain-english-definitions)

---

## 1. What is The Compliance Leader?

**The Compliance Leader** is an intelligent software platform designed for financial institutions navigating the global shift from the old SWIFT messaging system (called **MT format**) to the new international standard (called **ISO 20022 / MX format**).

Think of it as a **smart translation machine + AI tutor + compliance monitor** — all in one browser-based application.

### In Simple Terms:

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   OLD WAY:  MT103  →  ❓  →  Manually translate  →  MX     │
│                                                             │
│   NEW WAY:  MT103  →  The Compliance Leader  →  MX  ✓      │
│             + Validates it + Logs it + Teaches you + Alerts │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### What can it do?

| Feature | What it does for you |
|---------|---------------------|
| 🔄 **Translate** | Converts SWIFT MT messages to ISO 20022 XML automatically |
| ✅ **Validate** | Checks if your ISO 20022 messages follow the rules |
| 🤖 **Ask AI** | Answers your questions about payment standards in plain English |
| 📄 **Documents** | Lets you upload compliance documents and ask questions about them |
| 🔍 **Audit Trail** | Keeps a permanent, tamper-proof record of every operation |
| 📡 **Live Updates** | Shows real-time activity happening in the system |
| ⚙ **AI Provider** | Switch between different AI engines (Gemini, Groq, OpenAI) instantly |

---

## 2. Why Was This Platform Built?

### The Problem

The global banking industry is going through one of its biggest changes in 40 years. The old SWIFT messaging format (MT) is being retired. Every bank, payment processor, and financial institution must switch to the new ISO 20022 standard by **November 2025** (CBPR+ mandate).

This creates massive challenges:
- ❌ **Manual translation** is slow, error-prone, and expensive
- ❌ **Compliance teams** don't have time to learn an entirely new XML-based format
- ❌ **Audit requirements** demand that every transaction be logged and verifiable
- ❌ **Training** on new standards takes months

### The Solution

The Compliance Leader addresses every one of these challenges:

| Challenge | Solution |
|-----------|---------|
| Manual translation | ⚡ Automated, deterministic MT→MX engine |
| Learning new standards | 🤖 AI-powered knowledge assistant |
| Audit requirements | 🔐 SHA-256 hash-chained audit log |
| Compliance verification | ✅ CBPR+ rule validation engine |
| Document research | 📄 RAG-powered document search |

---

## 3. Who Uses This Platform?

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER PERSONAS                            │
│                                                                 │
│  👔 COMPLIANCE OFFICER                                          │
│     Uses: TX Engine, Audit & Telemetry                          │
│     Goal: Ensure all messages meet ISO 20022 / CBPR+ rules      │
│                                                                 │
│  💻 PAYMENT ENGINEER                                            │
│     Uses: TX Engine, Knowledge, Documents                       │
│     Goal: Understand field mappings, debug translation issues    │
│                                                                 │
│  📊 FINANCIAL ANALYST                                           │
│     Uses: Knowledge, Documents, Audit                           │
│     Goal: Research payment standards, generate reports          │
│                                                                 │
│  🔧 SYSTEM ADMINISTRATOR                                        │
│     Uses: LLM Config, Audit, Dashboard                          │
│     Goal: Monitor system health, manage AI providers            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Getting Started — First Launch

### Step 1: Start the Backend (API Server)

Open a terminal and run:
```bash
cd d:\WirePaymentAssistance\backend
uvicorn main:app --reload --port 8000
```

✅ You should see: `INFO: Application startup complete.`

### Step 2: Start the Frontend (Web App)

Open a second terminal and run:
```bash
cd d:\WirePaymentAssistance\frontend
npm run dev
```

✅ You should see: `ready started server on 0.0.0.0:3000`

### Step 3: Open the Platform

Open your browser and go to:
```
http://localhost:3000
```

### Step 4: Verify System is Running

```
Look at the bottom-left of the sidebar.
You should see: ● System Nominal (green dot)
```

> ⚠️ If you see **"API Degraded"** (red dot) — the backend is not running. Go back to Step 1.

---

## 5. Understanding the Interface

### The Main Layout

```
┌────────────────────────────────────────────────────────────────┐
│  TOPBAR ──────────────────────────────────────────── [Clock]   │
│  The Compliance Leader > Current Page                          │
├──────────────┬─────────────────────────────────────────────────┤
│              │                                                 │
│   SIDEBAR    │         MAIN CONTENT AREA                       │
│   (Left)     │         (Changes per page)                      │
│              │                                                 │
│  ▣ Command   │                                                 │
│  ↔ TX Engine │                                                 │
│  ⊕ Knowledge │                                                 │
│  ▣ Documents │                                                 │
│  ✓ Audit     │                                                 │
│              │                                                 │
│  ─────────   │                                                 │
│  SYSTEM      │                                                 │
│  [Uptime]    │                                                 │
│  [LLM Config]│                                                 │
│  ─────────   │                                                 │
│  ● Nominal   │                                                 │
│  v1.0.0      │                                                 │
└──────────────┴─────────────────────────────────────────────────┘
```

### Sidebar Navigation

| Icon & Label | What it Opens | When to Use |
|-------------|--------------|------------|
| 🏠 **Command Center** | Dashboard with stats and live feed | Check overall system status |
| ↔ **TX Engine** | Translation & Validation workspace | Translate MT messages |
| 📚 **Knowledge** | AI chat assistant | Ask questions about standards |
| 📄 **Documents** | PDF upload and search | Research uploaded documents |
| 🔐 **Audit & Telemetry** | Compliance log and live events | Review audit trail |

### Color System

The platform uses a consistent color language:

| Color | Meaning | Example |
|-------|---------|---------|
| 🔵 **Cyan** (`#00D4FF`) | Primary actions, active state, information | Active nav item |
| 🟢 **Green** (`#00E5A0`) | Success, valid, healthy | "VALID" badge |
| 🟡 **Amber** (`#FFB800`) | Warning, partial, needs attention | Validation warning |
| 🔴 **Red** (`#FF4444`) | Error, invalid, failed | API error |
| 🟣 **Purple** (`#7B2FBE`) | Knowledge/AI features | Knowledge module |

---

## 6. Module 1: Command Center (Dashboard)

**URL:** `http://localhost:3000/`

### What You See

```
┌─────────────────────────────────────────────────────────────┐
│  COMMAND CENTER                                             │
│  Real-time compliance operations dashboard                  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Total   │  │  Learn   │  │Documents │  │  Audit   │   │
│  │Translations│  │ Queries  │  │ Indexed  │  │  Events  │   │
│  │   142    │  │    38    │  │    12    │  │   847    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                             │
│  [Live Telemetry Feed]        [Recent Audit Logs]           │
│  ● TRANSLATION_COMPLETE       #a1b2c3  TRANSLATION  ✓      │
│  ● LEARN_QUERY_COMPLETE       #d4e5f6  LEARN_QUERY  ✓      │
│  ● DOCUMENT_INDEXED           #g7h8i9  DOCUMENT     ✓      │
└─────────────────────────────────────────────────────────────┘
```

### The Four Stat Cards

The numbers animate (count up) when the page loads — this is not a bug, it's a visual effect.

| Card | What it counts |
|------|---------------|
| **Total Translations** | How many MT→MX translations have been done |
| **Learn Queries** | How many AI questions have been asked |
| **Documents Indexed** | How many PDFs have been uploaded and processed |
| **Audit Events** | Total number of logged events (all types) |

### Live Telemetry Feed

This updates automatically without refreshing the page. Every time something happens in the system (a translation, a question, a document upload), a new event appears here within 1-2 seconds.

### Recent Audit Logs

Shows the last 5-10 audit entries. Click **"View All Logs"** to go to the full Audit page.

---

## 7. Module 2: TX Engine (Translation Engine)

**URL:** `http://localhost:3000/translate`

> **Purpose:** Convert old SWIFT MT payment messages into new ISO 20022 MX format.  
> **Non-technical analogy:** Like Google Translate, but for bank payment messages.

### Step-by-Step: Translating a Message

#### Step 1 — Select Message Type

```
┌─────────────────────────────────────────────────────────────┐
│  SELECT MESSAGE TYPE                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  MT103   │ │  MT202   │ │MT202COV  │ │  MT204   │      │
│  │ Customer │ │  FI to   │ │ Cover    │ │  Direct  │      │
│  │ Transfer │ │  FI      │ │ Payment  │ │  Debit   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
```

Choose the type of SWIFT MT message you have:
- **MT103** → Customer payment (one person/company paying another)
- **MT202** → Bank-to-bank payment (no customer details)
- **MT202COV** → Bank-to-bank payment that "covers" a customer payment
- **MT204** → Direct debit between banks
- **MT103RETURN / MT202RETURN** → Returning a payment

#### Step 2 — Paste Your MT Message

Click **"Load Sample"** to see an example, or paste your own MT message in the text area:

```
Example MT103:
{1:F01DEUTDEDBXXXX0000000000}
{2:I103BNPAFRPPXXXXN}
{4:
:20:TXN20260524001
:23B:CRED
:32A:260524EUR125000,00
:50K:/DE89370400440532013000
MUELLER HANS
:52A:DEUTDEDB
:57A:BNPAFRPP
:59:/FR7614508300000000000000000
DUPONT MARIE
:70:INVOICE 2026-001
:71A:OUR
-}
{5:{CHK:ABCDEF012345}}
```

#### Step 3 — Click "Translate"

```
                  ┌─────────────────────┐
                  │   ⚡ TRANSLATE       │  ← Click this button
                  └─────────────────────┘
```

#### Step 4 — View Results

The right panel shows:

```
┌─────────────────────────────────────────────────────────────┐
│  TRANSLATION RESULT                        ✅ VALID          │
│                                                             │
│  Message Type: pacs.008.001.08                              │
│  UETR: 550e8400-e29b-41d4-a716-446655440000                │
│  Status: SUCCESS                                            │
│                                                             │
│  <?xml version="1.0" encoding="UTF-8"?>                    │
│  <Document xmlns="urn:iso:std:iso:20022:tech:xsd:           │
│            pacs.008.001.08">                                │
│    <FIToFICstmrCdtTrf>                                      │
│      <GrpHdr>                                               │
│        ...                                                  │
│    </FIToFICstmrCdtTrf>                                     │
│  </Document>                                                │
│                                                             │
│  Audit ID: a1b2c3d4-...                                     │
└─────────────────────────────────────────────────────────────┘
```

### Validation Badges

| Badge | Meaning | Action Required |
|-------|---------|----------------|
| ✅ **VALID** | Message is fully compliant | None — ready to use |
| ⚠️ **PARTIAL** | Valid structure, minor warnings | Review warnings, may be acceptable |
| ❌ **INVALID** | Failed CBPR+ rules | Must fix before sending |

### Understanding the UETR

**UETR** (Unique End-to-end Transaction Reference) is a UUID4 identifier that tracks a payment across every bank it passes through. Like a tracking number for a payment.

```
Example UETR: 550e8400-e29b-41d4-a716-446655440000
              ────────────────────────────────────
              This unique ID stays the same from
              originating bank → correspondent → beneficiary bank
```

### Standalone Validation

You can also validate an existing ISO 20022 XML message without translating:

1. Click the **"Validate"** tab
2. Paste your ISO 20022 XML
3. Click **"Validate"**
4. See which rules pass ✅ and which fail ❌

### What Happens If I Submit an MT202 When It Should Be MT202COV?

The system detects this automatically and returns an error:

```
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ SWIFT ISO MUTATION DENIED                               │
│                                                             │
│  This MT202 message contains customer credit transfer data  │
│  (ordering customer or beneficiary fields).                 │
│                                                             │
│  ✅ Action Required:                                        │
│  Submit this message as MT202COV to include the            │
│  UndrlygCstmrCdtTrf block required by CBPR+ rules.         │
└─────────────────────────────────────────────────────────────┘
```

This protection prevents regulatory violations.

---

## 8. Module 3: Knowledge (AI Learning Assistant)

**URL:** `http://localhost:3000/learn`

> **Purpose:** Ask any question about ISO 20022, SWIFT, payment systems, and get expert answers from AI.  
> **Non-technical analogy:** Like ChatGPT, but specially trained on payment standards and compliance.

### The Interface

```
┌─────────────────────────────────────────────────────────────┐
│  TOPICS SIDEBAR      │  CHAT INTERFACE                      │
│  ────────────────    │  ─────────────────────────────────   │
│  pacs.008 Customer   │                                      │
│  Transfer            │   You: Explain pacs.008 settlement   │
│                      │                                      │
│  pacs.009 FI Credit  │   🤖 AI: pacs.008.001.08 is the     │
│  Transfer — CORE     │   ISO 20022 equivalent of SWIFT      │
│                      │   MT103. It carries the full chain:  │
│  pacs.009 — COV      │   <DbtrAgt> (ordering bank BIC),    │
│                      │   <Dbtr> (ordering customer with     │
│  MT103 Field         │   IBAN in <DbtrAcct><Id><IBAN>)...  │
│  Breakdown           │                                      │
│                      │   ─────────────────────────────────  │
│  SWIFT CBPR+         │   [Ask about ISO 20022, CBPR+...  ] │
│  Guidelines          │                              [Send ▶]│
└─────────────────────────────────────────────────────────────┘
```

### How to Ask Questions

1. **Click a topic** in the left sidebar to ask about a specific area, OR
2. **Type your question** in the text box at the bottom
3. Press **Enter** to send (or **Shift+Enter** for a new line)
4. Wait 2-5 seconds for the AI response

### Example Questions to Try

| Question | What you'll learn |
|----------|------------------|
| "What is a UETR and why is it important?" | End-to-end payment tracking |
| "Explain the difference between MT202 and MT202COV" | Cover payment structure |
| "What are the mandatory CBPR+ fields in pacs.008?" | CBPR+ compliance requirements |
| "How does a Nostro account work?" | Correspondent banking basics |
| "What is TARGET2 and how does it settle payments?" | European payment system |
| "Walk me through a cross-border USD payment from Germany to France" | Full settlement chain |

### Using Context (Advanced)

You can paste an XML snippet or MT message along with your question to get more specific answers:

```
Example:
"Here is my pacs.008 message: [paste XML here]
 Can you tell me if the <IntrBkSttlmAmt> element is correct?"
```

The AI will analyze your specific message and give targeted feedback.

### AI Response Quality

The AI is configured with a **Financial Domain System Prompt** that tells it to:
- Always reference exact XML element paths (like `<DbtrAgt><FinInstnId><BICFI>`)
- Describe the full settlement chain when explaining flows
- Distinguish clearly between MT (legacy) and MX (ISO 20022) concepts
- Give structured, zero-fluff answers

---

## 9. Module 4: Documents (Document Intelligence)

**URL:** `http://localhost:3000/documents`

> **Purpose:** Upload compliance documents (PDFs) and ask questions about their content using AI.  
> **Non-technical analogy:** Like having a very smart assistant who has read all your reference documents and can answer questions about them instantly.

### Step 1: Upload a Document

```
┌─────────────────────────────────────────────────────────────┐
│  UPLOAD COMPLIANCE DOCUMENT                                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │        📄 Drag & Drop PDF here                      │   │
│  │                                                     │   │
│  │           or click to browse                        │   │
│  │                                                     │   │
│  │     Supports: PDF files up to 50MB                 │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  After upload, the system:                                  │
│  1. Extracts text from the PDF                              │
│  2. Splits it into searchable chunks                        │
│  3. Creates AI embeddings for smart search                  │
│  4. Stores everything in the vector database                │
└─────────────────────────────────────────────────────────────┘
```

> ⏱️ Processing takes 10-60 seconds depending on document size.

### Step 2: View Indexed Documents

After uploading, documents appear in the **Document Library**:

```
┌─────────────────────────────────────────────────────────────┐
│  DOCUMENT LIBRARY                                           │
│  ──────────────────────────────────────────────────────     │
│  📄 SWIFT_CBPR_Plus_Guidelines_2024.pdf    324 chunks  ✓   │
│  📄 ISO_20022_pacs_Message_Guide.pdf       891 chunks  ✓   │
│  📄 BIS_Cross_Border_Payments_Report.pdf   156 chunks  ✓   │
└─────────────────────────────────────────────────────────────┘
```

### Step 3: Query Your Documents

```
┌─────────────────────────────────────────────────────────────┐
│  ASK ABOUT YOUR DOCUMENTS                                   │
│                                                             │
│  [What are the mandatory fields for pacs.008 per CBPR+?] 🔍 │
│                                                             │
│  🤖 Based on your uploaded SWIFT CBPR+ Guidelines:         │
│                                                             │
│  The following fields are mandatory in pacs.008.001.08:    │
│  1. GrpHdr/MsgId — Message Identification                  │
│  2. GrpHdr/CreDtTm — Creation DateTime                     │
│  3. GrpHdr/NbOfTxs — Number of Transactions                │
│  4. CdtTrfTxInf/PmtId/UETR — Mandatory for CBPR+          │
│  ...                                                        │
│                                                             │
│  Sources: SWIFT_CBPR_Plus_Guidelines_2024.pdf (p.34, p.67) │
└─────────────────────────────────────────────────────────────┘
```

The AI answers are **grounded in your documents** — it cites the specific source documents and page/section it used.

### What Documents Work Best?

✅ **Good documents to upload:**
- SWIFT CBPR+ Guidelines
- ISO 20022 message specifications
- Regulatory compliance frameworks
- Internal payment processing procedures
- Central bank guidelines

❌ **Not suitable:**
- Scanned image PDFs (no text layer)
- Password-protected PDFs
- Very large files (500MB+)

---

## 10. Module 5: Audit & Telemetry

**URL:** `http://localhost:3000/audit`

> **Purpose:** View the complete, tamper-proof record of every operation on the platform, plus a live feed of events.  
> **Non-technical analogy:** Like a security camera recording combined with a building entry log — everything is recorded and cannot be altered.

### The Two-Panel View

```
┌─────────────────────────────────────────────────────────────┐
│  AUDIT LOG                    │  LIVE TELEMETRY FEED        │
│  ──────────────────────────   │  ───────────────────────    │
│  FILTERS:                     │  ● TRANSLATION_COMPLETE     │
│  [Event Type ▼] [Module ▼]   │    MT103 → pacs.008 ✓      │
│  [From Date] [To Date]        │    0.2s ago                 │
│                               │                             │
│  #a1b2c3  TRANSLATION  ✓     │  ● LEARN_QUERY_COMPLETE     │
│  24/05/26  translate          │    "pacs.008 settlement"    │
│  MT103 → pacs.008             │    1.3s ago                 │
│  Hash: 3a7bd3e2...            │                             │
│                               │  ● DOCUMENT_INDEXED         │
│  #d4e5f6  LEARN_QUERY  ✓     │    CBPR_Guidelines.pdf      │
│  24/05/26  learn              │    5.2s ago                 │
│  "pacs.008 fields"            │                             │
│                               │  [Streaming live...]        │
│  [← Prev] Page 1 of 12 [Next→]│                             │
└─────────────────────────────────────────────────────────────┘
```

### Understanding Audit Log Entries

Each row in the audit table represents one recorded event:

| Column | Meaning |
|--------|---------|
| **Audit ID** | Unique identifier for this specific event |
| **Timestamp** | Exact date and time (UTC) |
| **Event Type** | What happened (TRANSLATION, LEARN_QUERY, DOCUMENT_UPLOAD, etc.) |
| **Module** | Which part of the system did it |
| **Status** | SUCCESS ✅ / ERROR ❌ / PARTIAL ⚠️ |
| **UETR** | Payment reference (only for translation events) |
| **Hash** | Cryptographic proof — if this changes, the log was tampered with |

### Filters

You can filter the audit log by:
- **Event Type**: See only translations, or only AI queries
- **Module**: Filter by translate, learn, documents
- **Date Range**: View a specific time period

### Exporting Audit Data

Click **"Export Bundle"** to download the complete audit log as an NDJSON file. This is useful for:
- Regulatory reporting
- External audits
- Backup purposes

### The Hash Chain — Tamper Proof Explained

```
Entry 1: [data] → hash_1 = "abc123..."
Entry 2: [data] + hash_1 → hash_2 = "def456..."
Entry 3: [data] + hash_2 → hash_3 = "ghi789..."
```

If someone tries to modify Entry 1, hash_1 would change, which would make hash_2 invalid, which would make hash_3 invalid, and so on. This means **any tampering is immediately detectable**.

### Live Telemetry Feed

The right panel shows events in real-time. The connection is maintained via WebSocket — you can see events appearing within 1-2 seconds of them happening. 

Color coding:
- 🔵 **Blue/Cyan** — INFO events (normal operations)
- 🟡 **Amber** — WARN events (something to note)
- 🔴 **Red** — ERROR events (something went wrong)

---

## 11. ⚙ LLM Configuration — Switching AI Providers

**Access:** Click **"LLM Config"** button in the sidebar (bottom of System section)

> **Purpose:** Switch between different AI providers and models without restarting the system.  
> **Why this matters:** Different AI providers have different rate limits, costs, and quality. When one hits its limit (like a quota error), switch to another instantly.

### The Config Panel

```
┌─────────────────────────────────────────────────────────────┐
│  ⚡ LLM Configuration                                   [X] │
│  Switch providers · models · API keys in real-time          │
│  ─────────────────────────────────────────────────────────  │
│  ACTIVE: ⚡ Groq · llama-3.3-70b-versatile  [Key: gsk_****] │
│                                                             │
│  [Configure] [History (3)]                                  │
│                                                             │
│  PROVIDER                                                   │
│  ┌──────────────┐ ┌──────────────┐                         │
│  │✦ Google      │ │⚡ Groq       │  ← Currently selected   │
│  │  Gemini      │ │  (selected)  │                         │
│  └──────────────┘ └──────────────┘                         │
│  ┌──────────────┐ ┌──────────────┐                         │
│  │◆ OpenAI      │ │◉ Ollama      │                         │
│  │              │ │  (Local)     │                         │
│  └──────────────┘ └──────────────┘                         │
│                                                             │
│  MODEL                                                      │
│  [Llama 3.3 70B Versatile (Recommended) ▼]                 │
│                                                             │
│  API KEY (leave blank to keep current)                      │
│  [gsk_...                              👁]                  │
│                                                             │
│  [🔄 Test Connection]  [⚡ Apply Configuration]             │
└─────────────────────────────────────────────────────────────┘
```

### How to Switch Providers

#### Scenario: Gemini quota exhausted, switching to Groq

1. Click **"LLM Config"** in the sidebar
2. Click the **"⚡ Groq"** provider button
3. Select model: **"Llama 3.3 70B Versatile (Recommended)"**
4. Paste your Groq API key in the API Key field: `gsk_...`
5. Click **"🔄 Test Connection"** — wait for ✅ confirmation
6. Click **"⚡ Apply Configuration"**
7. You'll see: ✅ "Switched to ⚡ Groq · llama-3.3-70b-versatile"

**The change is immediate** — next question in Knowledge tab uses Groq, no restart needed.

### Available Providers

| Provider | Best For | Key Format | Free Tier |
|----------|---------|-----------|-----------|
| **✦ Gemini** | General purpose, multimodal | `AIzaSy...` | Yes (rate limited) |
| **⚡ Groq** | Speed (fastest inference) | `gsk_...` | Yes (generous) |
| **◆ OpenAI** | Highest quality responses | `sk-...` | No (paid) |
| **◉ Ollama** | Privacy (runs locally) | No key needed | Yes (free, local) |

### The History Tab

Shows the last 25 configuration changes:

```
┌─────────────────────────────────────────────────────────────┐
│  HISTORY (3)                                                │
│  ─────────────────────────────────────────────────────────  │
│  [CURRENT] ⚡ Groq                           10:15:23 AM    │
│  Model: llama-3.3-70b-versatile                            │
│  Key: gsk_eCCC****DUg0                                     │
│                                                             │
│  ✦ Google Gemini                             09:42:11 AM    │
│  Model: gemini-2.0-flash                                    │
│  Key: AIzaSy****gmhg                                       │
│                                                             │
│  ✦ Google Gemini                             09:30:00 AM    │
│  Model: gemini-2.0-flash                                    │
│  Key: AIzaSy****gmhg                                       │
└─────────────────────────────────────────────────────────────┘
```

> 🔐 **Security note:** API keys are NEVER stored in full. Only the first 8 and last 4 characters are shown (e.g., `AIzaSyAh****gmhg`). Keys in memory are cleared when the server restarts.

---

## 12. Real-Time Features

### How Real-Time Updates Work

The platform uses a technology called **WebSocket** — a permanent two-way connection between your browser and the server. Unlike normal web pages that you have to refresh, this connection pushes updates to your screen instantly.

```
Your Browser  ←────────────────────────────────────  Server
              WebSocket connection (permanent pipe)
              
              TRANSLATION_COMPLETE event pushed!  →
              LEARN_QUERY_COMPLETE event pushed!  →
              DOCUMENT_INDEXED event pushed!      →
```

### Where You See Real-Time Updates

| Location | What Updates |
|----------|-------------|
| **Dashboard → Live Feed** | All platform events |
| **Audit page → Telemetry panel** | All events with severity colors |
| **Sidebar → Health dot** | API health status (30s polling) |
| **Sidebar → Uptime counter** | Increments every second |

### What Each Event Means

| Event | Trigger |
|-------|---------|
| `TRANSLATION_COMPLETE` | A MT→MX translation just finished |
| `VALIDATION_COMPLETE` | An XML validation just completed |
| `LEARN_QUERY_COMPLETE` | An AI question just got answered |
| `DOCUMENT_INDEXED` | A PDF was successfully uploaded and processed |
| `CONNECTED` | A new browser tab connected to the telemetry stream |
| `SYSTEM_STARTUP` | The backend server started |
| `SYSTEM_SHUTDOWN` | The backend server stopped |

---

## 13. Common Workflows

### Workflow 1: Daily Compliance Check

```
1. Open http://localhost:3000
2. Check Dashboard → "System Nominal" (green dot) ✓
3. Navigate to TX Engine
4. Paste your incoming MT messages one by one
5. For each: Select type → Paste → Click Translate
6. Review validation results
7. If ❌ errors: Read the error description, fix the source message
8. Navigate to Audit page to export today's log for records
```

### Workflow 2: Learning a New Standard

```
1. Navigate to Knowledge
2. Browse topics in the left sidebar
3. Click "pacs.008 FI-to-FI Customer Credit Transfer"
4. Read the auto-generated explanation
5. Ask follow-up questions in the chat box
6. Paste sample XML from TX Engine for AI to analyze
7. The AI explains each field in plain English
```

### Workflow 3: Research with Uploaded Documents

```
1. Download SWIFT CBPR+ Guidelines PDF from swift.com
2. Navigate to Documents
3. Drag-and-drop the PDF
4. Wait for "✓ 324 chunks indexed" confirmation
5. Ask: "What are the mandatory fields for cross-border payments?"
6. The AI answers using YOUR uploaded document as the source
7. It cites which pages the answer came from
```

### Workflow 4: Handling a Quota Error

```
You see: [LLM ERROR] Gemini API error 429: You exceeded your quota

1. Click "LLM Config" in the sidebar
2. Select "⚡ Groq"
3. Choose "Llama 3.3 70B Versatile"
4. Enter your Groq API key (gsk_...)
5. Click "Test Connection" → confirm ✅
6. Click "Apply Configuration"
7. Go back to Knowledge and try your question again
```

---

## 14. Troubleshooting

### ❌ "API Degraded" in sidebar

**Cause:** Backend server is not running  
**Fix:** 
```bash
cd d:\WirePaymentAssistance\backend
uvicorn main:app --reload --port 8000
```

### ❌ "[MOCK MODE — No API key]" in Knowledge

**Cause:** No LLM API key is configured  
**Fix:** Click "LLM Config" → Select provider → Enter API key → Apply

### ❌ "[LLM API ERROR] 429: You exceeded your quota"

**Cause:** API key has hit its rate/quota limit  
**Fix:** Switch to a different provider via LLM Config (see Workflow 4 above)

### ❌ Translation returns "PARTIAL" status

**Cause:** Message translated successfully but has minor CBPR+ warnings  
**Fix:** Review the listed validation errors. They're often informational and the message may still be usable.

### ❌ Document upload fails

**Cause:** File may be too large, not a PDF, or image-only (no text layer)  
**Fix:** Try a text-based PDF. Check the backend console for the specific error.

### ❌ WebSocket disconnects (telemetry stops updating)

**Cause:** Network interruption or backend restart  
**Fix:** Refresh the browser page. The connection re-establishes automatically.

### ❌ LLM Config "Test Connection" returns error

**Cause:** Wrong API key format, key expired, or no internet  
**Fix:** 
- Gemini key should start with `AIzaSy`
- Groq key should start with `gsk_`
- OpenAI key should start with `sk-`
- Check your internet connection
- Verify the key hasn't been revoked in the provider's dashboard

---

## 15. Glossary — Plain English Definitions

| Term | Plain English Explanation |
|------|--------------------------|
| **ISO 20022** | The new international standard for financial messages, using XML format. Like a universal language for banks worldwide. |
| **SWIFT MT** | The old SWIFT messaging format (MT103, MT202, etc.). Being retired by 2025. |
| **MT103** | A SWIFT message for sending money from one customer to another (like an international wire transfer). |
| **MT202** | A SWIFT message for bank-to-bank payments (no customer details). |
| **MT202COV** | Like MT202 but includes the original customer payment details underneath ("cover" payment). |
| **pacs.008** | The ISO 20022 version of MT103 (customer credit transfer). |
| **pacs.009** | The ISO 20022 version of MT202/MT202COV (financial institution credit transfer). |
| **pacs.004** | The ISO 20022 version of a payment return (sending money back). |
| **CBPR+** | Cross-Border Payments and Reporting Plus — SWIFT's rules for how ISO 20022 must be used in cross-border payments. |
| **MX** | The colloquial term for ISO 20022 messages (because they start with an "M" and use XML). |
| **UETR** | Unique End-to-end Transaction Reference — a tracking number (like a parcel tracking ID) that follows a payment through every bank. UUID4 format. |
| **XSD** | XML Schema Definition — a file that defines the rules for what valid ISO 20022 XML looks like. |
| **BIC** | Bank Identifier Code — the bank's unique address code (like DEUTDEDB for Deutsche Bank). |
| **IBAN** | International Bank Account Number — the customer's account number (like DE89370400440532013000). |
| **RAG** | Retrieval-Augmented Generation — AI technique where the model searches your documents first, then answers based on what it found (so it doesn't make things up). |
| **LLM** | Large Language Model — the AI engine that understands and generates text (e.g., Gemini, Groq, GPT-4). |
| **Nostro** | "Our account at your bank" — an account a bank holds at a foreign correspondent bank. |
| **Vostro** | "Your account at our bank" — the same account seen from the other bank's perspective. |
| **Correspondent Banking** | When Bank A doesn't have a direct relationship with Bank B, they use Bank C (a correspondent) in the middle to move money. |
| **Settlement** | The actual movement of money between banks (not just the instruction to move it). |
| **NDJSON** | Newline-Delimited JSON — an audit log format where each line is a separate JSON record. |
| **SHA-256** | A cryptographic algorithm that creates a unique fingerprint for data. If the data changes even slightly, the fingerprint completely changes. |
| **Hash Chain** | Using each record's fingerprint as input to the next — creates an unbreakable chain that reveals any tampering. |
| **WebSocket** | A permanent two-way connection between browser and server — enables real-time updates without refreshing. |
| **FastAPI** | The Python web framework powering the backend API. Known for speed and automatic documentation. |
| **Next.js** | The React framework powering the frontend. Handles routing, rendering, and performance. |
| **uvicorn** | The server that runs the Python/FastAPI application. |
| **TARGET2** | Trans-European Automated Real-time Gross Settlement Express Transfer — the Eurozone's main payment settlement system. |
| **FedNow** | The US Federal Reserve's real-time payment system (launched 2023). |
| **CHAPS** | Clearing House Automated Payment System — the UK's high-value payment settlement system. |

---

*© 2026 The Compliance Leader. This manual is for authorized users only.*  
*For technical support, check the backend console output and the Audit page for error details.*
