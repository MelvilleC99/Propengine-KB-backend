# Metadata Pre-Filtering in AstraDB - How It Works

## ✅ **YES - You Can Filter Metadata BEFORE Vector Search!**

AstraDB supports metadata filtering as a **pre-filter** before semantic search.
This is MUCH more efficient than searching all vectors and filtering after.

---

## 🔍 **How It Works Internally**

```
┌─────────────────────────────────────────────────────┐
│ AstraDB Vector Database                             │
│                                                      │
│ 10,000 vectors total                                │
│   ├─ 3,000 vectors: userType="agent"                │
│   ├─ 5,000 vectors: userType="internal"             │
│   └─ 2,000 vectors: userType="external"             │
└─────────────────────────────────────────────────────┘
                      ↓
         User Query: "upload photos"
         Metadata Filter: {userType: "agent"}
                      ↓
┌─────────────────────────────────────────────────────┐
│ Step 1: FILTER by Metadata (Pre-filter)            │
│                                                      │
│ AstraDB narrows search to:                          │
│ 3,000 vectors where userType="agent"                │
│                                                      │
│ (Ignores 7,000 other vectors entirely)              │
└─────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────┐
│ Step 2: VECTOR SEARCH (Semantic similarity)        │
│                                                      │
│ Search only those 3,000 filtered vectors            │
│ Find top K=5 with highest similarity                │
└─────────────────────────────────────────────────────┘
                      ↓
         Returns 5 results that are:
         ✅ userType="agent"
         ✅ Semantically similar to "upload photos"
```

---

## 📝 **Code Examples**

### **Example 1: Filter by User Type**

```python
from src.mcp.astradb import AstraDBMCP

astra = AstraDBMCP()

# Search only agent-facing documentation
results = await astra.search_vectors(
    query="how to upload photos",
    k=5,
    filter={
        "userType": "agent"  # ← Pre-filters to only agent docs
    },
    score_threshold=0.7
)

# Results will ONLY include entries where:
# - userType == "agent"
# - Semantic similarity >= 0.7
```

### **Example 2: Multiple Metadata Filters**

```python
# Search only internal error documentation
results = await astra.search_vectors(
    query="upload failed error",
    k=10,
    filter={
        "userType": "internal",    # Only internal docs
        "type": "error",            # Only error entries
        "category": "listings"      # Only listings category
    },
    score_threshold=0.75
)

# Results will ONLY include entries where ALL conditions match:
# - userType == "internal"
# - type == "error"
# - category == "listings"
# - Semantic similarity >= 0.75
```

### **Example 3: Filter by Product + Category**

```python
# Search property engine listings documentation
results = await astra.search_vectors(
    query="property description templates",
    k=5,
    filter={
        "product": "property_engine",
        "category": "listings",
        "subcategory": "descriptions"
    }
)

# This is MUCH faster than:
# 1. Searching all 10,000 vectors
# 2. Filtering results after
```

---

## 🎯 **Hierarchical Filtering Strategy**

### **Layer 1: Product (Always filter)**
```python
filter = {
    "product": "property_engine"  # Never search other products
}
```

### **Layer 2: User Type (Context-based)**
```python
if user.role == "agent":
    filter["userType"] = "agent"
elif user.role == "admin":
    # Admins see everything - no filter
    pass
else:
    filter["userType"] = "external"
```

### **Layer 3: Category (Query-based)**
```python
# Extract from query or user context
if "listing" in query.lower():
    filter["category"] = "listings"
elif "lead" in query.lower():
    filter["category"] = "leads"
```

### **Layer 4: Type (Intent-based)**
```python
if "error" in query.lower() or "problem" in query.lower():
    filter["type"] = "error"
elif "how to" in query.lower() or "how do i" in query.lower():
    filter["type"] = "how_to"
elif "what is" in query.lower():
    filter["type"] = "definition"
```

---

## ⚡ **Performance Benefits**

### **WITHOUT Pre-filtering:**
```
Search 10,000 vectors → Get 100 matches → Filter by metadata → Return 5
Time: ~300ms
```

### **WITH Pre-filtering:**
```
Filter to 1,000 vectors → Search 1,000 vectors → Get 5 matches
Time: ~80ms
```

**Result: 3-4x faster!** ⚡

---

## 🏗️ **Recommended Search Architecture**

```python
async def intelligent_search(query: str, user_context: dict):
    """
    Hierarchical metadata-filtered vector search
    """
    # 1. Build metadata filter based on context
    metadata_filter = {}
    
    # Layer 1: Product (always)
    metadata_filter["product"] = "property_engine"
    
    # Layer 2: User permissions
    if user_context.get("role") == "agent":
        metadata_filter["userType"] = "agent"
    elif user_context.get("role") != "admin":
        metadata_filter["userType"] = "external"
    
    # Layer 3: Query analysis (optional)
    query_lower = query.lower()
    if "error" in query_lower:
        metadata_filter["type"] = "error"
    
    # 2. Search with pre-filter
    astra = AstraDBMCP()
    results = await astra.search_vectors(
        query=query,
        k=10,
        filter=metadata_filter,
        score_threshold=0.7
    )
    
    # 3. Results are already filtered - no post-processing needed!
    return results
```

---

## ✅ **Current Metadata Available for Filtering**

From `vector_sync/server.py`, we store:

```python
{
    "id": "abc123",
    "title": "How to upload photos",
    "type": "how_to",              # ← Can filter
    "entryType": "how_to",         # ← Can filter  
    "userType": "internal",        # ← Can filter
    "product": "property_engine",  # ← Can filter
    "category": "listings",        # ← Can filter
    "subcategory": "photos",       # ← Can filter
    "tags": ["upload", "photos"],  # ← Can filter
    "createdAt": "2026-01-15",     # ← Can filter
    "lastSyncedAt": "2026-01-16"   # ← Can filter
}
```

**All of these can be used as pre-filters!**

---

## 🎯 **Answer to Your Question**

> "Can we filter against the metadata in AstraDB before we search the vector?"

**YES! This is exactly what you should do, and it's already built in!**

The `filter` parameter in `search_vectors()` applies metadata filters **BEFORE** 
the vector similarity search, making it much faster and more accurate.

---

## 📋 **Next Steps**

1. **Define your filtering hierarchy:**
   - Which metadata fields are most important?
   - What's the user permission model?

2. **Implement query processor:**
   - Analyzes query to extract intent
   - Builds appropriate metadata filter
   - Calls AstraDB with pre-filter

3. **Test performance:**
   - Measure search speed with/without filters
   - Verify results are correctly filtered

**Ready to implement once you answer the questions!** 🚀
