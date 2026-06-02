# PropEngine Support Agent — System Architecture

> **Purpose:** A map of all the moving parts — what each folder/file does, how a request
> flows end-to-end, where data is written, and the known issues/risks. Verified against the
> code (not older docs). Last mapped: 2026-06.

---

## 1. System Overview

An AI-powered knowledge-base support agent (RAG — Retrieval-Augmented Generation). A user
asks a question; the system retrieves relevant KB content from a vector database and uses an
LLM to generate a grounded answer, escalating to a human (Freshdesk ticket) when it can't help.

**External services it depends on:**

| Service | Used for |
|---|---|
| **OpenAI** | Embeddings (`text-embedding-3-small`) + chat completions (`gpt-4o-mini`) |
| **AstraDB** | Vector database — stores embedded KB chunks, does similarity search |
| **Firebase/Firestore** | Persistent storage — sessions, messages, analytics, feedback, failures, users |
| **Redis** | Fast cache — recent conversation context, rolling summaries, rate-limit counters |
| **Freshdesk** | Support ticketing — escalations become tickets |

**The three agents** (same pipeline, different KB visibility — set via `user_type_filter`):

| Agent | Endpoint | Filter | Sees | Response detail |
|---|---|---|---|---|
| **Customer** | `POST /api/agent/customer/` | `external` | only `external` KB entries | minimal (no sources/confidence) |
| **Support** | `POST /api/agent/support/` | `internal` | only `internal` KB entries | sources + confidence |
| **Test** | `POST /api/agent/test/` | `None` | **all** entries | full debug metrics |

---

## 2. Folder / File Responsibility Map

```
main.py                         App entry: FastAPI setup, CORS, global error handlers, router wiring, lifespan
src/
├── api/                        HTTP LAYER — request/response, routing, validation
│   ├── customer_agent_routes.py   Customer agent endpoint (external KB only)
│   ├── support_agent_routes.py    Support agent endpoint (internal KB only)
│   ├── test_agent_routes.py       Test/debug agent (no filter) + session/history inspection
│   ├── kb_routes.py + kb/          KB CRUD: entries, vectors (sync), documents (upload), duplicates
│   ├── feedback_routes.py          Thumbs up/down on responses
│   ├── agent_failure_routes.py     Escalation records + Freshdesk ticket creation + webhook
│   ├── user_routes.py              User management (Firebase Auth + Firestore)
│   ├── session_endpoints.py        End session, should-end checks
│   ├── dashboard_routes.py         Analytics dashboard metrics
│   ├── admin_routes.py             Admin: stats, session mgmt, Redis flush, KB analytics
│   └── health_routes.py            Health checks (/api/health/, /api/health/ping)
│
├── agent/                      THE QUERY PIPELINE (orchestration + reasoning)
│   ├── orchestrator.py            Agent.process_query() — coordinates the whole pipeline
│   ├── classification/            QueryClassifier — regex-based query-type detection
│   ├── query_processing/          QueryIntelligence (LLM) + QueryBuilder (structured query)
│   ├── context/                   ContextBuilder, ContextResponder (answer-from-conversation), ContextAnalyzer
│   ├── search/                    SearchStrategy (fallback tiers), ParentDocumentRetrieval
│   ├── response/                  ResponseGenerator — LLM answer generation + templated replies
│   └── escalation/                EscalationHandler (LLM escalation-intent detection)  ⚠️ see issues
│
├── query/                      RETRIEVAL PRIMITIVES
│   ├── vector_search.py           Embed query → AstraDB similarity search → filter by threshold
│   └── reranker.py                Heuristic re-scoring of results (keywords, title, query-type)
│
├── services/                   INTEGRATIONS + KB INGESTION
│   ├── vector_sync/               chunking.py + document_chunking.py + server.py (entry → chunks → AstraDB)
│   ├── astradb/server.py          AstraDB vector store operations
│   ├── firebase/server.py         Firebase service wrapper for KB entries
│   └── freshdesk_service.py       Freshdesk ticket creation
│
├── document_processing/        FILE INGESTION
│   ├── extractors.py              DOCX (python-docx) + PDF (PyMuPDF/pdfplumber/pypdf) text extraction
│   ├── structure_analyzer.py      LLM (gpt-4o-mini) structures extracted text into sections
│   └── entry_builder.py           Converts extracted structure → KB entry format
│
├── memory/                     SESSION + CONVERSATION STATE
│   ├── session_manager.py         Orchestrates Redis + Firebase + in-memory fallback (coordinator)
│   ├── redis_message_store.py     RedisContextCache — recent messages, summaries
│   ├── session_analytics.py       Buffers per-query metrics, batch-writes at session end
│   ├── session_fallback.py        In-memory backup when Redis/Firebase down
│   └── kb_analytics.py            KBAnalyticsTracker — per-KB-entry usage stats (kb_stats)
│
├── database/                   PERSISTENCE CLIENTS
│   ├── astra_client.py            AstraDB connection + OpenAI embeddings singleton
│   ├── firebase_client.py         Firebase Admin SDK init + Firestore client
│   ├── firebase_session_service.py    Session/message persistence
│   ├── firebase_analytics_service.py  Analytics persistence
│   ├── firebase_feedback_service.py   Feedback persistence
│   ├── firebase_agent_failure_service.py  Failure/escalation persistence
│   └── redis_client.py            Redis connection
│
├── analytics/                  METRICS + COST
│   ├── collectors/metrics_collector.py  Per-query execution metrics
│   ├── tracking/token_tracker.py        Token usage extraction from LLM responses
│   ├── tracking/cost_calculator.py      Token → $ via model_pricing.yaml
│   └── models/                          Pydantic models (QueryMetrics, CostBreakdown, TokenUsage)
│
├── prompts/                    PROMPT MANAGEMENT
│   └── prompt_loader.py            Loads YAML prompt templates, interpolates variables
│
├── config/                     CONFIGURATION
│   ├── settings.py                Env-based settings (models, thresholds, service creds)
│   ├── rate_limits.py             Rate-limit tiers  ⚠️ see issues (DEV limits active)
│   └── performance.py             Performance/logging flags
│
└── utils/                      SHARED UTILITIES
    ├── logging_helper.py          StructuredLogger (emoji-prefixed structured logs)
    ├── rate_limiter.py            Redis-backed rate limiting
    ├── chat_summary.py            Conversation summarization
    └── failsafe.py                Safe-execution helpers
```

