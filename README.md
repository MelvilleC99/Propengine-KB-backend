# PropertyEngine Knowledge Base & Support Agent — Backend

A FastAPI backend that powers **two products** from one knowledge base:

1. **KB Management** — create, chunk, embed, and sync knowledge-base articles to a vector store.
2. **Support Agent** — a RAG agent that answers questions over that knowledge, served to three
   audiences (customer / support staff / internal test) from a single pipeline.

Built on FastAPI + LangChain, OpenAI embeddings & `gpt-4o-mini` (via a company proxy), AstraDB
(vector store), Firebase/Firestore (durable data), and Redis (live session memory).

---

## Architecture at a glance

```
                 ┌───────────────────────── KB Management ─────────────────────────┐
  Create entry → │  Firebase (kb_entries)  →  chunk  →  embed  →  AstraDB (vectors) │
   / upload doc  └──────────────────────────────────────────────────────────────────┘
                                                  │
                 ┌───────────────────────── Support Agent ──────────────────────────┐
  User query  →  │  classify → search (audience-filtered) → rerank → stream answer   │ → NDJSON
                 │            ↑ Redis context        ↑ escalation decision            │   stream
                 └──────────────────────────────────────────────────────────────────┘
```

- **Audience isolation:** the same agent serves customers and staff; a `user_type_filter` decides
  which KB entries the search can see, so a customer never sees an internal article. See
  [docs/AGENT_PIPELINE.md](docs/AGENT_PIPELINE.md#audience-isolation).

---

## Directory structure

```
.
├── main.py                  # FastAPI app entry point
├── Dockerfile               # Cloud Run container (Python 3.11)
├── deploy_with_secrets.sh   # Deploy to Cloud Run (pulls secrets from Secret Manager)
├── requirements.txt
├── docs/                    # ← see Documentation below
├── tests/                   # pytest suite (escalation + audience isolation)
└── src/
    ├── api/                 # FastAPI routers
    │   └── kb/              #   KB management endpoints (entries, documents, vectors, duplicates)
    ├── agent/               # The support agent
    │   ├── classification/  #   query type classifier
    │   ├── query_processing/#   query intelligence + enhancement
    │   ├── search/          #   search strategy + parent-document retrieval
    │   ├── response/        #   answer generation (streaming + non-streaming)
    │   ├── escalation/      #   escalation decision (pure rules)
    │   ├── context/         #   context building + answer-from-history
    │   └── orchestrator.py  #   coordinates the whole query pipeline
    ├── query/               # vector_search + reranker (the read side)
    ├── services/            # vector_sync (chunk/embed/sync), astradb, firebase
    ├── document_processing/ # DOCX/PDF extraction → structure → KB entry
    ├── database/            # Firestore + AstraDB clients and per-collection services
    ├── memory/              # Redis session memory + rolling summaries + KB usage analytics
    ├── analytics/           # query metrics + token/cost tracking
    ├── config/              # settings, rate limits
    └── prompts/             # YAML prompt templates
```

---

## Quick start (local)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env        # then fill in the values (see .env.example)
                            # tip: set REQUIRE_AUTH=false for local testing without a frontend token
python main.py              # serves on http://127.0.0.1:8000

# health check
curl http://127.0.0.1:8000/api/health/
# interactive API docs
open http://127.0.0.1:8000/docs
```

Required env (see [.env.example](.env.example)): OpenAI proxy key + base URL, AstraDB token +
endpoint, Firebase credentials. Redis and Freshdesk are optional (graceful fallback).

---

## Deployment

Deploys to **Google Cloud Run**; secrets come from **Secret Manager** (never committed):

```bash
./deploy_with_secrets.sh
```

This builds the Dockerfile, deploys the container, and wires secrets via `--set-secrets`.
> **Auth:** the Cloud Run service stays `--allow-unauthenticated` by design (a browser can't present
> a Google IAM token); auth is enforced **in-app** via Firebase ID tokens, controlled by
> `REQUIRE_AUTH` (default **on**). The frontend must send the token before deploying with it on —
> see [docs/FRONTEND_AUTH.md](docs/FRONTEND_AUTH.md) and [docs/LIMITATIONS.md](docs/LIMITATIONS.md).

---

## Testing

```bash
pytest tests/ -v
```

- `tests/test_isolation.py` — proves a customer (`external`) search never returns an `internal`
  chunk (runs against live AstraDB).
- `tests/test_escalation.py` — escalation decision logic.

(One-off diagnostic/latency scripts live in `test_scripts/`, which is **not** committed.)

---

## Documentation

| Doc | What it covers |
|---|---|
| [docs/KB_INGESTION.md](docs/KB_INGESTION.md) | **Part 1** — creating, chunking, embedding & syncing KB entries |
| [docs/AGENT_PIPELINE.md](docs/AGENT_PIPELINE.md) | **Part 2** — how a query is classified, searched, isolated & answered |
| [docs/CUSTOMER_AGENT_API.md](docs/CUSTOMER_AGENT_API.md) | Frontend API reference for the customer chat (streaming) |
| [docs/FRONTEND_AUTH.md](docs/FRONTEND_AUTH.md) | How the frontend attaches the Firebase token to backend calls |
| [docs/FIREBASE_COLLECTIONS.md](docs/FIREBASE_COLLECTIONS.md) | Which Firestore collections we write, and what triggers each |
| [docs/PRODUCT_SPEC.md](docs/PRODUCT_SPEC.md) | Product spec / intent |
| [docs/LIMITATIONS.md](docs/LIMITATIONS.md) | Known gaps & roadmap (read me before judging 🙂) |
