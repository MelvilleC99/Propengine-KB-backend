"""Vector search functionality using AstraDB with connection pooling"""

import logging
from typing import List, Dict, Optional, Any
from langchain_astradb import AstraDBVectorStore
from langchain.schema import Document
from src.config.settings import settings
from src.database.astra_client import astradb_connection

logger = logging.getLogger(__name__)

class VectorSearch:
    """Vector search with reused AstraDB connection"""
    
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
    ) -> List[Dict]:
        """
        Perform vector similarity search using reused connection
        
        Args:
            query: Search query string
            entry_type: Filter by entry type (definition, error, howto, etc.)
            user_type: Filter by user type (internal, external, both)
            k: Number of results to return
            similarity_threshold: Minimum similarity score
            additional_metadata_filter: Additional filters to apply
        
        Returns:
            List of search results with metadata and similarity scores
        """
        try:
            # Use the singleton vector store instead of creating new one
            vector_store = self.get_vector_store()
            
            # Get embeddings (either provided or generate once)
            if query_embeddings is None:
                # Generate embeddings once
                embeddings_model = self.db_connection.get_embeddings()
                query_embeddings = await embeddings_model.aembed_query(query)
                logger.info(f"Generated embeddings for query: {query[:50]}...")
            else:
                logger.info(f"Reusing cached embeddings for query: {query[:50]}...")
            
            # Build metadata filter
            metadata_filter = {}
            
            # Filter by entry type if specified  
            if entry_type:
                metadata_filter["entryType"] = entry_type
            
            # Filter by user type if specified (internal, external, both)
            if user_type:
                metadata_filter["userType"] = user_type
            
            # Add any additional metadata filters
            if additional_metadata_filter:
                metadata_filter.update(additional_metadata_filter)
            
            logger.info(f"Searching with metadata filter: {metadata_filter}")
            
            # Perform similarity search using cached embeddings
            if metadata_filter:
                docs_with_scores = vector_store.similarity_search_with_score_by_vector(
                    query_embeddings,
                    k=k,
                    filter=metadata_filter
                )
            else:
                docs_with_scores = vector_store.similarity_search_with_score_by_vector(
                    query_embeddings, 
                    k=k
                )
            
            # Filter by similarity threshold
            filtered_docs = [(doc, score) for doc, score in docs_with_scores if score >= similarity_threshold]
            
            logger.info(f"Found {len(filtered_docs)} results above threshold {similarity_threshold}")
            
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
            
            return results, query_embeddings  # Return embeddings for caching
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return [], None  # Return empty results and None for embeddings on error
    
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
