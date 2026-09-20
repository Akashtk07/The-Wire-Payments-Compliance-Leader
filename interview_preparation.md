# 🚀 THE COMPLIANCE LEADER: ULTIMATE INTERVIEW PREPARATION MASTERCLASS

*A comprehensive system design, architecture, AI/GenAI, and full-stack interview preparation guide based on the actual implementation of The Compliance Leader.*

---

## 📑 TABLE OF CONTENTS

* [SECTION A — MY PROJECT](#section-a--my-project)
* [SECTION B — PROJECT INTERVIEW QUESTIONS](#section-b--project-interview-questions)
* [SECTION C — GENERAL TECHNICAL INTERVIEW](#section-c--general-technical-interview)
* [SECTION D — SCENARIO INTERVIEWS](#section-d--scenario-interviews)
* [SECTION E — PREPARATION](#section-e--preparation)

---

# SECTION A — MY PROJECT

## 1. Project Overview
**The Compliance Leader** is a full-stack ISO 20022 financial compliance workstation. It translates legacy SWIFT MT messages to the ISO 20022 MX format (e.g., pacs.008), validates them against strict CBPR+ R2025 rules, and features an integrated AI-powered RAG (Retrieval-Augmented Generation) engine to allow banking operators to query complex compliance guidelines in natural language.

## 2. Architecture
* **Backend**: FastAPI (Python), Async endpoints, REST architecture.
* **Frontend**: Next.js 14 (App Router), React, Tailwind CSS.
* **Database**: SQLite (via SQLAlchemy) for relational data (users, auth, configs).
* **Vector Database**: ChromaDB (Persistent Client) for document embeddings.
* **LLM Engine**: Multi-provider router supporting Gemini, OpenAI, Groq, and local Ollama.
* **Audit System**: Hash-chained NDJSON append-only logs for tamper evidence.
* **Telemetry**: Real-time WebSocket broadcasting for dashboard metrics.

## 3. RAG Implementation (Source of Truth)
* **Embedding Model**: `all-MiniLM-L6-v2` (SentenceTransformers, 384 dimensions).
* **Chunking Strategy**: Naive word-based (sliding window approximation).
* **Chunk Size**: 512 tokens (words).
* **Overlap**: 64 tokens (words).
* **Vector DB**: ChromaDB with HNSW index configured for `cosine` similarity (`"hnsw:space": "cosine"`).
* **Ingestion**: PyMuPDF for PDFs, `python-pptx` for PPTX, `python-docx` for Word.
* **Retrieval**: Top-K semantic search (default K=5). 

## 4. LLM Implementation
* **Routing**: Handled by `llm_router.py`. Reads configurations at runtime from a Singleton `llm_config_store`.
* **Resilience**: Implements asynchronous exponential backoff retries (3 attempts).
* **Fallback**: Graceful fallback to a local mock diagnostic mode if no API key is set.
* **System Prompt**: Enforces strict financial rules (CBPR+ R2025, UETR mandates, SDVA).

## 5. Security & Authentication
* **Auth**: JWT (HS256) access (60 min) and refresh tokens (7 days).
* **Hashing**: bcrypt (cost factor 12).
* **Verification**: 6-digit OTP sent via Gmail SMTP TLS.
* **Defense**: Account lockout mechanism (5 failed attempts = 30 min lock).

---

# SECTION B — PROJECT INTERVIEW QUESTIONS

### Q: Tell me about your project in 2 minutes.
**Short Interview Answer:** I built a full-stack financial compliance platform that translates legacy SWIFT payment messages into the modern ISO 20022 format and validates them against strict CBPR+ rules. To help banking operators navigate these complex regulations, I also engineered a custom RAG (Retrieval-Augmented Generation) pipeline that lets users query compliance documents in natural language. The system is built with FastAPI, Next.js, and ChromaDB, and includes enterprise features like tamper-evident hash-chained audit logging and multi-provider LLM routing.
**Why it exists:** The banking industry is migrating to ISO 20022, and operators struggle with the new XML formats and massive rulebooks.
**Advantages:** Replaces manual rulebook searching and manual translation with an automated, AI-assisted workflow.

### Q: Why did you choose this architecture? (FastAPI + Next.js + ChromaDB)
**Short Interview Answer:** I chose FastAPI because the heavy lifting of the application involves XML parsing, vector processing, and asynchronous network calls to LLMs, which Python handles beautifully. Next.js was chosen for the frontend because its App Router provides excellent structure and performance for a dashboard application. ChromaDB was selected as the vector store because it embeds seamlessly into a Python backend without requiring external infrastructure management.
**Trade-offs:** Python isn't as fast as Go or Rust for raw CPU tasks (like massive XML parsing), but the ecosystem for AI (sentence-transformers) and rapid API development (Pydantic/FastAPI) outweighed the raw CPU speed requirements for our scale.

## RAG & AI Deep Dive

### Q: What embedding model did you use and why?
**Short Interview Answer:** I used `all-MiniLM-L6-v2`. It produces 384-dimensional embeddings.
**Why did you choose it?** It is extremely fast, runs locally on a CPU without requiring a GPU, and provides an excellent balance of semantic accuracy vs. latency and memory footprint.
**Alternatives:** OpenAI's `text-embedding-ada-002` (1536 dims). I chose the local model to ensure sensitive financial compliance documents were not sent to a third-party embedding API, reducing data leakage risks and costs.

### Q: What chunking strategy did you use and why?
**Short Interview Answer:** I used a naive sliding-window word-based chunking strategy with a chunk size of 512 words and an overlap of 64 words.
**Why does this exist?** LLMs have context limits, and embedding entire 500-page rulebooks into a single vector dilutes the semantic meaning. Chunking breaks documents into searchable pieces.
**Why Overlap?** If a crucial concept is split exactly at the boundary of a chunk, the overlap ensures that context is preserved in at least one of the chunks. 
**Implementation (`rag_pipeline.py`):** The `_chunk_text()` function iterates through the extracted text, slicing 512 words at a time and advancing the index by 448 (512 - 64).

### Q: Why ChromaDB and Cosine Similarity?
**Short Interview Answer:** ChromaDB uses HNSW (Hierarchical Navigable Small World) graphs for fast Approximate Nearest Neighbor (ANN) searches. I configured it to use **Cosine Similarity** (`"hnsw:space": "cosine"`). 
**Why Cosine?** Cosine similarity measures the angle between two vectors, ignoring their magnitude. This is perfect for text embeddings because a short sentence and a long paragraph can have the same semantic meaning (pointing in the same direction) even if their vector lengths differ.

### Q: How is your LLM Router implemented?
**Short Interview Answer:** `llm_router.py` acts as an abstraction layer. It reads the active provider (Gemini, OpenAI, Groq, or Ollama) from `llm_config_store`. It formats the system prompt with strict CBPR+ financial context, injects the RAG retrieved chunks, and uses `httpx.AsyncClient` to make non-blocking HTTP requests to the respective APIs. 
**Resilience:** It implements a 3-attempt exponential backoff retry decorator (`_retry_async`) to handle transient API rate limits or network hiccups.

### Q: How does Hash Chaining work in your Audit system?
**Short Interview Answer:** Every audit event is serialized to JSON and hashed using SHA-256. The hash of the *previous* event is included in the payload of the *current* event.
**Why does this exist?** It creates a tamper-evident append-only log. If an attacker modifies an old log entry to hide unauthorized activity, the hash of that entry changes. This breaks the chain for every subsequent log, making the tampering immediately obvious.

---

# SECTION C — GENERAL TECHNICAL INTERVIEW

## 🧠 AI / GenAI / LLMs

### Q: What is RAG? Why not just fine-tune an LLM?
**Short Interview Answer:** RAG retrieves factual context from a database and provides it to the LLM at inference time. Fine-tuning bakes knowledge into the model's weights during training.
**Trade-offs:** RAG is much cheaper, updates instantly (just add a document to the DB), and allows citations/grounding. Fine-tuning is expensive, takes time, and the model cannot easily "unlearn" outdated rules.

### Q: What is Prompt Injection and how do you mitigate it?
**Short Interview Answer:** Prompt injection is when a user inputs text that tricks the LLM into ignoring its original instructions.
**Mitigation:** Parameterizing inputs, using strict system prompts, bounding user input with delimiters, and checking the output against a secondary guardrail model. In my project, I strictly enforce the system prompt behavior overriding user formatting.

## 🐍 Backend (Python / FastAPI / Spring Boot Concepts)

### Q: Why FastAPI over Spring Boot?
**Short Interview Answer:** FastAPI offers incredibly fast development cycles, native async support, and automatic OpenAPI documentation via Pydantic. It is the de-facto standard for AI/ML heavy backends. 
**When would I use Spring Boot?** If I were integrating with massive legacy Java banking systems (like core banking mainframes) or needed mature, out-of-the-box enterprise features like Spring Security, Spring Batch, and distributed transaction management.

### Q: What is the GIL in Python? How does FastAPI handle concurrency?
**Short Interview Answer:** The Global Interpreter Lock prevents multiple native threads from executing Python bytecodes at once. FastAPI bypasses this for I/O bound tasks using `asyncio`. When an endpoint awaits an LLM API call, the event loop pauses that coroutine and serves other requests, allowing high concurrency on a single thread.

## 🏗️ Microservices & Kafka

### Q: What problem does Kafka solve?
**Short Interview Answer:** Kafka is a distributed event streaming platform. It solves the problem of tight coupling and fragile point-to-point synchronous communication between microservices by acting as a highly scalable, fault-tolerant asynchronous message broker.
**Key Concepts:** 
* **Topic:** A category of events.
* **Partition:** Topics are split into partitions for parallel processing.
* **Consumer Group:** Ensures each message in a topic is processed by exactly one consumer in the group.

### Q: How do you handle a scenario where a database transaction succeeds but the Kafka publish fails?
**Short Interview Answer:** Use the **Transactional Outbox Pattern**.
**How it works:** Instead of publishing directly to Kafka, the service saves the event to an `Outbox` table in the *same* database transaction as the business data. A separate background process (or Debezium CDC) reads the Outbox table and reliably publishes to Kafka.

---

# SECTION D — SCENARIO INTERVIEWS

### Scenario: Retrieval returns irrelevant documents (RAG Failure)
**What do you do?** 
1. **Analyze Chunking:** Are the chunks too small and losing context? (Fix: Increase chunk size or use semantic/parent-child chunking).
2. **Analyze Embeddings:** Is the domain terminology (e.g., "pacs.008") being misunderstood by a generic embedding model? (Fix: Fine-tune the embedding model or use Hybrid Search/BM25 to catch exact keyword matches).
3. **Analyze Query:** Is the user's prompt poorly phrased? (Fix: Implement Query Expansion/HyDE to have the LLM rewrite the user's query before searching).

### Scenario: The API takes 10 seconds to respond. How do you handle it in React?
**Solution:** I would implement a loading state (`isLoading=true`) immediately upon form submission. I would display a skeleton loader or a spinner. Because LLM generation takes time, I would ideally refactor the backend to return a streaming response (Server-Sent Events or WebSockets) so the user sees the answer typing out in real-time, drastically reducing perceived latency.

### Scenario: A payment request is received twice (Idempotency).
**Solution:** I would implement an Idempotency Key. The client generates a UUID for the request. The backend checks the database or a Redis cache; if it has seen the UUID, it returns the cached response of the original transaction without reprocessing the payment.

### Scenario: The database query suddenly becomes slow.
**Debugging steps:** 
1. Run `EXPLAIN ANALYZE` on the query to see the execution plan.
2. Check if a full table scan is happening because an index is missing or ignored.
3. Check for lock contention or deadlocks.
4. Check if the table has grown massively, requiring partitioning or archiving.

---

# SECTION E — PREPARATION

## 🔥 Hot Topics in AI Interviews
* **Agentic AI & Tool Calling:** Moving beyond RAG. Giving LLMs tools (like calculators, API access, Python REPLs) to act autonomously using a ReAct (Reasoning + Acting) loop.
* **Small Language Models (SLMs):** Models like Llama-3-8B or Phi-3 that run locally, drastically reducing costs and privacy risks compared to massive frontier models.
* **Hybrid Search:** Combining dense vector search (Semantic) with sparse keyword search (BM25) and using a Cross-Encoder to Re-rank the results. This fixes the issue where vector databases fail at exact-match ID lookups.

## ⚡ 20 Rapid Fire Questions
1. **What is JWT?** JSON Web Token, a stateless way to securely transmit information between parties.
2. **What is Idempotency?** An operation that produces the same result no matter how many times it is executed.
3. **What is an Embedding?** A high-dimensional array of numbers representing the semantic meaning of text.
4. **What is Cosine Similarity?** A metric used to measure how similar two vectors are based on the angle between them.
5. **What is a Circuit Breaker?** A microservice pattern that stops calling a failing service to prevent cascading system failures.
6. **What is Dependency Injection?** A design pattern where objects are passed their dependencies rather than creating them internally, making testing much easier.
7. **What is `useEffect`?** A React hook used to perform side effects in functional components, like data fetching or subscriptions.
8. **What is Hallucination?** When an LLM confidently generates false or fabricated information.
9. **What is Chunk Overlap?** Repeating the end of one text chunk at the beginning of the next to preserve context across boundaries.
10. **What is a Consumer Group in Kafka?** A group of consumers that cooperate to consume messages from a topic, scaling processing horizontally.
11. **What is REST?** Representational State Transfer, an architectural style for APIs using standard HTTP methods and stateless communication.
12. **What is TLS?** Transport Layer Security, the cryptographic protocol that provides secure communication over a network (HTTPS).
13. **What is ACID?** Atomicity, Consistency, Isolation, Durability; the properties ensuring reliable database transactions.
14. **What is a B-Tree?** The default data structure used for database indexes, allowing logarithmic time complexity for searches.
15. **What is CORS?** Cross-Origin Resource Sharing, a browser security feature that restricts cross-origin HTTP requests.
16. **What is a Tuple vs List in Python?** Lists are mutable, Tuples are immutable.
17. **What is an Event Loop?** The core engine of async programming that executes asynchronous tasks and callbacks.
18. **What is UETR?** Unique End-to-end Transaction Reference, a mandatory UUID in modern SWIFT and ISO 20022 payments.
19. **What is Prompt Leakage?** A security vulnerability where an LLM is tricked into revealing its secret system instructions.
20. **What is Docker Compose?** A tool for defining and running multi-container Docker applications using a YAML file.

## 🏁 Final Revision Checklist
- [x] I know the exact name of my embedding model (`all-MiniLM-L6-v2`) and its dimensions (384).
- [x] I know my chunking strategy (Naive word-based, 512 size, 64 overlap).
- [x] I can explain why I chose FastAPI over Spring Boot, but I also know Spring Boot basics.
- [x] I can draw the architecture of a RAG pipeline on a whiteboard.
- [x] I know how to debug a slow database query.
- [x] I know how to handle partial microservice failures using Outbox and Circuit Breakers.

---
*Note: Due to output constraints, scenarios and rapid-fire questions have been highly curated to focus on the absolute highest-yield interview topics. Customize the behavioral sections with your personal STAR stories before the interview.*
