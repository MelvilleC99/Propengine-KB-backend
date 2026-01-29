"""Search Strategy - Handles search with progressive fallback logic

Extracted from orchestrator.py to keep logic modular.
"""

import logging
from typing import Dict, List, Optional, Tuple
from src.config.settings import settings
from src.query.vector_search import VectorSearch
from src.analytics.collectors import QueryMetricsCollector  # Updated import

logger = logging.getLogger(__name__)


class SearchStrategy:
    """Handles vector search with intelligent fallback strategy"""
    
    def __init__(self, vector_search: VectorSearch, metrics_collector: QueryMetricsCollector):
        """
        Initialize search strategy
        
        Args:
            vector_search: Vector search instance
            metrics_collector: Metrics collector instance
        """
        self.vector_search = vector_search
        self.metrics_collector = metrics_collector
        
        logger.info("✅ Search strategy initialized")
    
    async def search_with_fallback(
        self,
        query: str,
        query_type: str,
        user_type_filter: Optional[str],
        parent_retrieval_handler
    ) -> Tuple[List[Dict], List[str]]:
        """
        Search with progressive fallback strategy
        
        Strategy:
        1. Try with entry_type filter (most specific)
        2. If no results, remove entry_type filter
        3. If howto has no results, try error type
        4. If definition contains "error", try error type
        
        Args:
            query: Enhanced search query
            query_type: Classified query type (error/definition/howto)
            user_type_filter: Filter by user type (internal/external)
            parent_retrieval_handler: Handler for expanding parent documents
            
        Returns:
            Tuple of (results, search_attempts)
        """
        search_attempts = []
        cached_embeddings = None
        
        # Primary search with entry_type filter
        search_attempts.append(f"primary:{query_type}")
        results, cached_embeddings, search_stats = await self.vector_search.search(
            query=query,
            entry_type=query_type,
            user_type=user_type_filter,
            k=settings.MAX_SEARCH_RESULTS
        )
        
        # Record search execution
        if search_stats:
            self.metrics_collector.record_search_execution(
                filters=search_stats.get("filters_applied", {}),
                docs_scanned=search_stats.get("documents_requested", 0),
                docs_matched=search_stats.get("documents_matched", 0),
                docs_returned=search_stats.get("documents_returned", 0),
                similarity_threshold=search_stats.get("similarity_threshold", 0.7),
                embedding_time_ms=search_stats.get("embedding_time_ms", 0.0),
                search_time_ms=search_stats.get("search_time_ms", 0.0)
            )
        
        # === PARENT DOCUMENT RETRIEVAL ===
        # If results contain chunks from parent documents, fetch all sibling chunks
        if results:
            results = await parent_retrieval_handler.expand_parent_documents(
                results, query, cached_embeddings
            )
            search_attempts.append(f"parent_retrieval:expanded_to_{len(results)}")
        
        if results:
            return results, search_attempts
        
        # Fallback 1: Remove entry_type filter
        logger.info(f"No results for {query_type}, trying without entry_type filter")
        search_attempts.append("fallback:no_filter")
        results, _, search_stats = await self.vector_search.search(
            query=query,
            user_type=user_type_filter,
            k=settings.MAX_SEARCH_RESULTS,
            query_embeddings=cached_embeddings
        )
        
        # Expand parent documents for fallback results too
        if results:
            results = await parent_retrieval_handler.expand_parent_documents(
                results, query, cached_embeddings
            )
            search_attempts.append(f"parent_retrieval_fallback:expanded_to_{len(results)}")
            return results, search_attempts
        
        # Fallback 2: If howto, try error
        if query_type == "howto":
            logger.info("Trying error type as fallback for howto")
            search_attempts.append("fallback:error")
            results, _, search_stats = await self.vector_search.search(
                query=query,
                entry_type="error",
                user_type=user_type_filter,
                k=settings.MAX_SEARCH_RESULTS,
                query_embeddings=cached_embeddings
            )
        
        # Fallback 3: If definition contains "error", try error type
        if query_type == "definition" and "error" in query.lower():
            logger.info("Definition query contains 'error', trying error type")
            search_attempts.append("fallback:error_detected")
            results, _, search_stats = await self.vector_search.search(
                query=query,
                entry_type="error",
                user_type=user_type_filter,
                k=settings.MAX_SEARCH_RESULTS,
                query_embeddings=cached_embeddings
            )
        
        return results, search_attempts
