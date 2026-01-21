# Database Endpoints Documentation

## Overview
This document provides a comprehensive reference for all KB (Knowledge Base) database endpoints, including backend API routes, frontend API routes, and their usage.

---

## Backend API Endpoints

**Base URL**: `http://localhost:8000` (development)

All endpoints are defined in: `/src/api/kb_routes.py`

### 1. Create KB Entry
**Endpoint**: `POST /api/kb/entries`

**Purpose**: Create a new knowledge base entry in Firebase

**Request Body**:
```json
{
  "type": "how_to",
  "title": "How to Setup CRM Integration",
  "content": "Complete searchable text content",
  "metadata": {
    "category": "integrations",
    "userType": "internal",
    "product": "property_engine",
    "tags": ["crm", "setup", "integration"]
  },
  "rawFormData": {
    "overview": "This guide explains...",
    "prerequisites": "You need admin access...",
    "steps": ["Step 1: Login", "Step 2: Configure"],
    "commonIssues": "Error 401 means...",
    "tips": "Always test in sandbox first..."
  },
  "author": "john@propengine.com"
}
```

**Response**:
```json
{
  "success": true,
  "entry_id": "abc123xyz",
  "entry": {
    "id": "abc123xyz",
    "title": "How to Setup CRM Integration",
    "vectorStatus": "pending",
    "createdAt": "2026-01-21T10:30:00Z"
  },
  "message": "Entry created successfully"
}
```

**Notes**:
- Entry created with `vectorStatus: "pending"`
- Must call `/sync` endpoint to embed into vector database
- `content` field is a **string** (searchable text), not nested object
- `rawFormData` contains structured form data

---

### 2. Get Single Entry
**Endpoint**: `GET /api/kb/entries/{entry_id}`

**Purpose**: Retrieve a specific KB entry by ID

**Response**:
```json
{
  "success": true,
  "entry_id": "abc123xyz",
  "entry": {
    "id": "abc123xyz",
    "type": "how_to",
    "title": "How to Setup CRM Integration",
    "content": "...",
    "metadata": {...},
    "rawFormData": {...},
    "vectorStatus": "synced",
    "lastSyncedAt": "2026-01-21T10:35:00Z",
    "chunksCreated": 5
  }
}
```

---

### 3. List Entries
**Endpoint**: `GET /api/kb/entries`

**Purpose**: List all KB entries with optional filters

**Query Parameters**:
- `entry_type` (optional): Filter by type (`how_to`, `error`, `definition`, `workflow`)
- `category` (optional): Filter by category
- `archived` (optional): Include archived entries (default: `false`)
- `limit` (optional): Maximum entries to return

**Example**:
```
GET /api/kb/entries?entry_type=how_to&category=integrations&limit=50
```

**Response**:
```json
{
  "success": true,
  "entries": [
    {
      "id": "abc123",
      "title": "...",
      "type": "how_to",
      "category": "integrations",
      "vectorStatus": "synced"
    }
  ],
  "count": 15
}
```

---

### 4. Update Entry
**Endpoint**: `PUT /api/kb/entries/{entry_id}`

**Purpose**: Update an existing KB entry

**Request Body** (all fields optional):
```json
{
  "title": "Updated Title",
  "content": "Updated content",
  "metadata": {
    "category": "new_category"
  },
  "rawFormData": {
    "overview": "Updated overview..."
  }
}
```

**Response**:
```json
{
  "success": true,
  "entry_id": "abc123xyz",
  "message": "Entry updated successfully"
}
```

**Important**: After updating, call `/sync` to update vectors!

---

### 5. Delete Entry (Hard Delete)
**Endpoint**: `DELETE /api/kb/entries/{entry_id}`

**Purpose**: Permanently delete entry from Firebase AND vector database

**Response**:
```json
{
  "success": true,
  "entry_id": "abc123xyz",
  "message": "Entry deleted successfully"
}
```