---

## 3. The Request Lifecycle (a query, end-to-end)

`orchestrator.process_query()` is the spine. Steps (matching the `# === STEP n ===` comments):

```
1.  Store user message            → Redis (session_manager.add_message)
2.  Load conversation context     → Redis (recent messages + rolling summary)
3.  Classify query                → QueryClassifier (regex, NO LLM) → greeting/farewell/escalation/error/howto/etc.
4.  Conversational shortcut       → if greeting/farewell/escalation: templated reply, return early (1 LLM call, no search)
5.  Follow-up detection           → fast regex (_is_likely_followup, NO LLM)
        if follow-up  → QueryIntelligence.analyze()  (1 LLM call: routing + query enhancement)
        if not        → skip QI, use raw query  (saves ~2200ms)
6.  Route                         → if "answer_from_context": ContextResponder (1 LLM call), return early
                                    else continue to search
7.  Search (+fallback tiers)      → SearchStrategy.search_with_fallback() → embed query → AstraDB → filter
8.  No results?                   → templated fallback, set escalation=true, return (NO LLM call)
9.  Rerank                        → SearchReranker (heuristic, NO LLM)
9.5 Clarification?                → error queries w/ ambiguous results → ask for specifics
10. Build context                 → ContextBuilder (top chunks + source metadata)
11. Generate response             → ResponseGenerator.generate_response() (1 LLM call)
12-13. Cost + metadata            → token/cost aggregation, confidence, escalation decision
14. Persist (fire-and-forget)     → session write + KB analytics (background, non-blocking)
```

**LLM calls per query:** greeting/escalation = 1 · normal search = 1 · follow-up = 2 (QI + response) ·
no-results = 0 (templated).

---

## 4. Subsystem Deep-Dives

### 4a. Classification & Routing
- **`QueryClassifier`** uses **regex only** (no LLM, <1ms). Types: `greeting, farewell, escalation,
  error, definition, howto, workflow, general`. Returns `(type, confidence)`.
- Greeting/farewell/escalation short-circuit the pipeline (templated reply, no search).

