# KB Creation & Embedding — File Map

> **Last updated:** 2026-06-02
> **Scope:** Only the files that handle **creating a KB entry, processing it, chunking,
> embedding, and writing it to the vector DB.** (For the query/agent side, see ARCHITECTURE.md.)

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

---

## Files — by stage

### 1. API layer (entry points)
| File | Role |
|---|---|
| `src/api/kb_routes.py` | Aggregates the KB sub-routers |
| `src/api/kb/entries.py` | Create / update / get / list / delete / archive KB entries (Firebase CRUD). *No `/restore` route exists.* |
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
| `src/services/vector_sync/server.py` | **Orchestrates sync.** Fetches entry → chunks → embeds → writes to AstraDB → updates Firebase status. Contains `_prepare_chunk_metadata` — the single choke-point where metadata is **validated & normalized** (lowercase userType/entryType, category fallback, allowed-value checks). |
| `src/services/vector_sync/chunking.py` | Chunking strategies for **template** entries (definition/error/how_to/workflow), size-based splitting, and the `_tail_overlap` helper (chunk overlap). |
| `src/services/vector_sync/document_chunking.py` | Chunking strategies for **uploaded documents** (section-based + large-section splitting with overlap). |

### 4. Storage clients (shared with the read side)
| File | Role |
|---|---|
| `src/database/astra_client.py` | AstraDB connection + **OpenAI embeddings singleton** (`text-embedding-3-small`, 1536-dim). Same instance used by search — keeps query/doc embeddings consistent. |
| `src/services/astradb/server.py` | AstraDB operations: `store_vector`, `delete_vector` (by parent + chunks), search, list, stats |
| `src/services/firebase/server.py` | Firebase KB entry CRUD (the `kb_entries` collection) |
| `src/database/firebase_client.py` | Firestore client init |

### 5. Config (shared)
| File | Role |
|---|---|
| `src/config/settings.py` | `EMBEDDING_MODEL`, `PROPERTY_ENGINE_COLLECTION`, thresholds, service creds |

---

## What gets written per chunk (the metadata contract)

Every chunk stored in AstraDB carries its **own embedding vector** plus a copy of the parent's metadata, so each chunk is independently filterable:

```
_id:        "{entry_id}_chunk_{N}"
vector:     [1536-dim embedding of THIS chunk's text]
metadata:
  entryType, userType, category, product, tags, title, related_documents   # from parent (normalized lowercase)
  parent_entry_id, parent_title, chunk_index, total_chunks, section_type    # chunk identity
  context_position ("1 of 4"), context_section_name, prev/next summaries    # context
```

**Filtering contract:** the search side filters on `entryType` (e.g. `how_to`) and `userType` (`internal`/`external`). These are normalized to lowercase on write, so filtering can't silently break on casing.

---

## Current state (as of last updated)
- ✅ Embedding consistency (same model for query + docs) — verified correct
- ✅ Metadata keys match search filters — verified
- ✅ Schema validation + normalization (userType/entryType/category) — added
- ✅ Chunk overlap on size-based splits — added
- ✅ Partial sync marked `"partial"` (not silently `"synced"`) — added
- ⬜ Update doesn't auto-reset `vectorStatus` (by design: update Firebase, then manually re-sync)
- ⬜ `/restore` endpoint not implemented (frontend stub calls it)
