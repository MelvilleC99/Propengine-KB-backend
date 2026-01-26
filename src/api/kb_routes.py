"""KB Management API Routes - Using MCP Architecture"""

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from src.mcp.firebase import FirebaseMCP
from src.mcp.vector_sync import VectorSyncMCP
from src.mcp.astradb import AstraDBMCP

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/kb", tags=["kb"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class CreateEntryRequest(BaseModel):
    """Request to create a new KB entry - matches frontend format"""
    type: str = Field(..., description="Entry type: how_to, error, definition, workflow")
    title: str = Field(..., min_length=3, description="Entry title")
    content: str = Field(..., description="Searchable text content")  # STRING not dict!
    metadata: Dict[str, Any] = Field(..., description="Entry metadata with category, userType, etc")
    rawFormData: Optional[Dict[str, Any]] = Field(default=None, description="Raw form data")
    tags: Optional[List[str]] = Field(default=None, description="Entry tags")
    author: Optional[str] = Field(default=None, description="Entry author")


class UpdateEntryRequest(BaseModel):
    """Request to update an existing KB entry"""
    title: Optional[str] = None
    content: Optional[str] = None  # STRING not dict!
    metadata: Optional[Dict[str, Any]] = None
    rawFormData: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class EntryResponse(BaseModel):
    """Response containing entry data"""
    success: bool
    entry_id: str
    entry: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class ListEntriesResponse(BaseModel):
    """Response containing list of entries"""
    success: bool
    entries: List[Dict[str, Any]]
    count: int


class SyncRequest(BaseModel):
    """Request to sync a KB entry to vector database"""
    entry_id: str


class SyncResponse(BaseModel):
    """Response from sync operation"""
    success: bool
    message: str
    entry_id: str
    error: Optional[str] = None


# ============================================================================
# ENDPOINTS - CRUD OPERATIONS
# ============================================================================

