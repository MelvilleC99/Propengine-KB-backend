# KB Ingestion — Creating & Embedding Knowledge

> **Part 1 of 2.** This covers the **KB management product**: how a knowledge-base entry is
> created, processed, chunked, embedded, and written to the vector DB.
> For the **agent product** (how those entries get searched and answered), see
> [AGENT_PIPELINE.md](AGENT_PIPELINE.md).

---

## The flow (what calls what)

**Manual entry:**
```
Frontend POST /api/kb/entries
  → api/kb/entries.py (create_entry)        → Firebase (kb_entries, vectorStatus="pending")
Frontend POST /api/kb/entries/{id}/sync
  → api/kb/vectors.py (sync endpoint)
    → services/vector_sync/server.py (sync_entry_to_vector)
       → chunk it          (chunking.py)
       → build metadata     (_prepare_chunk_metadata)   ← validation/normalization lives here
       → embed + store      (astradb/server.py store_vector → AstraDB)
       → update Firebase     (vectorStatus="synced" | "partial")
```

**Document upload:**
```
Frontend POST /api/kb/documents/upload
  → api/kb/documents.py
    → document_processing/extractors.py        (extract text from DOCX/PDF)
    → document_processing/structure_analyzer.py (LLM splits into sections)
    → document_processing/entry_builder.py      (build KB entry)
    → Firebase create  →  then sync (same sync path as above, using document_chunking.py)
```

**Duplicate check (frontend pre-check, advisory only):**
```
Frontend POST /api/kb/check-duplicates → api/kb/duplicates.py → vector similarity search
```

> **Why create and sync are two steps:** creating an entry writes it to Firebase immediately
> (`vectorStatus="pending"`) so it's editable. Embedding only happens on **sync**. This means
> an edited entry is **stale in search until re-synced** — see [Vector drift](LIMITATIONS.md#vector-drift).

---

## Files — by stage

### 1. API layer (entry points)
| File | Role |
|---|---|
| `src/api/kb_routes.py` | Aggregates the KB sub-routers |
| `src/api/kb/entries.py` | Create / update / get / list / delete / archive KB entries (Firebase CRUD) |
| `src/api/kb/documents.py` | Upload DOCX/PDF → extract → build entry → sync |
| `src/api/kb/vectors.py` | **Sync** entry to vector DB (`/sync`), list vectors, delete vectors |
| `src/api/kb/duplicates.py` | Semantic duplicate check (threshold 0.70, dedup by parent) |
| `src/api/kb/models.py` | Pydantic request/response models (CreateEntryRequest, etc.) |

### 2. Document processing (uploads only)
| File | Role |
|---|---|
| `src/document_processing/extractors.py` | Extract text + structure from DOCX (python-docx) and PDF (PyMuPDF/pdfplumber/pypdf) |
| `src/document_processing/structure_analyzer.py` | LLM (gpt-4o-mini) organizes extracted text into sections |
| `src/document_processing/entry_builder.py` | Convert extracted structure → KB entry format |

### 3. Chunking, embedding & sync (the core)
| File | Role |
|---|---|
| `src/services/vector_sync/server.py` | **Orchestrates sync.** Fetch entry → chunk → embed → write to AstraDB → update Firebase status. Contains `_prepare_chunk_metadata` — the single choke-point where metadata is **validated & normalized** (lowercase userType/entryType, category fallback, allowed-value checks). |
| `src/services/vector_sync/chunking.py` | Chunking for **template** entries (definition/error/how_to/workflow) + size-based splitting + `_tail_overlap` (chunk overlap). |
| `src/services/vector_sync/document_chunking.py` | Chunking for **uploaded documents** (section-based + large-section splitting with overlap). |

### 4. Storage clients (shared with the read side)
| File | Role |
|---|---|
| `src/database/astra_client.py` | AstraDB connection + **OpenAI embeddings singleton** (`text-embedding-3-small`, 1536-dim). Same instance used by search — keeps query/doc embeddings consistent. |
| `src/services/astradb/server.py` | AstraDB operations: `store_vector`, `delete_vector` (by parent + chunks), search, list, stats |
| `src/services/firebase/server.py` | Firebase KB entry CRUD (the `kb_entries` collection) |
| `src/database/firebase_client.py` | Firestore client init |

---

## What gets written per chunk (the metadata contract)

Every chunk stored in AstraDB carries its **own embedding vector** plus a copy of the parent's
metadata, so each chunk is independently filterable:

```
_id:        "{entry_id}_chunk_{N}"
vector:     [1536-dim embedding of THIS chunk's text]
metadata:
  entryType, userType, category, product, tags, title, related_documents   # from parent (lowercased)
  parent_entry_id, parent_title, chunk_index, total_chunks, section_type    # chunk identity
  context_position ("1 of 4"), context_section_name, prev/next summaries    # context
```

**Filtering contract:** the search side filters on `entryType` (e.g. `how_to`) and `userType`.
These are normalized to **lowercase on write**, so filtering can't silently break on casing.

### Audience tagging (`userType`) — drives the whole isolation model
| `userType` | Visible to |
|---|---|
| `external` | customers only |
| `internal` | support staff only |
| `both` | everyone (customers **and** staff) |

The search side enforces this with a `$in` filter (e.g. a customer query matches
`userType ∈ {external, both}`). See [AGENT_PIPELINE.md → Audience isolation](AGENT_PIPELINE.md#audience-isolation).

---

## Current state
- ✅ Embedding consistency (same model for query + docs) — verified correct
- ✅ Metadata keys match search filters — verified
- ✅ Schema validation + normalization (userType/entryType/category) — in `_prepare_chunk_metadata`
- ✅ Chunk overlap on size-based splits
- ✅ Partial sync marked `"partial"` (not silently `"synced"`)
- ⬜ Update does **not** auto-reset `vectorStatus` (by design: edit in Firebase, then manually re-sync)
- ⬜ `/restore` endpoint not implemented (frontend stub calls it) — see [LIMITATIONS.md](LIMITATIONS.md)
