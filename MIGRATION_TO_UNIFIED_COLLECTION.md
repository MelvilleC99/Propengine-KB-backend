# Backend Migration to Unified PropertyEngine Collection

This document outlines the changes made to migrate from multiple collections to a single unified PropertyEngine collection with metadata filtering.

## Changes Made

### 1. Settings Configuration (`src/config/settings.py`)
- **REMOVED**: Multiple collection environment variables:
  - `DEFINITIONS_COLLECTION`
  - `ERRORS_COLLECTION` 
  - `HOWTO_COLLECTION`
  - `WORKFLOWS_COLLECTION`
- **ADDED**: Single unified collection:
  - `PROPERTY_ENGINE_COLLECTION`

### 2. Vector Search (`src/query/vector_search.py`)
- **UPDATED**: `VectorSearch` class to use single collection
- **REPLACED**: `collection_configs` with `collection_name` and `entry_type_map`
- **MODIFIED**: `get_vector_store()` to create single vector store instance
- **ENHANCED**: `search()` method with metadata filtering:
  - `entry_type` parameter for filtering by content type
  - `user_type` parameter for filtering by audience
  - `additional_metadata_filter` for custom filters
- **SIMPLIFIED**: `extract_content()` method signature

### 3. Agent Orchestrator (`src/agent/orchestrator.py`)
- **REPLACED**: Collection routing with metadata filtering
- **REMOVED**: `collection_map` dictionary
- **ADDED**: Direct entry type mapping
- **ENHANCED**: Search fallback strategies using metadata filters
- **UPDATED**: Result processing to include entry_type and user_type
- **ADDED**: Optional `user_type_filter` parameter for future use

### 4. Chat Routes (`src/api/chat_routes.py`)
- **UPDATED**: Session metadata tracking
- **REPLACED**: `collections_used` with `searches_performed`
- **ENHANCED**: Search tracking with timestamps and query types

### 5. Database Connection (`src/database/connection.py`)
- **SIMPLIFIED**: Connection testing to single collection
- **REPLACED**: Multiple collection testing with unified collection test
- **UPDATED**: Logging and error handling

### 6. Environment Configuration (`.env.example`)
- **ADDED**: `ASTRADB_KEYSPACE` configuration
- **ADDED**: `ASTRADB_PROPERTY_ENGINE_COLLECTION` configuration
- **DOCUMENTED**: New unified collection approach

## Migration Benefits

### Technical Improvements
- **Simplified Architecture**: Single collection reduces complexity
- **Better Performance**: No cross-collection searches needed
- **Flexible Filtering**: Rich metadata enables precise content targeting
- **Easier Maintenance**: One collection to manage and monitor

### Search Enhancements
- **Content Type Filtering**: `metadata.entryType` filters by definition/error/how_to
- **Audience Filtering**: `metadata.userType` filters by internal/external/both
- **Product Filtering**: `metadata.product` enables multi-product support
- **Category Filtering**: `metadata.category` for organizational structure

### Data Structure
The unified collection uses this metadata structure:
```json
{
  "_id": "entry_id",
  "content": "searchable_text_content",
  "metadata": {
    "title": "entry_title",
    "type": "definition|error|how_to",
    "entryType": "definition|error|how_to", 
    "userType": "internal|external|both",
    "product": "property_engine|betterID|nurture",
    "category": "leads|sales|listings|etc",
    "subcategory": "optional_subcategory",
    "tags": "comma,separated,tags",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  },
  "$vector": [0.1, 0.2, ...]
}
```

## Environment Variables Required

Update your `.env` file with:
```bash
# Replace old collection variables with:
ASTRADB_PROPERTY_ENGINE_COLLECTION=property_engine
ASTRADB_KEYSPACE=default_keyspace
```

## Backward Compatibility

- **Query Classification**: Still works the same way
- **Response Format**: Enhanced with entry_type and user_type info
- **API Endpoints**: No breaking changes to external API
- **Search Logic**: Improved with metadata filtering

## Usage Examples

### Search by Content Type
```python
# Search only for definitions
results = await vector_search.search(
    query="what is mandate",
    entry_type="definition"
)

# Search only for how-to guides
results = await vector_search.search(
    query="how to create listing", 
    entry_type="howto"
)
```

### Search by Audience
```python
# Search only internal content
results = await vector_search.search(
    query="troubleshooting steps",
    user_type="internal"
)

# Search only external content  
results = await vector_search.search(
    query="how to upload photos",
    user_type="external"
)
```

### Combined Filtering
```python
# Search for internal error documentation
results = await vector_search.search(
    query="database connection failed",
    entry_type="error",
    user_type="internal"
)
```

This migration provides a more flexible, maintainable, and powerful search system while maintaining compatibility with existing functionality.
