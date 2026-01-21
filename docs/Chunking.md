# Intelligent Chunking System Documentation

## Overview
The chunking system breaks down KB entries into smaller, contextualized pieces (chunks) that can be embedded and searched more precisely. Different entry types use different chunking strategies optimized for their structure.

---

## Why Chunking?

### Problems with Single Large Embeddings
❌ **No chunking**:
```
Entry: "How to Setup CRM" (5000 words)
→ Single embedding
→ Query: "what are prerequisites?" 
→ Returns entire 5000-word document
→ User has to search through it manually
```

✅ **With smart chunking**:
```
Entry: "How to Setup CRM" (5000 words)
→ 5 chunks: overview, prerequisites, steps, issues, tips
→ Query: "what are prerequisites?"
→ Returns ONLY prerequisites chunk (300 words)
→ Perfect precision!
```

### Benefits
- **Precision**: Match specific sections, not entire documents
- **Context**: Each chunk knows about neighboring sections
- **Navigation**: Related chunks linked for easy traversal
- **Better Embeddings**: Focused content = better semantic matching

---

## File Structure

### Core Files

```
/src/mcp/vector_sync/
├── server.py          → Orchestrates sync between Firebase and AstraDB
├── chunking.py        → Smart chunking logic (this doc focuses here)
└── __init__.py
```

**Main Entry Point**: `chunking.py` → `chunk_entry(entry)`

---

## Chunking Strategies by Entry Type

### 1. Definition Entries → Single Chunk
**Type**: `definition`

**Strategy**: Always create single chunk (definitions are short, one concept)

**Structure**:
```python
Entry: {
  type: "definition",
  rawFormData: {
    term: "API Key",
    definition: "A unique identifier used for authentication",
    context: "Used in PropertyEngine integrations",
    examples: ["sk_live_xxx", "pk_test_yyy"]
  }
}

↓ Chunking ↓

Chunk 0 (Full):
  Content: "Term: API Key
            Definition: A unique identifier...
            Context: Used in PropertyEngine...
            Examples: sk_live_xxx, pk_test_yyy"
  
  Metadata: {
    entryType: "definition",
    section_type: "full",
    chunk_index: 0,
    total_chunks: 1
  }
```

**Function**: `chunk_definition()` in `chunking.py:108`

---

### 2. Error Entries → Single Chunk
**Type**: `error`

**Strategy**: Single chunk (errors are usually short problem + solution)

**Structure**:
```python
Entry: {
  type: "error",
  title: "Error 401: Unauthorized",
  rawFormData: {
    errorCode: "401",
    description: "Authentication failed",
    symptoms: "API calls return 401 status",
    solution: "Check API key validity",
    causes: ["Expired key", "Wrong environment"],
    prevention: "Rotate keys quarterly"
  }
}

↓ Chunking ↓

Chunk 0 (Full):
  Content: "Error: Error 401: Unauthorized
            Error Code: 401
            Description: Authentication failed
            Symptoms: API calls return 401 status
            Solution: Check API key validity
            Common Causes: Expired key, Wrong environment
            Prevention: Rotate keys quarterly"
  
  Metadata: {
    entryType: "error",
    section_type: "full",
    chunk_index: 0,
    total_chunks: 1
  }
```

**Function**: `chunk_error()` in `chunking.py:159`

---

### 3. How-To Entries → Multi-Chunk with Context ⭐
**Type**: `how_to` or `workflow`

**Strategy**: Context-aware chunks by heading sections

**Sections Created**:
1. **Overview** - High-level explanation
2. **Prerequisites** - What's needed before starting
3. **Steps** - Step-by-step instructions
4. **Common Issues** - Troubleshooting
5. **Tips** - Best practices

