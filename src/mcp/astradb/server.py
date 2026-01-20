"""AstraDB MCP Server - Handles all vector database operations"""

from typing import Dict, Any, List, Optional
import logging
from src.database.connection import AstraDBConnection

logger = logging.getLogger(__name__)


class AstraDBMCP:
    """
    MCP Server for AstraDB vector operations.
    Provides tools for storing, searching, and managing vectors.
    """
    
    def __init__(self):
        """Initialize AstraDB MCP with existing connection"""
        self.astra = AstraDBConnection()
        self.vector_store = self.astra.get_vector_store()
        logger.info("✅ AstraDB MCP initialized")
    
    async def store_vector(
        self, 
        entry_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Store a document with its vector embedding in AstraDB.
        
        Args:
            entry_id: Unique document ID
            content: Text content to embed
            metadata: Document metadata
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123",
                "dimension": 1536
            }
        """
        try:
            # Add document to vector store (it will generate embedding automatically)
            self.vector_store.add_texts(
                texts=[content],
                metadatas=[metadata],
                ids=[entry_id]
            )
            
            logger.info(f"✅ Stored vector for entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id,
                "dimension": 1536  # text-embedding-3-large dimension
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to store vector for {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def update_vector(
        self, 
        entry_id: str,
        content: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update a vector in AstraDB (delete + recreate).
        
        Args:
            entry_id: Document ID
            content: Updated text content
            metadata: Updated metadata
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123"
            }
        """
        try:
            # Delete old vector
            await self.delete_vector(entry_id)
            
            # Store new vector
            result = await self.store_vector(entry_id, content, metadata)
            
            logger.info(f"✅ Updated vector for entry: {entry_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Failed to update vector for {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_vector(self, entry_id: str) -> Dict[str, Any]:
        """
        Delete vector(s) from AstraDB.
        Now handles both single vectors and chunked entries.
        
        For chunked entries, deletes all chunks matching parent_entry_id.
        For single entries, deletes the entry directly.
        
        Args:
            entry_id: Parent entry ID (will delete all chunks)
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123",
                "chunks_deleted": 4
            }
        """
        try:
            # Try to delete all chunks for this entry
            # This uses metadata filtering to find all chunks
            deleted_count = 0
            
            try:
                # Delete all vectors where parent_entry_id matches
                self.vector_store.delete(
                    filter={"parent_entry_id": entry_id}
                )
                deleted_count += 1
                logger.info(f"🗑️ Deleted chunk vectors for entry: {entry_id}")
            except Exception as chunk_error:
                logger.warning(f"No chunks found for {entry_id}, trying direct delete: {chunk_error}")
            
            # Also try direct deletion (for legacy single-vector entries)
            try:
                self.vector_store.delete(ids=[entry_id])
                deleted_count += 1
                logger.info(f"🗑️ Deleted direct vector for entry: {entry_id}")
            except Exception as direct_error:
                logger.warning(f"No direct vector found for {entry_id}: {direct_error}")
            
            if deleted_count == 0:
                logger.warning(f"⚠️ No vectors found to delete for entry: {entry_id}")
            else:
                logger.info(f"✅ Deleted vectors for entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id,
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete vector for {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_vectors(
        self,
        query: str,
        k: int = 5,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Search for similar vectors.
        
        Args:
            query: Search query text
            k: Number of results to return
            filter: Optional metadata filter
            score_threshold: Minimum similarity score (0-1)
            
        Returns:
            {
                "success": True,
                "results": [
                    {
                        "entry_id": "abc123",
                        "content": "...",
                        "score": 0.85,
                        "metadata": {...}
                    }
                ],
                "count": 3
            }
        """
        try:
            # Search with scores
            results = self.vector_store.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter or {}
            )
            
            # Filter by threshold and format results
            formatted_results = []
            for doc, score in results:
                if score >= score_threshold:
                    formatted_results.append({
                        "entry_id": doc.metadata.get("id", "unknown"),
                        "content": doc.page_content,
                        "score": float(score),
                        "metadata": doc.metadata
                    })
            
            logger.info(f"✅ Found {len(formatted_results)} results for query")
            
            return {
                "success": True,
                "results": formatted_results,
                "count": len(formatted_results)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to search vectors: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": [],
                "count": 0
            }
    
    async def list_vectors(self, limit: int = 50) -> Dict[str, Any]:
        """
        List all vectors in the database (for admin viewing).
        
        Args:
            limit: Maximum number of entries to return
            
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
            # Use LangChain's proper method to get documents with IDs
            # We need to search to get documents, but we want ALL documents
            # So we use a generic search with high k value
            from langchain_core.documents import Document
            
            # Get documents with scores (this returns tuples)
            results_with_ids = []
            
            # Try to get the underlying collection through the store's environment
            try:
                # Access the astra_env which has the collection
                collection = self.vector_store.astra_env.collection
                
                # Use find to get all documents with their IDs
                cursor = collection.find({}, projection={"*": 1}, limit=limit)
                
                for doc_dict in cursor:
                    results_with_ids.append(doc_dict)
                    
            except Exception as e:
                logger.warning(f"Could not access collection directly: {e}, falling back to search")
                # Fallback: use similarity_search and construct IDs from metadata
                results = self.vector_store.similarity_search("", k=limit)
                for doc in results:
                    # Try to construct ID from metadata
                    parent_id = doc.metadata.get("parent_entry_id", "unknown")
                    chunk_index = doc.metadata.get("chunk_index")
                    if chunk_index is not None:
                        doc_id = f"{parent_id}_chunk_{chunk_index}"
                    else:
                        doc_id = parent_id
                    
                    results_with_ids.append({
                        "_id": doc_id,
                        "content": doc.page_content,
                        **doc.metadata
                    })
            
            formatted_entries = []
            for doc_dict in results_with_ids:
                # Extract document ID and content
                doc_id = doc_dict.get("_id", "unknown")
                content = doc_dict.get("content", doc_dict.get("text", ""))
                
                # Get metadata - it's nested under 'metadata' key in AstraDB
                metadata = doc_dict.get("metadata", {})
                
                # Determine if this is a chunk
                is_chunk = "parent_entry_id" in metadata
                
                formatted_entries.append({
                    "entry_id": doc_id,
                    "title": metadata.get("parent_title") or metadata.get("title", "Untitled"),
                    "content_preview": content[:200] + "..." if len(content) > 200 else content,
                    "metadata": {
                        **metadata,
                        "is_chunk": is_chunk,
                        "chunk_section": metadata.get("section_type") if is_chunk else None,
                        "chunk_position": f"{metadata.get('chunk_index', 0) + 1}/{metadata.get('total_chunks', 1)}" if is_chunk else None
                    },
                    "vector_dimension": 1536
                })
            
            logger.info(f"✅ Listed {len(formatted_entries)} vector entries")
            
            return {
                "success": True,
                "entries": formatted_entries,
                "count": len(formatted_entries)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to list vectors: {e}")
            return {
                "success": False,
                "error": str(e),
                "entries": [],
                "count": 0
            }
    
    async def get_vector_stats(self) -> Dict[str, Any]:
        """
        Get statistics about vectors in the database.
        
        Returns:
            {
                "success": True,
                "total_vectors": 150,
                "collection": "kb_entries"
            }
        """
        try:
            # Get a sample to count (AstraDB doesn't have direct count)
            results = self.vector_store.similarity_search(
                query="test",
                k=10000  # Large number to get estimate
            )
            
            count = len(results)
            
            logger.info(f"✅ Vector stats: {count} vectors")
            
            return {
                "success": True,
                "total_vectors": count,
                "collection": "kb_entries"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get vector stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
