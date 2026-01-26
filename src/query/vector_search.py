"""Vector search functionality using AstraDB with connection pooling"""

import logging
import time
from typing import List, Dict, Optional, Any, Tuple
from langchain_astradb import AstraDBVectorStore
from langchain.schema import Document
from src.config.settings import settings
from src.database.astra_client import astradb_connection

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
        similarity_threshold: float = 0.7,
        additional_metadata_filter: Optional[Dict] = None,
        query_embeddings: Optional[List[float]] = None  # New parameter for cached embeddings
    ) -> tuple[List[Dict], Optional[List[float]], Dict]:
        """
        Perform vector similarity search using reused connection
        
        Args:
            query: Search query string
            entry_type: Filter by entry type (definition, error, howto, etc.)
            user_type: Filter by user type (internal, external, both)
            k: Number of results to return (will request k*3 to account for threshold filtering)
            similarity_threshold: Minimum similarity score
            additional_metadata_filter: Additional filters to apply
        
        Returns:
            Tuple of (results, embeddings, search_stats)
            - results: List of search results with metadata and similarity scores
            - embeddings: Query embeddings (for caching)
            - search_stats: Dict with documents_requested, documents_matched, documents_returned
        """
        try:
            # Start timing
            start_time = time.time()
            
            # Use the singleton vector store instead of creating new one
            vector_store = self.get_vector_store()
            
            # Get embeddings (either provided or generate once)
            if query_embeddings is None:
                embed_start = time.time()
                embeddings_model = self.db_connection.get_embeddings()
                query_embeddings = await embeddings_model.aembed_query(query)
                embedding_time_ms = (time.time() - embed_start) * 1000
                logger.info(f"Generated embeddings for query: {query[:50]}... ({embedding_time_ms:.0f}ms)")
            else:
                embedding_time_ms = 0
                logger.info(f"Reusing cached embeddings for query: {query[:50]}...")
            
            # Build metadata filter
            metadata_filter = {}
            
            # Filter by entry type if specified - normalize format to match DB
            if entry_type:
                # Map classifier output to DB format (e.g., "howto" -> "how_to")
                normalized_entry_type = self.ENTRY_TYPE_MAP.get(entry_type, entry_type)
                metadata_filter["entryType"] = normalized_entry_type
                logger.debug(f"Normalized entry_type: '{entry_type}' -> '{normalized_entry_type}'")
            
            # Filter by user type if specified (internal, external, both)
            if user_type:
                metadata_filter["userType"] = user_type
            
            # Add any additional metadata filters
            if additional_metadata_filter:
                metadata_filter.update(additional_metadata_filter)
            
            logger.info(f"Searching with metadata filter: {metadata_filter}")
            
            # REQUEST MORE DOCS to account for similarity threshold filtering
            # If we want K final results after threshold, request K*3 from DB
            # This ensures we get enough results even after filtering
            k_requested = k * 3
            
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
                result = {
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
    
    def clean_query(self, query: str) -> str:
        """Clean and optimize query for vector search"""
        # Remove common stop words that don't help with search
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'why', 'when', 'where'}
        words = query.lower().split()
        cleaned = ' '.join([w for w in words if w not in stop_words])
        return cleaned if cleaned else query
