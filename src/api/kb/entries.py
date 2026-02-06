"""KB Entry CRUD Operations"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional
import logging

from src.mcp.firebase import FirebaseMCP
from src.mcp.vector_sync import VectorSyncMCP
from .models import (
    CreateEntryRequest,
    UpdateEntryRequest,
    EntryResponse,
    ListEntriesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["kb-entries"])


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
        logger.info(f"Creating new KB entry: {request.title}")

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

        logger.info(f"Created entry: {result['entry_id']}")

        return EntryResponse(
            success=True,
            entry_id=result["entry_id"],
            entry=result["entry"],
            message="Entry created successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/entries/{entry_id}", response_model=EntryResponse)
async def get_entry(entry_id: str):
    """Get a single KB entry by ID."""
    try:
        logger.info(f"Fetching entry: {entry_id}")

        firebase_mcp = FirebaseMCP()
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
        logger.error(f"Error fetching entry {entry_id}: {e}", exc_info=True)
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
        logger.info("Listing KB entries")

        # Build filters
        filters = {}
        if entry_type:
            filters["type"] = entry_type
        if category:
            filters["category"] = category
        if archived is not None:
            filters["archived"] = archived

        firebase_mcp = FirebaseMCP()
        result = await firebase_mcp.list_entries(filters=filters, limit=limit)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to list entries")
            )

        logger.info(f"Found {result['count']} entries")

        return ListEntriesResponse(
            success=True,
            entries=result["entries"],
            count=result["count"]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing entries: {e}", exc_info=True)
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
        logger.info(f"Updating entry: {entry_id}")

        update_data = request.model_dump(exclude_none=True)

        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No fields to update"
            )

        firebase_mcp = FirebaseMCP()
        result = await firebase_mcp.update_entry(entry_id, update_data)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update entry")
            )

        logger.info(f"Updated entry: {entry_id}")

        return EntryResponse(
            success=True,
            entry_id=entry_id,
            message="Entry updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating entry {entry_id}: {e}", exc_info=True)
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
        logger.info(f"Deleting entry: {entry_id}")

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

        logger.info(f"Deleted entry: {entry_id}")

        return {
            "success": True,
            "entry_id": entry_id,
            "message": "Entry deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting entry {entry_id}: {e}", exc_info=True)
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
        logger.info(f"Archiving entry: {entry_id}")

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

        logger.info(f"Archived entry: {entry_id}")

        return {
            "success": True,
            "entry_id": entry_id,
            "message": "Entry archived successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving entry {entry_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