**Structure**:
```python
Entry: {
  type: "how_to",
  title: "How to Setup CRM Integration",
  rawFormData: {
    overview: "This guide explains how to integrate...",
    prerequisites: "You need admin access and API key",
    steps: [
      "Step 1: Login to admin panel",
      "Step 2: Navigate to integrations",
      "Step 3: Enter API credentials"
    ],
    commonIssues: "Error 401 means invalid API key...",
    tips: "Always test in sandbox environment first"
  }
}

↓ Chunking ↓

Chunk 0 (Overview):
  Content: "Overview for How to Setup CRM Integration:
            This guide explains how to integrate..."
  
  Metadata: {
    entryType: "how_to",
    section: "overview",
    chunk_index: 0,
    total_chunks: 5,
    parent_entry_id: "abc123",
    parent_title: "How to Setup CRM Integration"
  }
  
  Context: {
    position: "1 of 5",
    section_name: "overview",
    next_section: "prerequisites",
    next_summary: "You need admin access...",
    related_chunks: ["abc123_chunk_1", "abc123_chunk_2", ...]
  }

Chunk 1 (Prerequisites):
  Content: "Prerequisites for How to Setup CRM Integration:
            You need admin access and API key"
  
  Metadata: {
    entryType: "how_to",
    section: "prerequisites",
    chunk_index: 1,
    total_chunks: 5
  }
  
  Context: {
    position: "2 of 5",
    section_name: "prerequisites",
    previous_section: "overview",
    previous_summary: "This guide explains how to integrate...",
    next_section: "steps",
    next_summary: "Step-by-step instructions...",
    related_chunks: ["abc123_chunk_0", "abc123_chunk_2", ...]
  }

Chunk 2 (Steps):
  Content: "Steps for How to Setup CRM Integration:
            1. Login to admin panel
            2. Navigate to integrations
            3. Enter API credentials"
  
  Metadata: {
    entryType: "how_to",
    section: "steps",
    chunk_index: 2,
    total_chunks: 5
  }
  
  Context: {
    position: "3 of 5",
    section_name: "steps",
    previous_section: "prerequisites",
    next_section: "issues",
    related_chunks: [...]
  }

... (chunks 3 and 4 for issues and tips)
```

**Function**: `chunk_how_to()` in `chunking.py:218`

---

## Context System Explained

### What is Context?
Each chunk includes metadata about its neighboring sections to help the LLM understand:
- Where in the document this chunk appears
- What came before
- What comes next
- How to navigate to related information

### Context Fields

```python
context = {
    "position": "2 of 5",                    # Position in document
    "section_name": "prerequisites",          # Current section
    "previous_section": "overview",           # What came before
    "previous_summary": "This guide...",      # Brief summary
    "next_section": "steps",                  # What comes next
    "next_summary": "Step-by-step...",        # Brief summary
    "related_chunks": [                       # All other chunks
        "abc123_chunk_0",
        "abc123_chunk_2",
        "abc123_chunk_3",
        "abc123_chunk_4"
    ]
}
```

### Why Context Matters

**Without Context**:
```
User: "What are the prerequisites?"
Agent: [Returns prerequisites chunk]
User: "How do I do step 1?"
Agent: [NEW SEARCH - may not find correct chunk]
```

**With Context**:
```
User: "What are the prerequisites?"
Agent: [Returns prerequisites chunk]
       Context shows: "next_section: steps"
User: "How do I do step 1?"
Agent: [Can reference related_chunks to find steps]
       OR: "I can see steps come next, let me check that section"
```

---

## Metadata in Chunks

### Standard Metadata (All Chunks)
```python
metadata = {
    "entryType": "how_to",           # Entry type (MUST be "entryType")
    "userType": "internal",           # internal|external
    "category": "integrations",       # Category
    "product": "property_engine",     # Product
    "tags": ["crm", "setup"],         # Tags array
    "parent_entry_id": "abc123",      # Original entry ID
    "parent_title": "How to Setup CRM" # Original title
}
```

### Additional Metadata for Multi-Chunk Entries
```python
metadata = {
    ...standard fields...,
    "section": "prerequisites",       # Section name
    "chunk_index": 1,                 # Position (0-based)
    "total_chunks": 5,                # Total number of chunks
    "subcategory": "api_integrations" # Optional subcategory
}
```

### Flattened Context Metadata (AstraDB Limitation)
AstraDB doesn't support nested objects, so context is flattened:

