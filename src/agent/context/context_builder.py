"""Context Building Module

Extracts and formats contexts from search results for LLM consumption.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds context from search results"""
    
    @staticmethod
    def extract_contexts(results: List[Dict], query: str, max_contexts: int = 10) -> List[str]:
        """
        Extract key excerpts from search results
        
        Args:
            results: List of search result dictionaries
            query: Original user query for relevance extraction
            max_contexts: Maximum number of contexts to return
            
        Returns:
            List of context strings
        """
        contexts = []
        
        for r in results[:max_contexts]:
            content = r.get("content", "")
            
            # Use full content - don't truncate!
            # The LLM needs complete information to answer accurately
            contexts.append(content)
        
        logger.debug(f"Extracted {len(contexts)} contexts from {len(results)} results")
        return contexts

    @staticmethod
    def format_contexts_with_sources(results: List[Dict], max_contexts: int = 3) -> str:
        """
        Format contexts with source attribution for LLM

        This creates a rich, contextualized view of KB content that includes:
        - Source titles and confidence scores
        - Entry types (how_to, error, definition)
        - Related documents for follow-up awareness
        - Clear visual separation

        Args:
            results: List of search result dictionaries with metadata
            max_contexts: Maximum number of contexts to include (default: 3 for LLM)

        Returns:
            Formatted string with source attribution
        """
        if not results:
            return "No relevant information found in knowledge base."

        formatted_parts = []

        for i, r in enumerate(results[:max_contexts], 1):
            content = r.get("content", "")
            metadata = r.get("metadata", {})

            # Extract source information
            title = (
                metadata.get("parent_title") or
                metadata.get("title") or
                metadata.get("term") or
                metadata.get("issue_title") or
                "Untitled Entry"
            )

            entry_type = r.get("entry_type", "unknown")
            confidence = r.get("similarity_score", 0.0)
            related_docs = metadata.get("related_documents", [])

            # Format source header
            source_header = f"📄 Source {i}: {title}"
            type_badge = f"[{entry_type.upper()}]"
            confidence_badge = f"(confidence: {confidence:.2f})"

            # Build formatted section
            formatted_section = [
                f"{source_header} {type_badge} {confidence_badge}",
                "-" * 60,
                content
            ]

            # Add related documents if available
            if related_docs:
                related_str = ", ".join(related_docs[:5])  # Limit to 5
                formatted_section.append(f"\n📌 Related Topics: {related_str}")

            formatted_parts.append("\n".join(formatted_section))

        logger.info(f"Formatted {len(formatted_parts)} contexts with source attribution")
        return "\n\n" + "="*60 + "\n\n".join(formatted_parts)

    @staticmethod
    def build_sources(results: List[Dict]) -> List[Dict]:
        """
        Build source metadata from search results
        
        Args:
            results: List of search result dictionaries (from vector_search)
            
        Returns:
            List of source metadata dictionaries with entry_id and parent_entry_id
        """
        sources = []
        
        for r in results:
            # Try to get title from multiple places
            # AstraDB stores it as parent_title in metadata
            metadata = r.get("metadata", {})
            title = (
                metadata.get("parent_title") or  # ← PRIMARY: This is where title is stored in AstraDB
                metadata.get("title") or 
                metadata.get("term") or  # For definitions
                metadata.get("issue_title") or  # For errors
                r.get("title") or  # Sometimes it's at root level
                "Untitled Entry"
            )
            
            # Use rerank_score if available, otherwise raw similarity_score
            confidence = r.get("rerank_score", r.get("similarity_score", 0.0))

            source = {
                "entry_id": r.get("entry_id"),  # AstraDB chunk ID
                "parent_entry_id": r.get("parent_entry_id"),  # Firebase KB entry ID
                "title": title,
                "section": r.get("entry_type", "unknown"),
                "confidence": confidence,
                "content_preview": r.get("content", "")[:200] + "..." if len(r.get("content", "")) > 200 else r.get("content", ""),
                "metadata": metadata,
                "entry_type": r.get("entry_type", ""),
                "user_type": r.get("user_type", ""),
                "similarity_score": r.get("similarity_score", 0.0),
                "rerank_score": r.get("rerank_score")
            }
            sources.append(source)
        
        logger.debug(f"Built {len(sources)} source metadata entries")
        return sources
    
    @staticmethod
    def calculate_best_confidence(results: List[Dict]) -> float:
        """
        Calculate best confidence score from results
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            Best similarity score (0.0-1.0)
        """
        if not results:
            return 0.0
        
        # Use rerank_score if available (post-reranker), otherwise fall back to similarity_score
        best_score = max([r.get("rerank_score", r.get("similarity_score", 0.0)) for r in results])
        logger.debug(f"Best confidence score: {best_score:.2f}")
        return best_score