### 4b. Query Intelligence & Follow-up Detection
- **Follow-up** is detected by fast regex first (`FOLLOWUP_PATTERNS` + pronoun heuristic). Only if it
  looks like a follow-up does the **`QueryIntelligence` LLM call** run — which does routing
  (`answer_from_context` / `full_rag`) and query enhancement in one shot. This is a deliberate
  latency optimization (skips a ~2200ms LLM call for non-follow-ups).

### 4c. Search & Retrieval
- **Embedding:** query → `OpenAIEmbeddings(text-embedding-3-small)` (`astra_client.py`), async.
- **Vector search:** AstraDB `similarity_search_with_score_by_vector`, filtered by `entryType` +
  `userType`, threshold `MIN_CONFIDENCE_SCORE = 0.50`, up to `MAX_SEARCH_RESULTS = 6`.
- **Fallback tiers** (`search_strategy.py`): primary (typed) → parent-doc expansion → drop type
  filter → howto↔error cross-type → definition-with-error. Embeddings are cached and reused across tiers.
- **Parent retrieval:** for "comprehensive" queries (e.g. "step by step", "guide"), expands matched
  child chunks into their full parent documents.
- **Rerank:** heuristic re-scoring (query-type match, keyword density, title match, length) → top 3.

### 4d. Response Generation
- **`ResponseGenerator`** builds the final answer from retrieved contexts + conversation context via
  one LLM call. No-results path returns a **fixed template** (no LLM) to prevent hallucination.

### 4e. Escalation & Ticketing
- Escalation is flagged when: user explicitly asks (classified `escalation`), no results found, or
  `confidence < 0.7` / response contains failure phrases.
- Flagged escalation → frontend calls `POST /api/agent-failure/` (record) → user accepts →
  `POST /api/agent-failure/{id}/create-ticket` → `FreshdeskService` creates the ticket → webhook
  updates closure. **Ticket creation is user-initiated, not fully automatic.**

### 4f. KB Ingestion
- **Template entries:** `POST /api/kb/entries` → Firebase; `…/sync` → chunk → embed → AstraDB.
- **Document uploads:** extract (DOCX/PDF) → LLM structure analysis → build entry → Firebase → sync.
- **Chunking** is section-aware, preserving position/section/neighbour-summary context per chunk.
- **Deduplication** (`/api/kb/check-duplicates`) is **semantic** (vector similarity ≥ 0.70) + a title-similarity boost.

### 4g. Memory / Persistence — what's written where

| Event | Redis | Firestore | In-memory fallback |
|---|---|---|---|
| User/assistant message | ✅ `context:{sid}` (last 8, 2h TTL) | ❌ | ✅ |
| Rolling summary (every 5 msgs) | ✅ `session:{sid}:summary` | ❌ | ✅ |
| Session create | ❌ | ✅ `kb_sessions` | ✅ |
| Session end | (cleared) | ✅ `kb_sessions` + batch `kb_analytics` | (cleared) |
| KB entry usage | ❌ | ✅ `kb_stats` (instant, keyed by `parent_entry_id`) | ❌ |
| Feedback | ❌ | ✅ `response_feedback` | ❌ |
| Escalation/failure | ❌ | ✅ `agent_failures` | ❌ |

**Firestore collections:** `kb_sessions`, `kb_analytics`, `kb_stats`, `response_feedback`,
`agent_failures`, `users` (and `kb_messages` — **defined but unused**).

### 4h. Analytics, Cost & Logging
- **Per-query metrics** (`metrics_collector`): classification, search stats, timings, sources, escalation.
- **Cost:** `token_tracker` extracts token counts → `cost_calculator` × `model_pricing.yaml` → `CostBreakdown`.
- **Logging:** `StructuredLogger` (emoji-prefixed, pipe-delimited fields), standard Python logging at `LOG_LEVEL`.
- **Prompts:** YAML templates loaded + cached by `prompt_loader`.

---

## 5. ⚠️ Known Issues & Risks

> Scope note: the security/privacy items already fixed in the recent hardening pass (exception
> leaks, PII-in-logs, bare excepts, fire-and-forget safety, healthcheck, CORS) are **not** repeated
> here. Below are issues this architecture review surfaced that are **still open**.