@router.post("/entries", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(request: CreateEntryRequest):
    """
    Create a new KB entry in Firebase.
    
    Steps:
    1. Validate input data
    2. Call Firebase MCP to create entry
    3. Return entry ID
    
    Note: Entry is created with vectorStatus="pending"
    Use /sync endpoint to sync to vector database
    """
    try:
        logger.info(f"📝 Creating new KB entry: {request.title}")
        
        # Prepare entry data
        entry_data = request.model_dump(exclude_none=True)
        
        # Extract category from metadata for backwards compatibility
        if "metadata" in entry_data and "category" in entry_data["metadata"]:
            entry_data["category"] = entry_data["metadata"]["category"]
        
        # Initialize Firebase MCP
        firebase_mcp = FirebaseMCP()
        
        # Create entry
        result = await firebase_mcp.create_entry(entry_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to create entry")
            )
        
        logger.info(f"✅ Created entry: {result['entry_id']}")
        
        return EntryResponse(
            success=True,
            entry_id=result["entry_id"],
            entry=result["entry"],
            message="Entry created successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/entries/{entry_id}", response_model=EntryResponse)
async def get_entry(entry_id: str):
    """
    Get a single KB entry by ID.
    """
    try:
        logger.info(f"📖 Fetching entry: {entry_id}")
        
        # Initialize Firebase MCP
        firebase_mcp = FirebaseMCP()
        
        # Get entry
        result = await firebase_mcp.get_entry(entry_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get("error", "Entry not found")
            )
        
        return EntryResponse(
            success=True,
            entry_id=entry_id,
            entry=result["entry"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching entry {entry_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/entries", response_model=ListEntriesResponse)
async def list_entries(
    entry_type: Optional[str] = None,
    category: Optional[str] = None,
    archived: Optional[bool] = False,
    limit: Optional[int] = None
):
    """
    List KB entries with optional filters.
    
    Query parameters:
    - type: Filter by entry type
    - category: Filter by category
    - archived: Include archived entries (default: false)
    - limit: Maximum number of entries to return
    """
    try:
        logger.info("📋 Listing KB entries")
        
        # Build filters
        filters = {}
        if entry_type:
            filters["type"] = entry_type
        if category:
            filters["category"] = category
        if archived is not None:
            filters["archived"] = archived
        
        # Initialize Firebase MCP
        firebase_mcp = FirebaseMCP()
        
        # List entries
        result = await firebase_mcp.list_entries(filters=filters, limit=limit)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to list entries")
            )
        
        logger.info(f"✅ Found {result['count']} entries")
        
        return ListEntriesResponse(
            success=True,
            entries=result["entries"],
            count=result["count"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing entries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/entries/{entry_id}", response_model=EntryResponse)
async def update_entry(entry_id: str, request: UpdateEntryRequest):
    """
    Update an existing KB entry.
    
    Note: After updating, you should re-sync to update the vector database
    """
    try:
        logger.info(f"✏️ Updating entry: {entry_id}")
        
        # Prepare update data
        update_data = request.model_dump(exclude_none=True)
        
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )
        
        # Initialize Firebase MCP
        firebase_mcp = FirebaseMCP()
        
        # Update entry
        result = await firebase_mcp.update_entry(entry_id, update_data)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update entry")
            )
        
        logger.info(f"✅ Updated entry: {entry_id}")
        
        return EntryResponse(
            success=True,
            entry_id=entry_id,
            message="Entry updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error updating entry {entry_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: str):
    """
    Delete a KB entry (hard delete).
    
    This will:
    1. Delete from Firebase
    2. Delete from vector database
    """
    try:
        logger.info(f"🗑️ Deleting entry: {entry_id}")
        
        # Initialize MCPs
        firebase_mcp = FirebaseMCP()
        sync_mcp = VectorSyncMCP()
        
        # Delete from vector database first
        await sync_mcp.unsync_entry(entry_id)
        
        # Delete from Firebase
        result = await firebase_mcp.delete_entry(entry_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to delete entry")
            )
        
        logger.info(f"✅ Deleted entry: {entry_id}")
        
        return {
            "success": True,
            "entry_id": entry_id,
            "message": "Entry deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting entry {entry_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/entries/{entry_id}/archive")
async def archive_entry(entry_id: str):
    """
    Archive a KB entry (soft delete).
    
    This will:
    1. Mark as archived in Firebase
    2. Remove from vector database (archived entries not searchable)
    """
    try:
        logger.info(f"📦 Archiving entry: {entry_id}")
        
        # Initialize MCPs
        firebase_mcp = FirebaseMCP()
        sync_mcp = VectorSyncMCP()
        
        # Archive in Firebase
        result = await firebase_mcp.archive_entry(entry_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to archive entry")
            )
        
        # Remove from vector database
        await sync_mcp.unsync_entry(entry_id)
        
        logger.info(f"✅ Archived entry: {entry_id}")
        
        return {
            "success": True,
            "entry_id": entry_id,
            "message": "Entry archived successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error archiving entry {entry_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# VECTOR SYNC ENDPOINT
# ============================================================================

@router.post("/entries/{entry_id}/sync", response_model=SyncResponse)
async def sync_entry(entry_id: str):
    """
    Sync a KB entry to vector database.
    
    This endpoint:
    1. Fetches entry from Firebase
    2. Prepares content for embedding
    3. Stores in AstraDB with vector
    4. Updates Firebase sync status
    """
    try:
        logger.info(f"🔄 Starting sync for entry: {entry_id}")
        
        # Initialize Vector Sync MCP
        sync_mcp = VectorSyncMCP()
        
        # Sync entry
        result = await sync_mcp.sync_entry_to_vector(entry_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to sync entry")
            )
        
        logger.info(f"✅ Synced entry: {entry_id}")
        
        return SyncResponse(
            success=True,
            message=result.get("message", "Entry synced successfully"),
            entry_id=entry_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error syncing entry {entry_id}: {e}", exc_info=True)
        return SyncResponse(
            success=False,
            message="Failed to sync entry",
            entry_id=entry_id,
            error=str(e)
        )


# ============================================================================
# ASTRADB VIEWING & MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("/vectors")
async def list_vector_entries(limit: int = 50):
    """
    List all entries in vector database (for admin viewing).
    
    Args:
        limit: Maximum number of entries to return (default: 50)
    
    Returns:
        {
            "success": True,
            "entries": [
                {
                    "entry_id": "abc123",
                    "title": "...",
                    "content_preview": "...",
                    "metadata": {...}
                }
            ],
            "count": 25
        }
    """
    try:
        logger.info(f"📋 Listing vector entries (limit: {limit})")
        
        # Initialize AstraDB MCP
        astra_mcp = AstraDBMCP()
        
        # List vectors
        result = await astra_mcp.list_vectors(limit=limit)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to list vector entries")
            )
        
        logger.info(f"✅ Listed {result['count']} vector entries")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error listing vector entries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/vectors/{entry_id}")
async def delete_vector_entry(entry_id: str):
    """
    Delete vector(s) from AstraDB AND update Firebase status to "pending".
    
    Handles both:
    - Old single-vector entries (entry_id = Firebase ID)
    - New chunked entries (entry_id might be chunk_id, extract parent)
    
    This allows the entry to be re-synced later if needed.
    
    Args:
        entry_id: Document ID (could be parent entry or chunk ID)
    
    Returns:
        {
            "success": True,
            "entry_id": "abc123",
            "message": "Vector deleted and Firebase status updated to pending"
        }
    """
    try:
        logger.info(f"🗑️ Deleting vector(s) for: {entry_id}")
        
        # Initialize MCPs
        astra_mcp = AstraDBMCP()
        firebase_mcp = FirebaseMCP()
        
        # Extract parent entry ID if this is a chunk
        # Chunk IDs follow pattern: parent_id_chunk_N
        parent_entry_id = entry_id
        if "_chunk_" in entry_id:
            parent_entry_id = entry_id.rsplit("_chunk_", 1)[0]
            logger.info(f"📦 Detected chunk, parent entry: {parent_entry_id}")
        
        # Delete ALL vectors for this entry (handles both single and chunked)
        result = await astra_mcp.delete_vector(parent_entry_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to delete vector")
            )
        
        logger.info(f"✅ Deleted {result.get('deleted_count', 0)} vector(s)")
        
        # Update Firebase entry status to "pending" using parent ID
        try:
            await firebase_mcp.update_entry(parent_entry_id, {
                "vectorStatus": "pending",
                "lastSyncedAt": None,
                "chunksCreated": None
            })
            logger.info(f"✅ Updated Firebase status to pending: {parent_entry_id}")
        except Exception as e:
            logger.warning(f"⚠️ Could not update Firebase status (entry may not exist): {e}")
        
        return {
            "success": True,
            "entry_id": parent_entry_id,
            "chunks_deleted": result.get("deleted_count", 0),
            "message": f"Deleted {result.get('deleted_count', 0)} vector(s) and updated Firebase status to pending"
        }
        
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error deleting vector {entry_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/stats/vectors")
async def get_vector_stats():
    """
    Get vector database statistics.
    
    Returns:
        {
            "success": True,
            "total_vectors": 150,
            "collection": "kb_entries"
        }
    """
    try:
        logger.info("📊 Getting vector stats")
        
        # Initialize AstraDB MCP
        astra_mcp = AstraDBMCP()
        
        # Get stats
        result = await astra_mcp.get_vector_stats()
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get vector stats")
            )
        
        logger.info(f"✅ Vector stats retrieved: {result['total_vectors']} vectors")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting vector stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# ============================================================================
# DOCUMENT UPLOAD ENDPOINTS
# ============================================================================

@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    entry_type: str = Form(...),
    userType: str = Form(...),
    product: str = Form(...),
    category: str = Form(...),
    tags: str = Form(default=""),
    subcategory: str = Form(default=""),
    auto_sync: bool = Form(default=True)
):
    """
    Upload a document (DOCX or PDF) and create a KB entry.
    
    This endpoint:
    1. Extracts text and structure from the document
    2. Uses LLM to analyze and improve structure
    3. Builds a KB entry in the same format as template entries
    4. Saves to Firebase
    5. Optionally syncs to vector database
    
    Form fields:
    - file: The document file (DOCX or PDF)
    - title: Entry title
    - entry_type: Type of entry (how_to, definition, error)
    - userType: internal or customer
    - product: Product name
    - category: Category
    - tags: Comma-separated tags
    - subcategory: Optional subcategory
    - auto_sync: Whether to automatically sync to vector DB (default: true)
    """
    import asyncio
    from src.document_processing import get_extractor, StructureAnalyzer, EntryBuilder
    
    try:
        logger.info(f"📤 Document upload started: {file.filename}")
        
        # Validate file type
        filename_lower = file.filename.lower()
        if not (filename_lower.endswith('.docx') or filename_lower.endswith('.pdf')):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only DOCX and PDF files are supported."
            )
        
        # Read file bytes
        file_bytes = await file.read()
        logger.info(f"📄 Read {len(file_bytes)} bytes from {file.filename}")
        
        # Step 1: Extract text and structure using appropriate extractor
        extractor = get_extractor(file.filename)
        extraction_result = await extractor.extract(file_bytes, file.filename)
        
        if not extraction_result.success:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to extract document: {extraction_result.error}"
            )
        
        logger.info(f"✅ Extracted {len(extraction_result.sections)} sections from document")
        
        # Step 2: Analyze structure with LLM
        analyzer = StructureAnalyzer()
        analysis_result = await analyzer.analyze(extraction_result, entry_type)
        
        if not analysis_result.success:
            logger.warning(f"⚠️ Structure analysis failed: {analysis_result.error}, proceeding with basic structure")
        
        # Step 3: Build KB entry
        builder = EntryBuilder()
        
        # Parse tags
        tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        
        user_metadata = {
            "title": title,
            "type": entry_type,
            "userType": userType,
            "product": product,
            "category": category,
            "subcategory": subcategory if subcategory else None,
            "tags": tags_list
        }
        
        entry_data = builder.build_entry(analysis_result, extraction_result, user_metadata)
        
        logger.info(f"✅ Built KB entry: {entry_data.get('title')}")
        
        # Step 4: Save to Firebase
        firebase_mcp = FirebaseMCP()
        create_result = await firebase_mcp.create_entry(entry_data)
        
        if not create_result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save entry: {create_result.get('error')}"
            )
        
        entry_id = create_result["entry_id"]
        logger.info(f"✅ Saved to Firebase: {entry_id}")
        
        # Step 5: Optionally sync to vector database
        sync_result = None
        if auto_sync:
            sync_mcp = VectorSyncMCP()
            sync_result = await sync_mcp.sync_entry_to_vector(entry_id)
            
            if sync_result["success"]:
                logger.info(f"✅ Synced to vector DB: {sync_result.get('chunks_created')} chunks")
            else:
                logger.warning(f"⚠️ Vector sync failed: {sync_result.get('error')}")
        
        return {
            "success": True,
            "entry_id": entry_id,
            "title": entry_data.get("title"),
            "sections_extracted": len(extraction_result.sections),
            "word_count": extraction_result.metadata.get("word_count"),
            "sync_status": sync_result if auto_sync else {"status": "pending", "message": "Auto-sync disabled"},
            "message": "Document processed and saved successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Document upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/documents/status/{entry_id}")
async def get_document_status(entry_id: str):
    """
    Get processing status for an uploaded document.
    
    Useful for async processing - check if document has been synced.
    """
    try:
        firebase_mcp = FirebaseMCP()
        result = await firebase_mcp.get_entry(entry_id)
        
        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Entry not found"
            )
        
        entry = result["entry"]
        
        return {
            "success": True,
            "entry_id": entry_id,
            "title": entry.get("title"),
            "vector_status": entry.get("vectorStatus", "unknown"),
            "chunks_created": entry.get("chunksCreated"),
            "sync_error": entry.get("syncError"),
            "source": entry.get("metadata", {}).get("source"),
            "original_filename": entry.get("metadata", {}).get("original_filename")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting document status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
