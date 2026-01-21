# PropertyEngine Knowledge Base - Documentation Index

## Overview
This folder contains comprehensive documentation for the PropertyEngine Knowledge Base system, covering database operations, chunking logic, and system architecture.

---

## 📚 Available Documentation

### 1. [DB_Endpoints.md](./DB_Endpoints.md)
**Complete Database API Reference**

**Contents**:
- ✅ All 10 backend API endpoints with examples
- ✅ Request/response formats for each endpoint
- ✅ Frontend API routes (current and planned)
- ✅ MCP server architecture (Firebase, AstraDB, Vector Sync)
- ✅ Complete workflow examples
- ✅ Database schemas (Firebase & AstraDB)
- ✅ Error handling and troubleshooting

**Use When**:
- Setting up API integrations
- Building frontend components
- Debugging database operations
- Understanding data flow

---

### 2. [Chunking.md](./Chunking.md)
**Intelligent Chunking System Documentation**

**Contents**:
- ✅ Why chunking improves search precision
- ✅ Chunking strategies by entry type (Definition, Error, How-To)
- ✅ Context system explained
- ✅ Metadata structure and flattening
- ✅ Chunk ID naming conventions
- ✅ Helper functions and utilities
- ✅ Complete flow diagrams
- ✅ Testing and troubleshooting

**Use When**:
- Understanding how content is split
- Debugging search results
- Optimizing content structure
- Building context-aware features

---

## 🗺️ Quick Navigation

### For Developers

**Backend Development**:
1. Start with [DB_Endpoints.md](./DB_Endpoints.md) - Sections 1-10
2. Review [Chunking.md](./Chunking.md) - Sections 1-3
3. Check MCP architecture in [DB_Endpoints.md](./DB_Endpoints.md)

**Frontend Development**:
1. Read [DB_Endpoints.md](./DB_Endpoints.md) - Frontend API Routes
2. Review response formats in [DB_Endpoints.md](./DB_Endpoints.md) - Sections 1-10
3. Understand chunk structure in [Chunking.md](./Chunking.md) - Section 3

**Testing/QA**:
1. Follow workflows in [DB_Endpoints.md](./DB_Endpoints.md)
2. Use test scripts in parent directory
3. Check troubleshooting in [Chunking.md](./Chunking.md)

---