**What Happens**:
1. Deletes all vector chunks from AstraDB
2. Deletes entry from Firebase
3. **Cannot be undone**

---

### 6. Archive Entry (Soft Delete)
**Endpoint**: `POST /api/kb/entries/{entry_id}/archive`

**Purpose**: Archive entry (soft delete) - keeps in Firebase but removes from search

**Response**:
```json
{
  "success": true,
  "entry_id": "abc123xyz",
  "message": "Entry archived successfully"
}
```

**What Happens**:
1. Marks entry as `archived: true` in Firebase
2. Removes vectors from AstraDB (not searchable)
3. Entry preserved in Firebase, can be restored later

---

### 7. Sync Entry to Vectors ⭐
**Endpoint**: `POST /api/kb/entries/{entry_id}/sync`

**Purpose**: Embed entry into vector database with intelligent chunking

**Response**:
```json
{
  "success": true,
  "message": "Entry synced successfully (5 chunks)",
  "entry_id": "abc123xyz",
  "chunks_created": 5
}
```

**What Happens**:
1. Fetches entry from Firebase
2. Chunks content intelligently based on entry type
3. Generates embeddings for each chunk
4. Stores chunks as separate vectors in AstraDB
5. Updates Firebase with `vectorStatus: "synced"`

**See**: `Chunking.md` for detailed chunking logic

---

### 8. List Vector Entries
**Endpoint**: `GET /api/kb/vectors`

**Purpose**: View all entries in vector database (admin/debug)

**Query Parameters**:
- `limit` (optional): Max entries to return (default: 50)

**Response**:
```json
{
  "success": true,
  "entries": [
    {
      "entry_id": "abc123_chunk_0",
      "title": "How to Setup CRM Integration",
      "content_preview": "Overview for How to Setup CRM...",
      "metadata": {
        "entryType": "how_to",
        "userType": "internal",
        "section": "overview",
        "chunk_index": 0,
        "total_chunks": 5
      }
    }
  ],
  "count": 25
}
```

---

### 9. Delete Vector Entry
**Endpoint**: `DELETE /api/kb/vectors/{entry_id}`

**Purpose**: Remove vector(s) from AstraDB and reset Firebase status

**Response**:
```json
{
  "success": true,
  "entry_id": "abc123xyz",
  "chunks_deleted": 5,
  "message": "Deleted 5 vector(s) and updated Firebase status to pending"
}
```

**What Happens**:
1. Deletes ALL chunks for entry (handles `entry_id_chunk_0`, `entry_id_chunk_1`, etc.)
2. Updates Firebase: `vectorStatus: "pending"`
3. Entry can be re-synced later

---

### 10. Get Vector Statistics
**Endpoint**: `GET /api/kb/stats/vectors`

**Purpose**: Get vector database statistics

**Response**:
```json
{
  "success": true,
  "total_vectors": 150,
  "collection": "kb_entries"
}
```

---

## Frontend API Routes

**Location**: `/app/api/`

### Current Frontend Endpoints

#### 1. Support Agent (Placeholder)
**File**: `/app/api/support-agent/route.ts`

**Status**: ⚠️ Placeholder - needs backend integration

**Purpose**: Will forward chat requests to backend `/api/chat`

**Current Behavior**: Returns mock response

---

## MCP (Model Context Protocol) Servers

### Firebase MCP
**File**: `/src/mcp/firebase/server.py`

**Purpose**: Manages all Firebase operations

**Methods**:
- `create_entry(entry_data)` - Create entry
- `get_entry(entry_id)` - Get single entry
- `list_entries(filters, limit)` - List with filters
- `update_entry(entry_id, update_data)` - Update entry
- `delete_entry(entry_id)` - Delete entry
- `archive_entry(entry_id)` - Archive entry

---

### AstraDB MCP
**File**: `/src/mcp/astradb/server.py`

**Purpose**: Manages vector database operations

