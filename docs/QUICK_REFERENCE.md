# Quick Reference Card - PropertyEngine KB System

## 🚀 Most Common Operations

### Create & Sync Entry
```bash
# 1. Create
POST /api/kb/entries
{
  "type": "how_to",
  "title": "Entry Title",
  "content": "Searchable text",
  "metadata": {"category": "...", "userType": "internal"},
  "rawFormData": {...}
}
→ Returns: { "entry_id": "abc123" }

# 2. Sync to vectors
POST /api/kb/entries/abc123/sync
→ Returns: { "chunks_created": 5 }
```

### Update & Re-sync
```bash
PUT /api/kb/entries/abc123
{"content": "Updated..."}

POST /api/kb/entries/abc123/sync
```

### Delete Entry
```bash
# Permanent
DELETE /api/kb/entries/abc123

# Archive (soft delete)
POST /api/kb/entries/abc123/archive
```

---

## 📊 Entry Types & Chunking

| Type | Chunks | Sections |
|------|--------|----------|
| `definition` | 1 | Full content |
| `error` | 1 | Full content |
| `how_to` | 3-5 | overview, prerequisites, steps, issues, tips |
| `workflow` | 3-5 | Same as how_to |

---

## 🔍 Metadata Fields

### Required Fields
```json
{
  "entryType": "how_to",        // ⚠️ Use "entryType" not "type"!
  "userType": "internal",       // internal|external
  "category": "integrations"
}
```

### Optional Fields
```json
{
  "subcategory": "api",
  "product": "property_engine",
  "tags": ["crm", "setup"],
  "section": "prerequisites"     // Auto-added for chunks
}
```

---

## 🔗 Chunk ID Pattern

```
{parent_id}_chunk_{index}

Example:
abc123_chunk_0  → Overview
abc123_chunk_1  → Prerequisites
abc123_chunk_2  → Steps
```

---

## 📡 All Endpoints

### CRUD Operations
```
POST   /api/kb/entries           Create
GET    /api/kb/entries           List all
GET    /api/kb/entries/{id}      Get one
PUT    /api/kb/entries/{id}      Update
DELETE /api/kb/entries/{id}      Delete
POST   /api/kb/entries/{id}/archive  Archive
```

### Vector Operations
```
POST   /api/kb/entries/{id}/sync     Sync to vectors
GET    /api/kb/vectors               List vectors
DELETE /api/kb/vectors/{id}          Delete vector(s)
GET    /api/kb/stats/vectors         Get stats
```

---

## 🎯 Vector Status Flow

```
Created → "pending"
   ↓
Synced → "synced"
   ↓
Updated → "pending" (must re-sync)
   ↓
Deleted → vectors removed
```

---

## 🧪 Testing

```bash
# Test metadata consistency
python test_metadata_fix.py

# Check vector DB
GET /api/kb/vectors?limit=10

# Verify entry
GET /api/kb/entries/{id}
```

---

## ⚠️ Common Mistakes

❌ **Using "type" instead of "entryType"**
```json
{"type": "definition"}  // WRONG
```
✅ **Correct**
```json
{"entryType": "definition"}  // RIGHT
```

❌ **Forgetting to sync after update**
```bash
PUT /api/kb/entries/{id}
# Vectors are now outdated!
```
✅ **Correct**
```bash
PUT /api/kb/entries/{id}
POST /api/kb/entries/{id}/sync  # Re-sync!
```

❌ **Not checking vectorStatus**
```json
{"vectorStatus": "pending"}  // Not searchable yet!
```

---

## 🗂️ File Locations

### Backend
```
/src/api/kb_routes.py          → API endpoints
/src/mcp/firebase/server.py    → Firebase ops
/src/mcp/astradb/server.py     → Vector ops
/src/mcp/vector_sync/server.py → Sync orchestration
/src/mcp/vector_sync/chunking.py → Chunking logic
```

### Docs
```
/docs/DB_Endpoints.md    → Complete API reference
/docs/Chunking.md        → Chunking system docs
/docs/README.md          → Documentation index
METADATA_FIX.md          → Recent fix notes
```

---

## 🔧 Troubleshooting

### Entry not found in search?
1. Check `vectorStatus` is "synced"
2. Verify metadata fields (use `entryType`)
3. Test with direct chunk query

### Sync failed?
1. Check Firebase entry exists
2. Verify `rawFormData` structure
3. Review logs for errors

### Too many/few chunks?
1. Check entry type
2. Verify `rawFormData` sections
3. See Chunking.md for logic

---

## 📚 Full Documentation

- **Complete API Guide**: `docs/DB_Endpoints.md`
- **Chunking System**: `docs/Chunking.md`
- **Getting Started**: `docs/README.md`

---

**Print this card and keep it handy!** 🎉