```python
# Instead of:
metadata = {
    "context": {
        "position": "2 of 5",
        "next_section": "steps"
    }
}

# We store:
metadata = {
    "context_position": "2 of 5",
    "context_next_section": "steps",
    "context_next_summary": "...",
    "context_previous_section": "overview",
    "context_related_chunks": ["chunk_0", "chunk_2"]
}
```

---

## Chunk ID Naming Convention

### Pattern
```
{parent_entry_id}_chunk_{chunk_index}
```

### Examples
```
Original Entry ID: "abc123xyz"

Chunks Created:
- abc123xyz_chunk_0  → Overview
- abc123xyz_chunk_1  → Prerequisites
- abc123xyz_chunk_2  → Steps
- abc123xyz_chunk_3  → Common Issues
- abc123xyz_chunk_4  → Tips
```

### Why This Matters
- **Deletion**: When deleting "abc123xyz", we delete ALL chunks
- **Navigation**: Related chunks easily identified
- **Debugging**: Clear parent-child relationship

---

## Helper Functions

### 1. `_to_string(value)` 
**Purpose**: Convert any value (list, dict, str, None) to string for content building

**Examples**:
```python
_to_string("simple text")
→ "simple text"

_to_string(["item1", "item2", "item3"])
→ "item1\nitem2\nitem3"

_to_string([{"action": "Step 1"}, {"action": "Step 2"}])
→ "1. Step 1\n2. Step 2"

_to_string({"key1": "value1", "key2": "value2"})
→ "key1: value1\nkey2: value2"

_to_string(None)
→ ""
```

**Location**: `chunking.py:17`

---

### 2. `_summarize(text, max_length=100)`
**Purpose**: Create brief summaries for context

**Logic**:
1. If text ≤ 100 chars → return as-is
2. Find last sentence boundary before 100 chars
3. Return truncated text with "..." if needed

**Example**:
```python
_summarize("This is a long paragraph about CRM integration. It has multiple sentences.")
→ "This is a long paragraph about CRM integration."
```

**Location**: `chunking.py:401`

---

## Chunk Class

### Definition
```python
class Chunk:
    def __init__(
        self,
        content: str,              # Main content text
        chunk_index: int,          # Position (0-based)
        total_chunks: int,         # Total count
        section_type: str,         # Section name
        parent_id: str,            # Original entry ID
        parent_title: str,         # Original title
        metadata: Dict[str, Any],  # Metadata dict
        context: Dict[str, Any]    # Context dict (optional)
    )
```

**Location**: `chunking.py:54`

---

## Complete Flow Diagram

```
1. Entry Created in Firebase
   └─ vectorStatus: "pending"
   
2. User Calls: POST /api/kb/entries/{id}/sync
   
3. Vector Sync MCP (server.py)
   ├─ Fetches entry from Firebase
   └─ Calls: chunk_entry(entry)
   
4. Chunking Logic (chunking.py)
   ├─ Check entry type
   │
   ├─ IF "definition" → chunk_definition()
   │   └─ Returns: [single chunk]
   │
   ├─ IF "error" → chunk_error()
   │   └─ Returns: [single chunk]
   │
   ├─ IF "how_to" or "workflow" → chunk_how_to()
   │   ├─ Parse sections (overview, prerequisites, steps, issues, tips)
   │   ├─ Build context for each chunk
   │   │   ├─ Add previous/next section info
   │   │   ├─ Add summaries
   │   │   └─ Add related chunk IDs
   │   └─ Returns: [5 chunks with context]
   │
   └─ ELSE → chunk_single()
       └─ Returns: [fallback single chunk]
   
5. Vector Sync MCP
   ├─ For each chunk:
   │   ├─ Generate chunk_id: parent_id_chunk_N
   │   ├─ Prepare metadata (flatten context)
   │   └─ Call: astradb.store_vector(chunk_id, content, metadata)
   │
   └─ Update Firebase:
       ├─ vectorStatus: "synced"
       ├─ lastSyncedAt: timestamp
       └─ chunksCreated: count
   
6. Chunks Stored in AstraDB
   ├─ Each chunk has unique ID
   ├─ Each chunk has vector embedding
   └─ Each chunk has full metadata + context
```

---

## Search Flow with Chunks

### Query: "What are the prerequisites for CRM setup?"

