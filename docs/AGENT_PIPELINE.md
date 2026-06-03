# Agent Pipeline — How a Query Becomes an Answer

> **Part 2 of 2.** This covers the **support-agent product**: how a user's question is
> classified, searched, and answered. For how the knowledge itself is created, see
> [KB_INGESTION.md](KB_INGESTION.md).

---

## One pipeline, three audiences

There is a **single** retrieval + answer pipeline. The three "agents" are the *same* code
differentiated by one parameter — `user_type_filter` — which controls **which KB entries the
search is allowed to see**:

| Endpoint | `user_type_filter` | Sees KB entries tagged… |
|---|---|---|
| `POST /api/agent/customer/stream` | `external` | `external` + `both` |
| `POST /api/agent/support/stream` | `internal` | `internal` + `both` |
| `POST /api/agent/test/stream` | `None` | everything (debug/QA only) |

The route files (`src/api/customer_agent_routes.py`, `support_agent_routes.py`,
`test_agent_routes.py`) are thin wrappers — they set the filter and call the same orchestrator.

> **Auth:** all agent routes (plus feedback / KB / admin) require a valid Firebase token when
> `REQUIRE_AUTH` is on; `/` and `/api/health/` stay public. Gating is wired in `main.py` via
> `src/api/auth.py`. See [FRONTEND_AUTH.md](FRONTEND_AUTH.md).

The orchestrator lives in [`src/agent/orchestrator.py`](../src/agent/orchestrator.py); the public
entry point is `process_query_stream()`.

---

## The pipeline (streaming)

`process_query_stream()` yields NDJSON frames in a fixed order:
`session → sources → token* → metadata → done` (or `error`). The steps:

| # | Step | What happens | Cost |
|---|---|---|---|
| 1–2 | **Store + load context** | Write user message to Redis, load conversation context (recent msgs + rolling summary) | Redis |
| 3 | **Classify** | Local classifier → `query_type` (`howto`/`error`/`definition`/`greeting`/`farewell`/`escalation`) | <1ms, no LLM |
| 4 | **Greeting / farewell / escalation** | Templated reply, emitted as one chunk, return early | none |
| 5 | **Follow-up detection → Query Intelligence** | Fast regex follow-up check; **only if** follow-up, one LLM call enhances the query + decides routing | 0–1 LLM |
| 6 | **Answer-from-context** | If the question can be answered from conversation history alone, do that and return | 1 LLM |
| 7 | **Search (with fallback)** | Vector search in AstraDB **filtered by `user_type_filter`** → parent-document expansion | embedding + DB |
| 8 | **No results** | Fixed fallback message (no LLM, no hallucination), `escalated=true`, return | none |
| 9 | **Rerank** | Re-score the retrieved chunks against the enhanced query | local |
| 9.5 | **Clarification check** | For ambiguous `error` queries (tight score spread, no error code), ask the user to specify | none |
| 10 | **Build context + sources** | Assemble the prompt context, compute confidence, **emit the `sources` frame** | local |
| 11 | **Stream the answer** | `generate_response_stream()` streams the LLM answer **token-by-token** | 1 LLM (streamed) |
| 12–14 | **Finalize** | Cost breakdown, **escalation decision**, `metadata` frame; background writes (session + analytics) | none |

> **Steps 4, 6, 8 are guardrails:** the agent only invents prose when it has real KB context
> (step 11). With no results it returns a **fixed** message (step 8) — it does not ask the LLM
> to make something up. See [LIMITATIONS.md → Answering behaviour](LIMITATIONS.md).

---

## Audience isolation

This is the security-critical part: **a customer must never see an `internal` KB entry.**

- The filter is applied **inside the vector search** (`src/query/vector_search.py`), not after,
  so internal chunks never even enter the candidate set:
  ```python
  metadata_filter["userType"] = {"$in": [user_type.lower(), "both"]}
  ```
- It is also threaded through **parent-document expansion** (`src/agent/search/parent_retrieval.py`),
  so expanding a chunk to its full parent can't pull in internal content.
- Covered by [`tests/test_isolation.py`](../tests/test_isolation.py), which asserts an `external`
  search never returns an `internal` chunk against live AstraDB.

---

## Escalation (single source of truth)

The decision to escalate is made by **one** component — `EscalationHandler`
([`src/agent/escalation/escalation_handler.py`](../src/agent/escalation/escalation_handler.py)) —
using **pure rules, no LLM**:

- `check_escalation(query_type, results, best_confidence)` returns
  `{should_escalate, escalation_reason, escalation_type, response_strategy}`.
- Escalates when confidence is below `MIN_CONFIDENCE_SCORE` (0.50) or there are no usable results.
- The result rides out in the `metadata` frame as `requires_escalation`. The **frontend** then
  offers "Create a ticket?" — escalation itself does not create a ticket (see
  [CUSTOMER_AGENT_API.md](CUSTOMER_AGENT_API.md)).
- Covered by [`tests/test_escalation.py`](../tests/test_escalation.py).

---

## Search design (why it's shaped this way)

- **Unified collection.** All KB chunks live in one AstraDB collection (`property_engine`),
  filtered by metadata — not split across per-type collections. Simpler, and lets one query
  span types.
- **Chunk → parent expansion.** Search matches small chunks (precise), then expands to the parent
  document when the user needs full steps ("show me all the steps") — precision of chunks,
  completeness of documents.
- **Rerank.** Vector similarity is the recall stage; the reranker re-orders for precision.
- **Same embedding model for query and docs** (`text-embedding-3-small`, 1536-dim) via the shared
  singleton — mismatched models would silently wreck similarity.

---

## Files map (agent side)

| Area | Files |
|---|---|
| Orchestration | `src/agent/orchestrator.py` |
| Classification | `src/agent/classification/query_classifier.py` |
| Query intelligence | `src/agent/query_processing/` (query_intelligence, query_builder) |
| Search & ranking | `src/query/vector_search.py`, `src/query/reranker.py`, `src/agent/search/` |
| Context & response | `src/agent/context/`, `src/agent/response/response_generator.py` |
| Escalation | `src/agent/escalation/escalation_handler.py` |
| Memory | `src/memory/` (session manager, Redis store, rolling summaries) |
| Streaming transport | `src/api/streaming_utils.py` (NDJSON framing) |
