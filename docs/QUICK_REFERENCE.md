# 🎯 QUICK REFERENCE - Where Does It Go?

---

## 📖 **READING DATA (Display/List)**

### **Route:** Frontend → Firebase (Direct)

**Operations:**
- View entries list
- Filter entries
- Search entries
- Display entry details
- View archived entries

**Why Direct?**
- ✅ Fast (no backend)
- ✅ Simple (just reading)
- ✅ Less server load

**Code:**
```typescript
// In api-client.ts
export async function getKBEntries() {
  return getKBEntriesFirebase();  // Direct Firebase!
}
```

---

## ✏️ **WRITING DATA (Create/Update/Delete)**

### **Route:** Frontend → Backend → Firebase

**Operations:**
- Create new entry
- Update entry
- Delete entry
- Archive entry
- Restore entry

**Why Backend?**
- ✅ Secure (credentials hidden)
- ✅ Validation (check data)
- ✅ Business logic (processing)

**Code:**
```typescript
// In api-client.ts
export async function createKBEntry(data) {
  return fetch(`${BACKEND_URL}/api/kb/entries`, {
    method: 'POST',
    body: JSON.stringify(data)
  });
}
```

---

## 🤖 **PROCESSING DATA (Embeddings/Sync)**

### **Route:** Frontend → Backend → Vector DB

**Operations:**
- Sync to vector database
- Generate embeddings
- Vector search

**Why Backend?**
- ✅ Compute intensive
- ✅ Requires AI models
- ✅ Multiple DB coordination

**Code:**
```typescript
// In api-client.ts
export async function syncEntry(id) {
  return fetch(`${BACKEND_URL}/api/kb/entries/${id}/sync`, {
    method: 'POST'
  });
}
```

---

## 🎓 **REMEMBER:**

**If you're just LOOKING at data** → Firebase Direct  
**If you're CHANGING data** → Backend API  
**If you're PROCESSING data** → Backend API

---

## 🔍 **QUICK DECISION TREE:**

```
Does this operation just READ data?
├─ YES → Use Firebase directly (fast!)
└─ NO → Does it WRITE or PROCESS?
    └─ YES → Use Backend API (secure!)
```

---

**Simple!** 🎉
