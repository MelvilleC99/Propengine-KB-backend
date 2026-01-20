# Hierarchical Search Architecture - Decision Document

## 🎯 **THE BIG QUESTION**

**Where does the query go? Firebase → AstraDB? Or straight to AstraDB?**

---

## 📊 **CURRENT STATE**

### What We Have:
```
User Query
    ↓
VectorSearch.search()
    ↓
AstraDB (vector similarity search)
    ↓
Results with metadata
```

### Metadata Currently Stored in Vectors:
```python
{
    "id": "abc123",
    "title": "How to upload photos",
    "type": "how_to",           # Entry type
    "entryType": "how_to",      
    "userType": "internal",     # Who can see this
    "product": "property_engine",
    "category": "listings",     # Main category
    "subcategory": "photos",    # Sub-category
    "tags": ["upload", "photos"],
    "createdAt": "2026-01-15",
    "lastSyncedAt": "2026-01-16"
}
```

---

## 🔀 **OPTION 1: Direct to AstraDB (Vector-First)**

```
User Query: "how do I upload photos for a listing?"
    ↓
[Query Analysis]
    ↓
AstraDB Vector Search
    ├─ Semantic similarity (embedding match)
    ├─ Metadata filters (category, userType, type)
    └─ Score threshold (0.7)
    ↓
Top K Results (k=5-10)
    ↓
[Optional Re-ranking]
    ↓
Firebase (fetch full entry details)
    ↓
Return to User
```

**Pros:**
- ✅ Fast - One hop to find relevant content
- ✅ Semantic search - Finds conceptually similar content
- ✅ Scalable - AstraDB handles millions of vectors
- ✅ Metadata filtering built-in (AstraDB supports it)

**Cons:**
- ❌ Can't filter by Firebase-only fields (archived, draft status)
- ❌ Vector might be stale if Firebase updated but not re-synced

**Best For:**
- User-facing search (speed matters)
- Semantic "what's related to X?" queries
- Large-scale KB with thousands of entries

---

## 🔀 **OPTION 2: Firebase → AstraDB (Hierarchical)**

```
User Query: "how do I upload photos for a listing?"
    ↓
[Query Analysis & Metadata Extraction]
    ↓
Firebase Filter (Step 1 - Narrow Down)
    ├─ archived = false
    ├─ userType matches user's role
    ├─ product = "property_engine"
    └─ Get entry IDs
    ↓
AstraDB Vector Search (Step 2 - Rank by Relevance)
    ├─ Only search vectors with IDs from step 1
    ├─ Semantic similarity
    └─ Score threshold
    ↓
Top K Results
    ↓
Firebase (fetch full details)
    ↓
Return to User
```

**Pros:**
- ✅ Always fresh - Firebase is source of truth
- ✅ Can filter by Firebase-specific fields (archived, permissions)
- ✅ Guarantees only valid entries are searched
- ✅ Better security - Firebase controls access

**Cons:**
- ❌ Slower - Two database hops
- ❌ More complex - Need to coordinate two systems
- ❌ Doesn't scale as well - Firebase query first

**Best For:**
- Admin tools (accuracy > speed)
- Permission-sensitive queries
- When Firebase has critical filter fields

---

## 🎯 **OPTION 3: HYBRID (Context-Aware)**

**Use different strategies based on query type:**

### **Strategy A: Vector-First (Default)**
```
General semantic queries → Direct to AstraDB
Example: "how do I upload photos?"
```

### **Strategy B: Firebase-First**
```
Admin queries → Firebase → AstraDB
Example: "show me archived error entries"
```

### **Strategy C: Parallel**
```
Complex queries → Both simultaneously
Firebase: Get IDs matching filters
AstraDB: Get semantic matches
Intersect results
```

---

## 🏗️ **HIERARCHICAL SEARCH LAYERS**

Here's how we can use metadata in a hierarchical way:

### **Layer 1: Product/Permission Filter (Pre-filter)**
```python
# Before vector search, filter by:
metadata_filter = {
    "product": "property_engine",      # Only this product
    "userType": "internal"              # Only internal docs
}
```

### **Layer 2: Vector Similarity (Semantic Search)**
```python
# AstraDB returns top K matches based on:
- Query embedding similarity
- Applied metadata filters from Layer 1
```

### **Layer 3: Type/Category Boosting (Re-rank)**
```python
# After getting results, boost scores based on:
if query_mentions_error and result.type == "error":
    score *= 1.5  # Boost error entries
if query_mentions_category and result.category == category:
    score *= 1.3  # Boost matching category
```

### **Layer 4: Recency/Usage (Final Sort)**
```python
# Sort by combination of:
- Semantic similarity score
- Boost factors
- Recency (newer entries ranked higher)
- Usage count (popular entries ranked higher)
```

---

## 💡 **MY RECOMMENDATION**

### **Use OPTION 3 (Hybrid) with this flow:**

```python
async def search_kb(query: str, user_context: dict, filters: dict = None):
    """
    Intelligent search routing based on query type
    """
    # 1. Analyze query
    needs_firebase_filter = has_admin_filters(filters) or filters.get("archived")
    
    if needs_firebase_filter:
        # Option 2: Firebase → AstraDB (Hierarchical)
        entry_ids = await firebase_mcp.filter_entries(filters)
        results = await astradb_mcp.search_vectors(
            query=query,
            filter={"id": {"$in": entry_ids}}  # Only search these IDs
        )
    else:
        # Option 1: Direct to AstraDB (Vector-First)
        metadata_filter = {
            "userType": user_context.get("userType"),
            "product": user_context.get("product", "property_engine")
        }
        results = await astradb_mcp.search_vectors(
            query=query,
            filter=metadata_filter
        )
    
    # 3. Re-rank with hierarchy
    results = apply_hierarchical_boosting(results, query, user_context)
    
    # 4. Fetch full details from Firebase for top results
    top_results = results[:5]  # Top 5
    enriched = await firebase_mcp.get_entries_batch([r["entry_id"] for r in top_results])
    
    return enriched
```

---

## 🔑 **KEY DECISIONS NEEDED**

1. **Primary Search Path:**
   - [ ] Vector-First (fast, semantic)
   - [ ] Firebase-First (accurate, filtered)
   - [ ] Hybrid (context-aware)

2. **Metadata Usage:**
   - [ ] Pre-filter (before vector search)
   - [ ] Post-filter (after vector search)
   - [ ] Boost scores (during re-ranking)

3. **Firebase Role:**
   - [ ] Source of truth (fetch after vector search)
   - [ ] Pre-filter (narrow before vector search)
   - [ ] Ignore (vector DB is sufficient)

4. **Hierarchy Levels:**
   - [ ] 2-tier (Product → Vector)
   - [ ] 3-tier (Product → Category → Vector)
   - [ ] 4-tier (Product → Category → Type → Vector)

---

## 📋 **QUESTIONS FOR YOU**

1. **Speed vs Accuracy:** Is search speed (100ms) or accuracy (always fresh) more important?

2. **User Context:** Do different user types (agent vs admin) see different results?

3. **Firebase Filters:** Do you need to filter by fields that are ONLY in Firebase (archived, draft, approval status)?

4. **Search Patterns:** What are the most common query types?
   - "How do I...?" (semantic, procedural)
   - "Error: X" (keyword, specific)
   - "Show me archived errors" (filtered, admin)

5. **Scale:** How many entries do you expect? (hundreds, thousands, millions?)

---

## 🎯 **NEXT STEPS**

Once we agree on the search architecture, I'll implement:

1. **Query Processor** - Analyzes queries and routes appropriately
2. **Hierarchical Search** - Implements chosen strategy
3. **Metadata Boosting** - Uses metadata for re-ranking
4. **Result Enrichment** - Fetches full details from Firebase

**What's your preference?** 🤔