```
1. Vector Search
   ├─ Embeds query: "prerequisites CRM setup"
   ├─ Searches AstraDB with metadata filter
   └─ Finds: abc123xyz_chunk_1 (prerequisites section)
       Score: 0.92 similarity
   
2. Returns Chunk:
   Content: "Prerequisites for How to Setup CRM Integration:
             You need admin access and API key..."
   
   Metadata: {
     section: "prerequisites",
     parent_title: "How to Setup CRM Integration"
   }
   
   Context: {
     next_section: "steps",
     next_summary: "Step-by-step instructions...",
     related_chunks: ["abc123xyz_chunk_0", "abc123xyz_chunk_2"]
   }
   
3. Agent Response:
   "To setup CRM integration, you need:
    - Admin access to PropertyEngine
    - Valid API key
    
    [Context aware: Can offer to show steps next]"
```

---

## Testing Chunking

### Test Script
```python
# Test chunking logic
from src.mcp.vector_sync.chunking import chunk_entry

# Test entry
entry = {
    "id": "test123",
    "type": "how_to",
    "title": "Test Entry",
    "rawFormData": {
        "overview": "Test overview",
        "prerequisites": "Test prerequisites",
        "steps": ["Step 1", "Step 2"],
        "commonIssues": "Test issues",
        "tips": "Test tips"
    }
}

# Chunk it
chunks = chunk_entry(entry)

# Verify
print(f"Created {len(chunks)} chunks")
for chunk in chunks:
    print(f"Chunk {chunk.chunk_index}: {chunk.section_type}")
    print(f"  Content: {chunk.content[:50]}...")
    print(f"  Context: {chunk.context}")
```

---

## Configuration

### Chunking Settings
All settings are in the chunking logic itself (no external config):

- **Max summary length**: 100 characters
- **Section order**: overview → prerequisites → steps → issues → tips
- **Fallback strategy**: Single chunk if no sections found

### Future Enhancements
- Configurable max chunk size
- Custom section definitions per product
- Adaptive chunking based on content length

---

## Common Issues & Solutions

### Issue: Chunks Not Created
**Symptoms**: Entry synced but no chunks in AstraDB

**Causes**:
1. Empty `rawFormData` fields
2. Entry type not recognized
3. Chunking function error

**Solution**: Check logs, verify entry structure

---

### Issue: Too Many Chunks
**Symptoms**: 10+ chunks for single entry

**Causes**: Usually doesn't happen with current logic

**Solution**: Review entry structure, check for malformed data

---

### Issue: Search Not Finding Chunks
**Symptoms**: Query returns no results but chunks exist

**Causes**:
1. Metadata field mismatch (`type` vs `entryType`)
2. Wrong `userType` filter
3. Content doesn't match query semantically

**Solution**: 
- Verify metadata consistency (see `METADATA_FIX.md`)
- Check filters in search query
- Test with direct chunk queries

---

## Files Reference

### Core Files
```
/src/mcp/vector_sync/
├── chunking.py        → Chunking logic (THIS DOC)
├── server.py          → Sync orchestration
└── __init__.py

/src/mcp/astradb/
└── server.py          → Vector storage

/src/mcp/firebase/
└── server.py          → Entry management

/src/query/
└── vector_search.py   → Search with metadata filters
```

### Related Documentation
- `DB_Endpoints.md` - API endpoints reference
- `METADATA_FIX.md` - Metadata field standardization
- `/src/agent/README.md` - Agent usage of chunks

---

## Key Takeaways

✅ **Smart chunking improves search precision**
- Definitions/Errors: Single chunk (simple)
- How-To/Workflow: Multi-chunk with context (advanced)

✅ **Context enables intelligent navigation**
- Each chunk knows about neighbors
- Agent can suggest related sections
- Better conversation flow

✅ **Metadata consistency is critical**
- Use `entryType` not `type`
- Flatten nested objects for AstraDB
- Include parent info for traceability

✅ **Chunk IDs follow pattern**
- `{parent_id}_chunk_{index}`
- Easy deletion of all chunks
- Clear parent-child relationship

---

**Last Updated**: January 21, 2026
