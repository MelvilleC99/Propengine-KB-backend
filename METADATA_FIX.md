# Metadata Field Standardization Fix

## Issue Identified
There was an inconsistency in metadata field naming between chunking and vector search:

### Before Fix:
- **Chunking** (`chunking.py`): Used `"type": "definition"`
- **Vector Search** (`vector_search.py`): Filtered by `"entryType": "definition"`
- **Result**: Metadata filtering didn't work ❌

## Fix Applied
Standardized on `entryType` everywhere for consistency.

### Changes Made:
✅ **File**: `/src/mcp/vector_sync/chunking.py`

Changed all 4 chunk functions:
1. `chunk_definition()` - Line 149
2. `chunk_error()` - Line 208  
3. `chunk_how_to()` - Line 336
4. `chunk_single()` - Line 390

**Before**:
```python
metadata={
    "type": "definition",
    "category": entry.get("category"),
    "userType": entry.get("metadata", {}).get("userType", "internal"),
    ...
}
```

**After**:
```python
metadata={
    "entryType": "definition",
    "category": entry.get("category"),
    "userType": entry.get("metadata", {}).get("userType", "internal"),
    ...
}
```

## Impact

### Now Consistent Across System:
- ✅ **Chunking**: Stores `entryType` in metadata
- ✅ **Vector Search**: Filters by `entryType`
- ✅ **Orchestrator**: Maps query types to `entryType`

### Metadata Filter Now Works:
```python
# In vector_search.py
metadata_filter["entryType"] = "definition"  # ← Matches chunk metadata ✅

# In AstraDB
{
  "entryType": "definition",  # ← Stored by chunking ✅
  "userType": "internal",
  "category": "core_concepts"
}
```

## Next Steps

### ⚠️ Important: Re-sync Existing Entries
Any entries created BEFORE this fix will still have `"type"` instead of `"entryType"` in their metadata.

**Options**:
1. **Delete and re-sync** all vectors:
   ```bash
   # For each entry
   DELETE /api/kb/vectors/{entry_id}
   POST /api/kb/entries/{entry_id}/sync
   ```

2. **Clear AstraDB collection** and bulk re-sync:
   ```python
   # In Python/script
   for entry in firebase_entries:
       await sync_mcp.sync_entry_to_vector(entry['id'])
   ```

### Testing Checklist:
- [ ] Create new entry via API
- [ ] Sync to vectors
- [ ] Verify metadata contains `entryType` (not `type`)
- [ ] Test search with entry type filter
- [ ] Confirm results are filtered correctly

## Why `entryType` Over `type`?

1. **More descriptive**: Clear what type it refers to
2. **Avoids Python keyword**: `type` is a built-in
3. **Consistent pattern**: Matches `userType` naming
4. **No confusion**: Won't conflict with other "type" fields

## Files Affected
- ✅ `/src/mcp/vector_sync/chunking.py` - Fixed (4 edits)
- ✅ `/src/query/vector_search.py` - Already correct
- ✅ `/src/agent/orchestrator.py` - Already uses correct field

## Date Fixed
January 21, 2026
