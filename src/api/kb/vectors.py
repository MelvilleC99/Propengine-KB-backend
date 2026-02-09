"""KB Vector Sync and Management Operations"""

from fastapi import APIRouter, HTTPException, status
import logging

from src.services.firebase import FirebaseService
from src.services.vector_sync import VectorSyncService
from src.services.astradb import AstraDBService
from .models import SyncResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["kb-vectors"])


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
        logger.info(f"Starting sync for entry: {entry_id}")

        sync_mcp = VectorSyncService()
        result = await sync_mcp.sync_entry_to_vector(entry_id)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to sync entry")
            )

        logger.info(f"Synced entry: {entry_id}")

        return SyncResponse(
            success=True,
            message=result.get("message", "Entry synced successfully"),
            entry_id=entry_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error syncing entry {entry_id}: {e}", exc_info=True)
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
            "entries": [...],
            "count": 25
        }
    """
    try:
        logger.info(f"Listing vector entries (limit: {limit})")

        astra_mcp = AstraDBService()
        result = await astra_mcp.list_vectors(limit=limit)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to list vector entries")
            )

        logger.info(f"Listed {result['count']} vector entries")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing vector entries: {e}", exc_info=True)
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
    """
    try:
        logger.info(f"Deleting vector(s) for: {entry_id}")

        astra_mcp = AstraDBService()
        firebase_mcp = FirebaseService()

        # Extract parent entry ID if this is a chunk
        parent_entry_id = entry_id
        if "_chunk_" in entry_id:
            parent_entry_id = entry_id.rsplit("_chunk_", 1)[0]
            logger.info(f"Detected chunk, parent entry: {parent_entry_id}")

        # Delete ALL vectors for this entry
        result = await astra_mcp.delete_vector(parent_entry_id)

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to delete vector")
            )

        logger.info(f"Deleted {result.get('deleted_count', 0)} vector(s)")

        # Update Firebase entry status to "pending"
        try:
            await firebase_mcp.update_entry(parent_entry_id, {
                "vectorStatus": "pending",
                "lastSyncedAt": None,
                "chunksCreated": None
            })
            logger.info(f"Updated Firebase status to pending: {parent_entry_id}")
        except Exception as e:
            logger.warning(f"Could not update Firebase status (entry may not exist): {e}")

        return {
            "success": True,
            "entry_id": parent_entry_id,
            "chunks_deleted": result.get("deleted_count", 0),
            "message": f"Deleted {result.get('deleted_count', 0)} vector(s) and updated Firebase status to pending"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vector {entry_id}: {e}", exc_info=True)
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
        logger.info("Getting vector stats")

        astra_mcp = AstraDBService()
        result = await astra_mcp.get_vector_stats()

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to get vector stats")
            )

        logger.info(f"Vector stats retrieved: {result['total_vectors']} vectors")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vector stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
