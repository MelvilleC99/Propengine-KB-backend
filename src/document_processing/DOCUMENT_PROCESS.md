# Document Upload Processing

## Directory Structure

```
src/
├── document_processing/          # Document extraction & transformation
│   ├── __init__.py              # Module exports
│   ├── extractors.py            # DOCX & PDF text extraction
│   ├── structure_analyzer.py    # LLM-based content analysis
│   ├── entry_builder.py         # Transforms to KB entry format
│   └── DOCUMENT_PROCESS.md      # This file
│
├── api/
│   └── kb_routes.py             # POST /documents/upload endpoint
│
└── mcp/vector_sync/
    ├── document_chunking.py     # Chunks documents for vectors
    └── server.py                # Orchestrates sync to AstraDB
```

---

## Flow Overview

```
User uploads DOCX/PDF
        ↓
    extractors.py        → Extracts text + structure (headings, tables)
        ↓
 structure_analyzer.py   → LLM analyzes sections, suggests entry type
        ↓
    entry_builder.py     → Builds KB entry (rawFormData, metadata)
        ↓
    Firebase             → Stores entry
        ↓
 document_chunking.py    → Creates searchable chunks (by steps)
        ↓
    AstraDB              → Stores vectors for RAG search
```

---

## File Descriptions

### `extractors.py`
**Purpose:** Extract text and structure from uploaded documents.

- **DocxExtractor:** Reads DOCX files using python-docx
  - Iterates through paragraphs AND tables (important for step-based docs)
  - Detects heading styles (Heading 1, Heading 2, etc.)
  - Filters out Word error text ("No table of contents entries found")
  
- **PdfExtractor:** Reads PDF files using PyMuPDF
  - Extracts text with font size info
  - Detects headings by font size and numbered patterns (1.1., 1.2.)

- **get_extractor(filename):** Factory function returns correct extractor

### `structure_analyzer.py`
**Purpose:** Use LLM (gpt-4o-mini) to analyze document structure.

- Determines if document is structured (multiple sections) or unstructured
- Classifies each section type: overview, prerequisites, steps, troubleshooting, etc.
- Generates summaries and key topics for each section
- Suggests appropriate KB entry type (how_to, definition, error)

### `entry_builder.py`
**Purpose:** Transform analyzed document into KB entry format.

- Builds entries matching the template structure (same as manual entries)
- Creates `rawFormData` with: overview, prerequisites, steps, sections, tips
- Extracts steps from "steps" type sections
- Combines user-provided tags with LLM-extracted topics
- Sets metadata: source="upload", original_filename, word_count, etc.

### `kb_routes.py` (relevant endpoint)
**Purpose:** API endpoint for document upload.

```
POST /api/kb/documents/upload
```

- Accepts multipart form: file, title, entry_type, category, tags, etc.
- Validates file type (DOCX or PDF)
- Orchestrates: extract → analyze → build → save to Firebase → sync to vectors
- Returns: entry_id, sections_extracted, word_count, sync_status

### `document_chunking.py`
**Purpose:** Create searchable vector chunks from document entries.

- **chunk_document():** Standard chunking by sections
- **_chunk_by_steps():** Better chunking for how-to docs with many steps
  - Groups 4 steps per chunk for granular search
  - Creates overview chunk + step chunks
- Adds metadata for search compatibility: title, type, entryType, category
- Includes context: previous/next section references

### `server.py` (VectorSyncMCP)
**Purpose:** Orchestrate sync between Firebase and AstraDB.

- Fetches entry from Firebase
- Detects if document upload (`is_document_entry()`)
- Calls appropriate chunker (document vs template)
- Stores vectors in AstraDB with embeddings
- Updates Firebase sync status

---

## Key Design Decisions

1. **Table extraction:** DOCX files often have steps in tables, not paragraphs
2. **Step-based chunking:** Groups 4 steps per chunk for better RAG results
3. **Metadata compatibility:** Document chunks have same fields as manual entries
4. **Source tracking:** `source="upload"` distinguishes from template entries