### 🔴 Verify before / soon after deploy
| # | Issue | Where | Why it matters |
|---|---|---|---|
| A1 | **No application-level auth on any endpoint** | all of `src/api/` | Admin (Redis flush, escalate), KB write/delete, user management, dashboards are all open. Must be protected at the gateway/infra layer (GCloud IAP / API gateway / Firebase-auth-gated frontend) — **confirm this is enforced somewhere**, because the app enforces nothing. |
| A2 | **Rate limiting effectively disabled** | `rate_limits.py:103,135,142` | `ACTIVE_LIMITS` is assigned 3×; the last wins → `DEV_LIMITS` (10,000/day). Your intended 100/day isn't active. Set a single prod value. |
| A3 | **Rate-limit identity is client-supplied** | agent routes (`user_info.agent_id/email`) | A caller can change `agent_id`/`email` to reset their own counter — limits are bypassable even once A2 is fixed. |

### 🟠 High (correctness / cost / data-loss)
| # | Issue | Where | Notes |
|---|---|---|---|
| B1 | **Blocking vector-search call in async** | `vector_search.py` (sync `similarity_search_*` in async fn) | Blocks the event loop ~100-500ms/query → hurts concurrency under load. Use the async variant or `asyncio.to_thread`. |
| B2 | **Duplicate chunking implementations** | `chunking.py` vs `document_chunking.py` | ~150 lines of near-identical section-chunking. Consolidate to one parameterized chunker. |
| B3 | **Escalation logic duplicated; `EscalationHandler` unused** | `orchestrator.py` inline vs `escalation/escalation_handler.py` | Two code paths; the inline one uses fragile failure-phrase matching (a polite apology can falsely escalate). |
| B4 | **Dead / unintegrated modules** | `ContextAnalyzer`, `EscalationHandler`, `kb_messages` collection | Present but not wired into the live path → confusion + rot. Remove or integrate. |
| B5 | **In-session analytics buffer is memory-only** | `session_analytics.py` (`query_buffers`) | If the process crashes before session end, all buffered query analytics are lost (batch-written only at end). |
| B6 | **No Freshdesk API retry** | `freshdesk_service.py` | Single POST; a transient network/timeout means the ticket silently isn't created. |

### 🟡 Medium
| # | Issue | Where | Notes |
|---|---|---|---|
| C1 | **`SessionManager` instantiated ~9×** | many modules | Wasteful: each builds its own Redis/Firebase/fallback clients. (Data is still shared — Redis/Firebase are external stores — so this is efficiency/cleanliness, not data loss.) Make it a singleton / DI dependency. |
| C2 | **N+1 queries in parent retrieval** | `parent_retrieval.py` | One extra AstraDB query per parent doc; batch or `asyncio.gather`. |
| C3 | **Rolling summaries Redis-only (2h TTL)** | `session_manager.py` | Long sessions / Redis purge lose the summary; only a final summary is persisted. |
| C4 | **Hardcoded Freshdesk custom fields + fallback email** | `freshdesk_service.py`, `agent_failure_routes.py` | `cf_*` fields must match Freshdesk schema or tickets fail silently; fallback `support@…` if `user_email` missing. |
| C5 | **No per-request correlation ID** | logging | We now log `session_id`; a per-request `request_id` would make multi-line traces unambiguous. |
| C6 | **Token→byte chunk sizing is approximate** | `chunking.py` (`ASTRA_MAX_CONTENT_BYTES=7500`, ~4 chars/token) | Could exceed AstraDB field / embedding token limits on edge cases. |

### Verification corrections (vs. older notes/assumptions)
- Embedding model is **`text-embedding-3-small`** (1536-dim), not `-large`.
- `SessionManager` non-singleton does **not** cause cross-instance message loss (Redis/Firebase are shared) — it's an efficiency issue only.
- Intended rate limits (100/day) are **not** the active ones (see A2).

---

## 6. Where to look first (onboarding shortcuts)
- **"How does a question get answered?"** → `src/agent/orchestrator.py` (`process_query`).
- **"How does search work?"** → `src/query/vector_search.py` + `src/agent/search/search_strategy.py`.
- **"How is a KB article stored?"** → `src/services/vector_sync/server.py` + `chunking.py`.
- **"Where's conversation state?"** → `src/memory/session_manager.py`.
- **"How do escalations become tickets?"** → `src/api/agent_failure_routes.py` + `src/services/freshdesk_service.py`.