## 📊 System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    FRONTEND (Next.js)                        │
│  /app/api/support-agent/ → Backend API Proxy                │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                 BACKEND API (FastAPI)                        │
│  /api/kb/* → KB Management Endpoints                        │
│  /api/chat → Agent Chat Endpoint                            │
└────────────────┬───────────────────┬────────────────────────┘
                 │                   │
        ┌────────▼────────┐ ┌───────▼────────┐
        │  Firebase MCP   │ │  AstraDB MCP   │
        │  (Entry CRUD)   │ │  (Vectors)     │
        └────────┬────────┘ └───────┬────────┘
                 │                   │
                 └────────┬──────────┘
                          │
                    ┌─────▼──────┐
                    │ Vector     │
                    │ Sync MCP   │
                    │ (Chunking) │
                    └────────────┘
```

**See**: [DB_Endpoints.md](./DB_Endpoints.md) for detailed architecture

---

## 🔑 Key Concepts

### Entry Types
1. **Definition** - Single concept, single chunk
2. **Error** - Problem + solution, single chunk
3. **How-To** - Multi-section guide, 3-5 chunks
4. **Workflow** - Process documentation, 3-5 chunks

**See**: [Chunking.md](./Chunking.md) - Sections 1-3

---

### Metadata Fields
```json
{
  "entryType": "how_to",      // ⚠️ MUST be "entryType"
  "userType": "internal",     // internal|external
  "category": "integrations",
  "section": "prerequisites"  // for multi-chunk entries
}
```

**Important**: Recent fix standardized on `entryType` (not `type`)  
**See**: `../METADATA_FIX.md` for details

---

### Vector Status Flow
```
1. Created    → vectorStatus: "pending"
2. Synced     → vectorStatus: "synced"
3. Failed     → vectorStatus: "failed"
4. Deleted    → vectorStatus: "pending" (after vector deletion)
```

**See**: [DB_Endpoints.md](./DB_Endpoints.md) - Section 7

---

## 🚀 Quick Start Guide

### Creating Your First Entry

```bash
# 1. Create entry
POST /api/kb/entries
{
  "type": "definition",
  "title": "API Key",
  "content": "A unique identifier for authentication",
  "metadata": {
    "category": "core_concepts",
    "userType": "internal"
  },
  "rawFormData": {
    "term": "API Key",
    "definition": "A unique identifier..."
  }
}

# 2. Get entry ID from response
# Response: { "entry_id": "abc123" }

# 3. Sync to vectors
POST /api/kb/entries/abc123/sync

# 4. Verify in vector DB
GET /api/kb/vectors?limit=5

# 5. Test search
POST /api/chat
{
  "message": "what is an API key",
  "session_id": "test123"
}
```

**Full Details**: [DB_Endpoints.md](./DB_Endpoints.md) - Complete Workflow Example

---

## 🔧 Common Tasks

### Task 1: Update an Entry
```bash
# Update content
PUT /api/kb/entries/{id}
{ "content": "Updated content..." }

# Re-sync vectors
POST /api/kb/entries/{id}/sync
```

**See**: [DB_Endpoints.md](./DB_Endpoints.md) - Section 4

---

### Task 2: Delete an Entry
```bash
# Option A: Hard delete (permanent)
DELETE /api/kb/entries/{id}

# Option B: Soft delete (archive)
POST /api/kb/entries/{id}/archive
```

**See**: [DB_Endpoints.md](./DB_Endpoints.md) - Sections 5-6

---

### Task 3: Debug Chunking
```python
# View chunks created
GET /api/kb/vectors?limit=50

# Check specific entry
GET /api/kb/entries/{id}
# Look for: chunksCreated, vectorStatus
```

**See**: [Chunking.md](./Chunking.md) - Testing Chunking

---

## 📝 Additional Resources

### In Parent Directory

- **`METADATA_FIX.md`** - Recent metadata field standardization fix
- **`test_metadata_fix.py`** - Script to verify chunking consistency
- **`/src/agent/README.md`** - Agent orchestrator documentation
- **`/src/api/kb_routes.py`** - API endpoint implementations
- **`/src/mcp/vector_sync/chunking.py`** - Chunking logic source

---

## 🆘 Troubleshooting

### Common Issues

**Search not finding entries?**
→ Check [Chunking.md](./Chunking.md) - Common Issues & Solutions

**API errors?**
→ Check [DB_Endpoints.md](./DB_Endpoints.md) - Error Handling

**Sync failures?**
→ Review [DB_Endpoints.md](./DB_Endpoints.md) - MCP Servers

**Metadata inconsistencies?**
→ See `../METADATA_FIX.md`

---

## 📅 Change Log

### January 21, 2026
- ✅ Created comprehensive documentation
- ✅ Fixed metadata field mismatch (`type` → `entryType`)
- ✅ Standardized on `entryType` across system
- ✅ Added DB_Endpoints.md and Chunking.md
- ✅ Created this index document

---

## 👥 For New Team Members

### Recommended Reading Order

1. **Start Here**: Read this index fully
2. **API Basics**: [DB_Endpoints.md](./DB_Endpoints.md) - Sections 1-7
3. **Chunking Basics**: [Chunking.md](./Chunking.md) - Sections 1-3
4. **Test Everything**: Run `test_metadata_fix.py` 
5. **Deep Dive**: Read full docs as needed

---

## 🎯 Goals & Architecture Decisions

### Why This Structure?

**MCP (Model Context Protocol) Architecture**:
- Clean separation of concerns
- Firebase MCP handles all database ops
- AstraDB MCP handles all vector ops
- Vector Sync MCP orchestrates between them

**Benefits**:
- Easy to test individual components
- Can swap out Firebase/AstraDB easily
- Clear data flow and responsibilities

**Smart Chunking**:
- Better search precision (match specific sections)
- Context preservation (know what's before/after)
- Future-proof (easy to add new chunk types)

**Benefits**:
- Users get exact answers, not full documents
- Agent can suggest related sections
- Better embeddings = better search

---

## 📧 Contact & Support

For questions or issues:
1. Check troubleshooting sections in docs
2. Review logs in `/logs/` directory
3. Test with provided scripts
4. Contact dev team with specific error messages

---

**Documentation Maintained By**: Development Team  
**Last Updated**: January 21, 2026  
**Version**: 1.0
