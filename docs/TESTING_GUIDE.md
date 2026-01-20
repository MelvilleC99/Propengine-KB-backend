# Testing Guide - Firebase Operations via Backend

**Created:** 2026-01-16

---

## 🎯 **WHAT WE JUST DID**

### **Backend Changes:**
1. ✅ Created Firebase MCP (`src/mcp/firebase/`)
2. ✅ Created AstraDB MCP (`src/mcp/astradb/`)
3. ✅ Created Vector Sync MCP (`src/mcp/vector_sync/`)
4. ✅ Created API endpoints in `src/api/kb_routes.py`
5. ✅ Updated `main.py` to initialize Firebase at startup

### **Frontend Changes:**
1. ✅ Updated Next.js API routes to proxy to FastAPI backend
2. ✅ Routes now forward requests instead of calling Firebase directly

---

## 🧪 **TESTING FLOW**

### **Step 1: Start Backend**

```bash
cd /Users/melville/Documents/Propengine-KB-backend
python -m uvicorn main:app --reload
```

**Expected output:**
```
INFO: Starting PropEngine Support Agent...
✅ Firebase Admin SDK initialized successfully
✅ Firebase connection test successful
✅ All AstraDB collections connected successfully
INFO: Application startup complete.
INFO: Uvicorn running on http://127.0.0.1:8000
```

---

### **Step 2: Start Frontend**

```bash
cd /Users/melville/Documents/PropEngine_KB_Frontend/Propengine-KB-frontend
npm run dev
```

**Expected output:**
```
  ▲ Next.js 14.x.x
  - Local:        http://localhost:3000
  - ready in 2.1s
```

---

### **Step 3: Test Create Entry**

1. Go to `http://localhost:3000`
2. Login with test user
3. Click "Create KB Entry"
4. Fill in the form
5. Click "Submit"

**Expected Backend Logs:**
```
📝 Creating new KB entry: [Title]
✅ Created entry: [entry_id]
```

**Expected Frontend:**
- Success toast
- Redirect to entries list
- New entry appears

---

### **Step 4: Test Archive Entry**

1. Go to "Manage Entries"
2. Click archive button on an entry
3. Confirm

**Expected Backend Logs:**
```
📦 Archiving entry: [entry_id]
✅ Archived entry: [entry_id]
```

**Expected Frontend:**
- Entry removed from list
- Success toast

---

### **Step 5: Test Delete Entry**

1. Go to archived entries
2. Click permanent delete
3. Confirm

**Expected Backend Logs:**
```
🗑️ Deleting entry: [entry_id]
✅ Deleted entry: [entry_id]
```

---

### **Step 6: Test Sync Entry**

1. Create a new entry
2. Click "Sync" button
3. Watch the status change

**Expected Backend Logs:**
```
🔄 Starting sync for entry: [entry_id]
📄 Retrieved entry from Firebase: [title]
📝 Prepared content (XXX chars)
✅ Stored vector in AstraDB
✅ Successfully synced entry: [entry_id]
```

**Expected Frontend:**
- vectorStatus changes: pending → synced
- Success toast
- Green checkmark in table

---

## 🔍 **DEBUGGING**

### **If Backend doesn't start:**

Check Firebase environment variables:
```bash
# Backend .env should have:
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n..."
FIREBASE_CLIENT_EMAIL=firebase-adminsdk-...@....iam.gserviceaccount.com
```

### **If Frontend can't reach backend:**

Check frontend `.env.local`:
```bash
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

### **If create fails:**

Check browser console for:
```
🔄 Proxying POST request to: http://localhost:8000/api/kb/entries
```

Check backend logs for:
```
📝 Creating new KB entry: ...
```

---

## ✅ **SUCCESS INDICATORS**

**Everything works when:**
1. ✅ Backend starts without errors
2. ✅ Firebase connection test passes
3. ✅ Can create entries (appear in Firebase)
4. ✅ Can archive entries
5. ✅ Can sync entries (appear in AstraDB)
6. ✅ All operations show in backend logs

---

## 🚨 **COMMON ISSUES**

### **Issue 1: "Firebase not initialized"**
**Solution:** Make sure `initialize_firebase()` is called in `main.py` lifespan

### **Issue 2: "CORS error"**
**Solution:** Backend needs CORS middleware for `http://localhost:3000`

### **Issue 3: "404 Not Found"**
**Solution:** Check backend is running on port 8000, frontend on 3000

### **Issue 4: "Entry not found"**
**Solution:** Entry might be in wrong Firebase collection or database

---

## 📊 **CURRENT ARCHITECTURE**

```
USER BROWSER
    ↓
FRONTEND (Next.js - Port 3000)
    ↓ /api/kb/entries
NEXT.JS API ROUTE (Proxy)
    ↓ HTTP
FASTAPI BACKEND (Port 8000)
    ↓ /api/kb/entries
KB_ROUTES.PY
    ↓
FIREBASE MCP
    ↓
FIREBASE DATABASE
```

**All Firebase operations now go through backend!** 🎉

---

## 🎓 **WHAT TO TEST NEXT**

After basic operations work:
1. Test with real data
2. Test sync with multiple entries
3. Test search (vector database)
4. Test error handling (invalid data)
5. Load testing (many entries)

---

**Ready to test?** Start both servers and try creating an entry! 🚀
