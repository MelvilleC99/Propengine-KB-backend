"""Vector Sync Service - Orchestrates syncing between Firebase and AstraDB"""

from typing import Dict, Any, List
import logging
from src.services.firebase.server import FirebaseService
from src.services.astradb.server import AstraDBService
from src.services.vector_sync.chunking import chunk_entry, Chunk
from src.services.vector_sync.document_chunking import chunk_document, chunk_large_document, is_document_entry

logger = logging.getLogger(__name__)


class VectorSyncService:
    """
    MCP Server for vector sync orchestration.
    Coordinates between Firebase and AstraDB to sync KB entries.
    """

    # Allowed values for the filterable metadata fields. The search side filters on
    # these exact values, so anything outside the set could never be retrieved —
    # they are validated/coerced on write in _prepare_chunk_metadata.
    VALID_USER_TYPES = {"internal", "external"}
    VALID_ENTRY_TYPES = {"how_to", "workflow", "definition", "error"}

    def __init__(self):
        """Initialize Vector Sync MCP with Firebase and AstraDB MCPs"""
        self.firebase = FirebaseService()
        self.astradb = AstraDBService()
        logger.info("✅ Vector Sync MCP initialized")
    
    async def sync_entry_to_vector(self, entry_id: str) -> Dict[str, Any]:
        """
        Sync a single KB entry from Firebase to AstraDB with intelligent chunking.
        
        This is the main sync operation that:
        1. Fetches entry from Firebase
        2. Chunks content based on entry type
        3. Stores multiple vectors (one per chunk) in AstraDB
        4. Updates Firebase sync status
        
        Args:
            entry_id: Document ID to sync
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123",
                "chunks_created": 4,
                "message": "Synced successfully"
            }
        """
        try:
            logger.info(f"🔄 Starting sync for entry: {entry_id}")
            
            # 1. Get entry from Firebase
            firebase_result = await self.firebase.get_entry(entry_id)
            
            if not firebase_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to get entry from Firebase: {firebase_result.get('error')}"
                }
            
            entry = firebase_result["entry"]
            logger.info(f"📄 Retrieved entry from Firebase: {entry.get('title', 'Untitled')}")
            
            # 2. Chunk the entry - use appropriate chunker based on source
            if is_document_entry(entry):
                # Document upload - use document chunking
                word_count = entry.get("metadata", {}).get("word_count", 0)
                if word_count > 3000:  # Large document threshold
                    chunks = chunk_large_document(entry)
                    logger.info(f"🧩 Created {len(chunks)} chunks for large document")
                else:
                    chunks = chunk_document(entry)
                    logger.info(f"🧩 Created {len(chunks)} chunks for document")
            else:
                # Template-based entry - use original chunking
                chunks = chunk_entry(entry)
                logger.info(f"🧩 Created {len(chunks)} chunks for entry type: {entry.get('type')}")
            
            if not chunks:
                return {
                    "success": False,
                    "error": "No chunks created - entry may be empty"
                }
            
            # 3. Store each chunk as a separate vector in AstraDB
            chunks_stored = 0
            for chunk in chunks:
                # Generate chunk ID: entry_id_chunk_N
                chunk_id = f"{entry_id}_chunk_{chunk.chunk_index}"
                
                # Prepare metadata for this chunk
                chunk_metadata = self._prepare_chunk_metadata(entry, chunk)
                
                # Store vector
                vector_result = await self.astradb.store_vector(
                    entry_id=chunk_id,
                    content=chunk.content,
                    metadata=chunk_metadata
                )
                
                if not vector_result["success"]:
                    logger.error(f"❌ Failed to store chunk {chunk.chunk_index}: {vector_result.get('error')}")
                    # Continue storing other chunks even if one fails
                    continue
                
                chunks_stored += 1
                logger.info(f"✅ Stored chunk {chunk.chunk_index + 1}/{len(chunks)}: {chunk.section_type}")
            
            # 4. Check if all chunks were stored
            if chunks_stored == 0:
                # Update Firebase with failed status
                await self.firebase.update_entry(entry_id, {
                    "vectorStatus": "failed",
                    "syncError": "Failed to store any chunks"
                })
                
                return {
                    "success": False,
                    "error": "Failed to store any chunks in AstraDB"
                }
            
            all_stored = chunks_stored == len(chunks)
            logger.info(f"✅ Stored {chunks_stored}/{len(chunks)} chunks in AstraDB")

            # 5. Update Firebase sync status — mark "partial" (not "synced") when some
            #    chunks failed, so an entry that is missing content isn't silently shown
            #    as fully synced. "partial" entries are searchable but incomplete.
            await self.firebase.update_entry(entry_id, {
                "vectorStatus": "synced" if all_stored else "partial",
                "lastSyncedAt": None,  # Firestore will auto-set server timestamp
                "syncError": None if all_stored else f"Only {chunks_stored}/{len(chunks)} chunks stored",
                "chunksCreated": chunks_stored
            })

            if all_stored:
                logger.info(f"✅ Successfully synced entry: {entry_id}")
            else:
                logger.warning(f"⚠️ Partial sync for {entry_id}: {chunks_stored}/{len(chunks)} chunks stored")

            return {
                "success": True,
                "entry_id": entry_id,
                "chunks_created": chunks_stored,
                "total_chunks": len(chunks),
                "status": "synced" if all_stored else "partial",
                "message": (f"Entry synced to vector database successfully ({chunks_stored} chunks)"
                            if all_stored
                            else f"Entry partially synced ({chunks_stored}/{len(chunks)} chunks) — re-sync recommended")
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to sync entry {entry_id}: {e}")
            
            # Try to update Firebase with error status
            try:
                await self.firebase.update_entry(entry_id, {
                    "vectorStatus": "failed",
                    "syncError": str(e)
                })
            except Exception as update_error:
                logger.warning(f"Could not update Firebase error status for {entry_id}: {update_error}")
            
            return {
                "success": False,
                "error": str(e)
            }
    
    async def resync_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Re-sync an entry (delete old vector and create new one).
        
        Args:
            entry_id: Document ID to re-sync
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123",
                "message": "Re-synced successfully"
            }
        """
        try:
            logger.info(f"🔄 Re-syncing entry: {entry_id}")
            
            # Delete old vector
            delete_result = await self.astradb.delete_vector(entry_id)
            
            if delete_result["success"]:
                logger.info(f"🗑️ Deleted old vector")
            
            # Sync new vector
            result = await self.sync_entry_to_vector(entry_id)
            
            if result["success"]:
                result["message"] = "Entry re-synced successfully"
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to re-sync entry {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def unsync_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Remove entry from vector database (but keep in Firebase).
        
        Args:
            entry_id: Document ID to unsync
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123"
            }
        """
        try:
            # Delete vector from AstraDB
            vector_result = await self.astradb.delete_vector(entry_id)
            
            if not vector_result["success"]:
                return vector_result
            
            # Update Firebase status
            await self.firebase.update_entry(entry_id, {
                "vectorStatus": "pending",
                "lastSyncedAt": None
            })
            
            logger.info(f"✅ Unsynced entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id,
                "message": "Entry removed from vector database"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to unsync entry {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _prepare_chunk_metadata(self, entry: Dict[str, Any], chunk: Chunk) -> Dict[str, Any]:
        """
        Prepare metadata for chunk storage in vector DB.
        Combines entry metadata with chunk-specific information.
        
        Args:
            entry: Original KB entry
            chunk: Chunk object
            
        Returns:
            Metadata dictionary for vector storage
        """
        # Start with base metadata from chunk
        metadata = {
            **chunk.metadata,
            # Add chunk-specific fields
            "parent_entry_id": chunk.parent_id,
            "parent_title": chunk.parent_title,
            "chunk_index": chunk.chunk_index,
            "total_chunks": chunk.total_chunks,
            "section_type": chunk.section_type,
            # Add dates
            "createdAt": entry.get("createdAt"),
            "lastSyncedAt": entry.get("lastSyncedAt")
        }
        
        # Flatten context into individual fields (AstraDB doesn't support nested objects)
        if chunk.context:
            metadata["context_position"] = chunk.context.get("position", "")
            metadata["context_section_name"] = chunk.context.get("section_name", "")
            metadata["context_previous_section"] = chunk.context.get("previous_section", "")
            metadata["context_previous_summary"] = chunk.context.get("previous_summary", "")
            metadata["context_next_section"] = chunk.context.get("next_section", "")
            metadata["context_next_summary"] = chunk.context.get("next_summary", "")
            # related_chunks is an array - keep it
            if related_chunks := chunk.context.get("related_chunks"):
                metadata["context_related_chunks"] = related_chunks

        # Validate & normalize the filterable fields. This is the single point every
        # chunk passes through before being written to AstraDB, so enforcing the schema
        # here guarantees the vector DB only ever contains clean, queryable values —
        # regardless of how the frontend supplied them.

        # userType: must be one of the known audiences; lowercase; default to the safe
        # "internal" (never accidentally expose internal content to customers).
        user_type = str(metadata.get("userType") or "internal").lower()
        if user_type not in self.VALID_USER_TYPES:
            logger.warning(
                f"⚠️ Invalid userType '{user_type}' for {chunk.parent_id} — defaulting to 'internal'"
            )
            user_type = "internal"
        metadata["userType"] = user_type

        # entryType: lowercase to match the search-side filter; warn (don't drop) if it's
        # an unrecognized type so it surfaces in logs without blocking the sync.
        entry_type = str(metadata.get("entryType") or "").lower()
        if entry_type and entry_type not in self.VALID_ENTRY_TYPES:
            logger.warning(f"⚠️ Unrecognized entryType '{entry_type}' for {chunk.parent_id}")
        metadata["entryType"] = entry_type

        # category: never store None (that would make the entry invisible to category
        # filtering). Read from either the top-level or nested location, else default.
        if not metadata.get("category"):
            metadata["category"] = (
                entry.get("category")
                or entry.get("metadata", {}).get("category")
                or "general"
            )

        return metadata
