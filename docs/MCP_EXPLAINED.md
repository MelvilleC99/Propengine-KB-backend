# Understanding MCPs and Backend APIs

**Created:** 2026-01-16

---

## 🤔 **WHAT IS AN MCP (Model Context Protocol)?**

### **Simple Explanation:**

**MCP = A standardized way for AI models to interact with external tools/services**

Think of MCPs like **electrical outlets** 🔌:
- You don't need to know how electricity works
- You just plug in and it works
- Standard interface for any device

**MCPs provide a standard interface** for Claude (or any AI) to:
- Read/write databases
- Call APIs
- Access file systems
- Use external tools

---

## 🏗️ **MCP ARCHITECTURE**

```
┌──────────────────────────────────────────────────────┐
│  AI MODEL (Claude)                                   │
│  "Create a KB entry about authentication"           │
└──────────────────────────────────────────────────────┘
                        ↓
                    Uses MCP
                        ↓
┌──────────────────────────────────────────────────────┐
│  MCP SERVER (Your Backend)                           │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐    │
│  │ Firebase   │  │ AstraDB    │  │VectorSync  │    │
│  │   MCP      │  │   MCP      │  │   MCP      │    │
│  └────────────┘  └────────────┘  └────────────┘    │
└──────────────────────────────────────────────────────┘
         ↓                ↓                ↓
    ┌─────────┐      ┌─────────┐     ┌─────────┐
    │Firebase │      │ AstraDB │     │  Sync   │
    │   DB    │      │ Vector  │     │ Logic   │
    └─────────┘      └─────────┘     └─────────┘
```

---

## 📦 **YOUR MCP STRUCTURE**

### **1. Firebase MCP** (`src/mcp/firebase/`)

**What it does:**
- CRUD operations on Firestore
- create_entry()
- get_entry()
- update_entry()
- delete_entry()
- archive_entry()
- list_entries()

**Example:**
```python
firebase_mcp = FirebaseMCP()
result = await firebase_mcp.create_entry({
    "title": "How to reset password",
    "type": "how_to",
    "content": "..."
})
# Returns: {"success": True, "entry_id": "abc123"}
```

---

### **2. AstraDB MCP** (`src/mcp/astradb/`)

**What it does:**
- Vector database operations
- store_vector()
- update_vector()
- delete_vector()
- search_vectors()

**Example:**
```python
astra_mcp = AstraDBMCP()
result = await astra_mcp.store_vector(
    entry_id="abc123",
    content="How to reset password...",
    metadata={"type": "how_to"}
)
# Automatically generates embedding and stores it
```

---

### **3. Vector Sync MCP** (`src/mcp/vector_sync/`)

**What it does:**
- Orchestrates Firebase + AstraDB
- sync_entry_to_vector()
- resync_entry()
- unsync_entry()

**Example:**
```python
sync_mcp = VectorSyncMCP()
result = await sync_mcp.sync_entry_to_vector("abc123")
# 1. Gets from Firebase
# 2. Prepares content
# 3. Stores in AstraDB
# 4. Updates Firebase status
```

---

## 🔄 **WHY DO WE STILL NEED BACKEND APIs?**

**GREAT QUESTION!** Here's why:

### **MCPs ≠ HTTP Endpoints**

**MCPs are internal tools** (Python functions)  
**APIs are external interfaces** (HTTP endpoints)

```
FRONTEND (Browser)
    ↓ HTTP Request
    ↓ POST /api/kb/entries
BACKEND API ENDPOINT
    ↓ Calls MCP
    ↓ firebase_mcp.create_entry()
MCP SERVER
    ↓ Writes to
FIREBASE DATABASE
```

---

## 🎯 **THE COMPLETE FLOW**

### **Example: User Creates KB Entry**

