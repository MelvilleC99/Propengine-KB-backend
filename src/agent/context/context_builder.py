"""Context Building Module

Extracts and formats contexts from search results for LLM consumption.
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds context from search results"""
    
    @staticmethod
    def extract_contexts(results: List[Dict], query: str, max_contexts: int = 3) -> List[str]:
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
        query_words = query.lower().split()
        
        for r in results[:max_contexts]:
            content = r.get("content", "")
            
            # Extract key excerpt (max 150 chars) instead of full content
            if len(content) > 150:
                # Find sentences containing query keywords
                sentences = content.split('.')
                relevant_sentences = []
                
                for sentence in sentences:
                    if any(word in sentence.lower() for word in query_words):
                        relevant_sentences.append(sentence.strip())
                        if len(' '.join(relevant_sentences)) > 100:
                            break
                
                if relevant_sentences:
                    excerpt = '. '.join(relevant_sentences) + '.'
                else:
                    excerpt = content[:150] + "..."
            else:
                excerpt = content
            
            contexts.append(excerpt)
        
        logger.debug(f"Extracted {len(contexts)} contexts from {len(results)} results")
        return contexts
    
    @staticmethod
    def build_sources(results: List[Dict]) -> List[Dict]:
        """
        Build source metadata from search results
        
        Args:
            results: List of search result dictionaries
            
        Returns:
            List of source metadata dictionaries
        """
        sources = []
        
        for r in results:
            source = {
                "title": r.get("metadata", {}).get("title", "Untitled Entry"),
                "section": r.get("entry_type", "unknown"),
                "confidence": r.get("similarity_score", 0.0),
                "content_preview": r.get("content", "")[:200] + "..." if len(r.get("content", "")) > 200 else r.get("content", ""),
                "metadata": r.get("metadata", {}),
                "entry_type": r.get("entry_type", ""),
                "user_type": r.get("user_type", ""),
                "similarity_score": r.get("similarity_score", 0.0)
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
        
        best_score = max([r.get("similarity_score", 0.0) for r in results])
        logger.debug(f"Best confidence score: {best_score:.2f}")
        return best_score
