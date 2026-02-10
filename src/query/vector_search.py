"""Vector search functionality using AstraDB with connection pooling"""

import logging
import time
from typing import List, Dict, Optional, Any, Tuple
from langchain_astradb import AstraDBVectorStore
from langchain.schema import Document
from src.config.settings import settings
from src.database.astra_client import astradb_connection
from src.analytics.tracking import token_tracker  # Updated import

logger = logging.getLogger(__name__)

class VectorSearch:
    """Vector search with reused AstraDB connection"""
    
    # Normalize classifier output to match AstraDB storage format
    ENTRY_TYPE_MAP = {
        "howto": "how_to",      # Classifier outputs "howto", DB has "how_to"
        "error": "error",        # Already matches
        "definition": "definition",  # Already matches
        "workflow": "workflow"   # Already matches
    }
    
    def __init__(self):
        """Initialize vector search with singleton connection"""
        # Use the global singleton connection instead of creating new ones
        self.db_connection = astradb_connection
        logger.info("VectorSearch initialized with singleton connection")
    
    def get_vector_store(self) -> AstraDBVectorStore:
        """Get the reused vector store connection"""
        return self.db_connection.get_vector_store()
    
    async def search(
        self, 
        query: str, 
        entry_type: Optional[str] = None,
        user_type: Optional[str] = None, 
        k: int = 5,
        similarity_threshold: float = 0.5,  # Low threshold for retrieval - reranker handles precision
        additional_metadata_filter: Optional[Dict] = None,
        query_embeddings: Optional[List[float]] = None,  # New parameter for cached embeddings
        session_id: Optional[str] = None  # NEW: For cost tracking
    ) -> tuple[List[Dict], Optional[List[float]], Dict]:
        """
        Perform vector similarity search using reused connection
        
        Args:
            query: Search query string
            entry_type: Filter by entry type (definition, error, howto, etc.)
            user_type: Filter by user type (internal, external, both)
            k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            additional_metadata_filter: Additional metadata filters
            query_embeddings: Optional cached embeddings to reuse
            
        Returns:
            Tuple of (results, embeddings, search_stats)
        """
        start_time = time.time()
        
        try:
            vector_store = self.get_vector_store()
            embeddings_model = self.db_connection.get_embeddings()
            
            # Build metadata filter
            metadata_filter = {}
            
            # Add entry type filter if specified
            if entry_type:
                normalized_type = self.ENTRY_TYPE_MAP.get(entry_type.lower(), entry_type.lower())
                metadata_filter["entryType"] = normalized_type
                logger.info(f"Filtering by entry_type: {normalized_type}")
            
            # Add user type filter if specified
            if user_type and user_type.lower() != "both":
                metadata_filter["userType"] = user_type.lower()
                logger.info(f"Filtering by user_type: {user_type}")
            
            # Add any additional filters
            if additional_metadata_filter:
                metadata_filter.update(additional_metadata_filter)
                logger.info(f"Additional filters: {additional_metadata_filter}")
            
            # If no filters, set to None (AstraDB doesn't like empty dicts)
            if not metadata_filter:
                metadata_filter = None
                
            # Generate query embeddings if not provided (cache for reuse)
            embedding_tokens = 0
            if query_embeddings is None:
                embedding_start = time.time()
                # Use async embedding to avoid blocking the event loop for other users
                query_embeddings = await embeddings_model.aembed_query(query)
                embedding_time_ms = (time.time() - embedding_start) * 1000
                
                # Track embedding tokens (rough estimate: 1 token per 4 chars)
                embedding_tokens = len(query) // 4
                token_tracker.track_embedding_usage(
                    tokens=embedding_tokens,
                    model=settings.EMBEDDING_MODEL,
                    session_id=session_id,  # NOW PASSED FROM CALLER
                    operation="embedding"  # Changed to match cost_breakdown key
                )
                
                logger.info(f"Generated embeddings in {embedding_time_ms:.0f}ms ({embedding_tokens} tokens)")
            else:
                embedding_time_ms = 0
                logger.info("Using cached embeddings")
            
            # Request exact number of documents
            # No need to over-fetch - similarity threshold filters appropriately
            k_requested = k
            
            # Perform similarity search using cached embeddings
            search_start = time.time()
            if metadata_filter:
                docs_with_scores = vector_store.similarity_search_with_score_by_vector(
                    query_embeddings,
                    k=k_requested,
                    filter=metadata_filter
                )
            else:
                docs_with_scores = vector_store.similarity_search_with_score_by_vector(
                    query_embeddings, 
                    k=k_requested
                )
            search_time_ms = (time.time() - search_start) * 1000
            
            docs_matched = len(docs_with_scores)
            logger.info(f"AstraDB returned {docs_matched} results (requested {k_requested})")

            
            # Filter by similarity threshold (keep top K after filtering)
            filtered_docs = [
                (doc, score) for doc, score in docs_with_scores 
                if score >= similarity_threshold
            ][:k]  # Limit to K results after threshold filtering
            
            docs_returned = len(filtered_docs)
            
            logger.info(
                f"Found {docs_returned} results above threshold {similarity_threshold} "
                f"(filtered from {docs_matched} matched documents)"
            )
            
            # Process results
            results = []
            for doc, score in filtered_docs:
                # Extract entry_id (chunk ID) and parent_entry_id (Firebase KB entry ID)
                entry_id = None
                parent_entry_id = None
                
                if hasattr(doc, 'metadata') and doc.metadata:
                    # Chunk ID from AstraDB
                    entry_id = doc.metadata.get('_id') or doc.metadata.get('id')
                    
                    # Parent entry ID (Firebase KB entry ID)
                    parent_entry_id = doc.metadata.get('parent_entry_id')
                
                if not entry_id and hasattr(doc, 'id'):
                    entry_id = doc.id
                
                # DEBUG: Log what we're finding
                logger.debug(f"Document extraction: entry_id={entry_id}, parent_entry_id={parent_entry_id}")
                if not parent_entry_id:
                    logger.warning(f"⚠️ No parent_entry_id found! This chunk won't link to Firebase KB entry. Metadata keys: {list(doc.metadata.keys()) if hasattr(doc, 'metadata') and doc.metadata else 'None'}")
                
                result = {
                    "entry_id": entry_id,  # AstraDB chunk ID
                    "parent_entry_id": parent_entry_id,  # ← ADDED: Firebase KB entry ID
                    "content": self.extract_content(doc),
                    "metadata": doc.metadata if hasattr(doc, 'metadata') else {},
                    "entry_type": doc.metadata.get("entryType", "unknown") if hasattr(doc, 'metadata') else "unknown",
                    "user_type": doc.metadata.get("userType", "unknown") if hasattr(doc, 'metadata') else "unknown",
                    "similarity_score": score
                }
                results.append(result)
            
            # Build search stats for metrics
            total_time_ms = (time.time() - start_time) * 1000
            search_stats = {
                "filters_applied": metadata_filter,
                "documents_requested": k_requested,
                "documents_matched": docs_matched,
                "documents_returned": docs_returned,
                "embedding_time_ms": embedding_time_ms,
                "search_time_ms": search_time_ms,
                "total_time_ms": total_time_ms,
                "similarity_threshold": similarity_threshold
            }
            
            logger.info(f"✅ Search completed in {total_time_ms:.0f}ms")
            
            return results, query_embeddings, search_stats
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [], None, {}  # Return empty results, None embeddings, empty stats on error
    
    def extract_content(self, document: Document) -> str:
        """Extract content from document"""
        # Try page_content first (standard LangChain field)
        if hasattr(document, 'page_content') and document.page_content:
            return document.page_content
        
        # Try metadata content fields
        if hasattr(document, 'metadata') and document.metadata:
            if 'content' in document.metadata:
                return document.metadata['content']
            if 'text' in document.metadata:
                return document.metadata['text']
        
        logger.warning("Could not extract content from document")
        return ""