**Methods**:
- `store_vector(entry_id, content, metadata)` - Store vector
- `list_vectors(limit)` - List all vectors
- `delete_vector(entry_id)` - Delete vector(s)
- `get_vector_stats()` - Get statistics

---

### Vector Sync MCP (Orchestrator)
**File**: `/src/mcp/vector_sync/server.py`

**Purpose**: Orchestrates sync between Firebase and AstraDB

**Methods**:
- `sync_entry_to_vector(entry_id)` - Main sync operation
- `resync_entry(entry_id)` - Delete old and create new
- `unsync_entry(entry_id)` - Remove from vectors only

**Process Flow**:
```
1. Fetch entry from Firebase
2. Chunk content (smart chunking by type)
3. Generate embeddings per chunk
4. Store each chunk as separate vector
5. Update Firebase sync status
```

---

## Complete Workflow Example

### Creating and Syncing an Entry

```bash
# Step 1: Create entry
POST /api/kb/entries
{
  "type": "how_to",
  "title": "How to Export Reports",
  "content": "Complete guide to exporting reports from PropertyEngine",
  "metadata": {
    "category": "reporting",
    "userType": "internal"
  },
  "rawFormData": {
    "overview": "This guide shows you how to export...",
    "steps": ["Go to Reports", "Click Export", "Choose format"]
  }
}

# Response: { "entry_id": "xyz789" }

# Step 2: Sync to vectors
POST /api/kb/entries/xyz789/sync

# Response: { "success": true, "chunks_created": 3 }

# Step 3: Verify in vector DB
GET /api/kb/vectors?limit=5

# Should see:
# - xyz789_chunk_0 (overview)
# - xyz789_chunk_1 (steps)
# - xyz789_chunk_2 (tips)
```

---

## Database Schema

### Firebase Structure
```
kb_entries/
  {entry_id}/
    id: "abc123"
    type: "how_to"
    title: "..."
    content: "searchable text"
    metadata: {
      category: "..."
      userType: "internal|external"
      product: "property_engine"
      tags: [...]
    }
    rawFormData: {...}
    vectorStatus: "pending|synced|failed"
    lastSyncedAt: timestamp
    chunksCreated: 5
    archived: false
    createdAt: timestamp
    updatedAt: timestamp
```

### AstraDB Vector Structure
```
kb_entries (collection)
  {chunk_id}: "parent_id_chunk_0"
    content: "chunk text content"
    $vector: [0.123, 0.456, ...]  # embedding
    metadata: {
      entryType: "how_to"
      userType: "internal"
      category: "..."
      section: "overview"
      chunk_index: 0
      total_chunks: 5
      parent_entry_id: "parent_id"
      parent_title: "..."
      context_next_section: "steps"
      context_related_chunks: [...]
    }
```

---

## Error Handling

### Common Error Responses

**Entry Not Found (404)**:
```json
{
  "success": false,
  "error": "Entry not found"
}
```

**Sync Failed (500)**:
```json
{
  "success": false,
  "error": "Failed to sync entry",
  "entry_id": "abc123"
}
```

**Validation Error (400)**:
```json
{
  "success": false,
  "error": "title field is required"
}
```

---

## Performance Notes

### Optimization Strategies
1. **Embedding Cache**: Embeddings reused between searches
2. **Connection Pooling**: AstraDB connections are singletons
3. **Batch Operations**: Use bulk sync for multiple entries
4. **Chunk Limits**: How-to entries create 3-5 chunks typically

### Rate Limits
- No rate limits on backend (internal use)
- Frontend will implement rate limiting for customer agent

---

## Related Documentation
- `Chunking.md` - Detailed chunking logic and strategies
- `METADATA_FIX.md` - Recent metadata field standardization
- `/src/agent/README.md` - Agent orchestrator documentation

---

## Support
For issues or questions:
1. Check logs in `/logs/` directory
2. Test endpoints with test script
3. Review MCP server logs for sync issues

---

**Last Updated**: January 21, 2026