```
┌─────────────────────────────────────────────────────┐
│  STEP 1: Frontend sends HTTP request                │
├─────────────────────────────────────────────────────┤
│  fetch('http://localhost:8000/api/kb/entries', {    │
│    method: 'POST',                                   │
│    body: JSON.stringify({                           │
│      title: "How to upload photos",                 │
│      type: "how_to",                                │
│      content: "..."                                  │
│    })                                               │
│  })                                                  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  STEP 2: Backend API receives request               │
├─────────────────────────────────────────────────────┤
│  @router.post("/entries")                           │
│  async def create_entry(data: dict):                │
│      # Validate data                                │
│      # Call MCP                                     │
│      firebase_mcp = FirebaseMCP()                   │
│      result = await firebase_mcp.create_entry(data) │
│      return result                                  │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  STEP 3: Firebase MCP writes to database            │
├─────────────────────────────────────────────────────┤
│  class FirebaseMCP:                                 │
│      async def create_entry(self, data):            │
│          doc_ref = self.db.collection('kb_entries') │
│          doc_ref.document().set(data)               │
│          return {"success": True, "id": "abc123"}   │
└─────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────┐
│  STEP 4: Response flows back to frontend            │
├─────────────────────────────────────────────────────┤
│  {"success": true, "entry_id": "abc123"}            │
└─────────────────────────────────────────────────────┘
```

---

## 💡 **KEY CONCEPTS**

### **1. MCPs = Internal Tools**
- Python classes with methods
- Used WITHIN your backend
- Not directly accessible from internet

### **2. APIs = External Interface**
- HTTP endpoints (REST)
- Accept requests from frontend/mobile/etc
- Call MCPs to do the work

### **3. Separation of Concerns**

```
API Layer (src/api/)
├── Validates input
├── Handles authentication
├── Returns HTTP responses
└── Calls → MCPs

MCP Layer (src/mcp/)
├── Business logic
├── Database operations
└── No HTTP knowledge needed
```

---

## 🔐 **WHY THIS ARCHITECTURE IS BETTER**

### **Before (Current mess):**
```
Frontend → Firebase directly ❌
Frontend → AstraDB directly ❌
Frontend → Has all credentials exposed ❌
```

### **After (Clean MCP architecture):**
```
Frontend → Backend API ✅
Backend API → MCPs ✅
MCPs → Databases ✅
Credentials stay on server ✅
```

---

## 📊 **EXAMPLE: Complete Sync Flow**

### **User clicks "Sync" button:**

```python
# 1. Frontend calls API
fetch('/api/kb/entries/abc123/sync', {method: 'POST'})

# 2. Backend API endpoint
@router.post("/entries/{entry_id}/sync")
async def sync_entry(entry_id: str):
    # Initialize MCP
    sync_mcp = VectorSyncMCP()
    
    # Call MCP operation
    result = await sync_mcp.sync_entry_to_vector(entry_id)
    
    # Return HTTP response
    return JSONResponse(result)

# 3. Vector Sync MCP orchestrates
class VectorSyncMCP:
    async def sync_entry_to_vector(self, entry_id):
        # Get from Firebase MCP
        entry = await self.firebase.get_entry(entry_id)
        
        # Store in AstraDB MCP
        await self.astradb.store_vector(
            entry_id, 
            content, 
            metadata
        )
        
        # Update Firebase MCP
        await self.firebase.update_entry(entry_id, {
            "vectorStatus": "synced"
        })
        
        return {"success": True}
```

---

## ✅ **BENEFITS OF THIS APPROACH**

1. **Security** 🔒
   - Credentials never exposed to frontend
   - All authentication on server

2. **Maintainability** 🛠️
   - Change database? Just update MCP
   - API stays the same

3. **Testability** 🧪
   - Test MCPs independently
   - Mock MCPs in API tests

4. **Reusability** ♻️
   - Use same MCPs in different APIs
   - Use same MCPs in CLI tools

5. **Scalability** 📈
   - Add caching in MCPs
   - Add rate limiting in APIs
   - Easy to add new features

---

## 🎓 **SUMMARY**

**MCPs** = Internal tools (like a library)  
**APIs** = External interface (like a website)

**You need both because:**
- MCPs do the work (talk to databases)
- APIs expose the work (HTTP for frontend)

**Think of it like a restaurant:**
- **Kitchen (MCPs)** = Where food is made
- **Waiters (APIs)** = Take orders, serve food
- **Customers (Frontend)** = Don't enter kitchen, order through waiters

---

**Does this make sense now?** 🚀
