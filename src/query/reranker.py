"""
Re-ranking system to improve search result quality
Reorders vector search results based on query-specific relevance
"""

import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

class SearchReranker:
    """
    Re-ranks vector search results for better relevance
    Uses keyword matching, query type analysis, and content scoring
    """
    
    def __init__(self):
        """Initialize re-ranking system"""
        # Define query type patterns for re-ranking
        self.query_patterns = {
            "error": [r"\berror\b", r"\bfail\b", r"\bnot work\b", r"\bbroken\b"],
            "how_to": [r"\bhow to\b", r"\bhow do\b", r"\bsteps\b", r"\bprocess\b"],
            "troubleshoot": [r"\bnot showing\b", r"\bmissing\b", r"\bcan't see\b"],
            "definition": [r"\bwhat is\b", r"\bwhat are\b", r"\bdefine\b"]
        }
        
        logger.info("✅ Search re-ranker initialized")
    
    def rerank_results(self, results: List[Dict], query: str, max_results: int = 3) -> List[Dict]:
        """
        Re-rank search results based on query relevance
        
        Args:
            results: Original vector search results
            query: User's query
            max_results: Maximum results to return
            
        Returns:
            List[Dict]: Re-ranked results
        """
        if not results:
            return results
        
        try:
            # Score each result
            scored_results = []
            query_type = self._detect_query_type(query)
            query_keywords = self._extract_keywords(query)
            
            for result in results:
                score = self._calculate_relevance_score(
                    result, query, query_type, query_keywords
                )
                result["rerank_score"] = score
                scored_results.append(result)
            
            # Sort by re-rank score (descending)
            reranked = sorted(scored_results, key=lambda x: x["rerank_score"], reverse=True)
            
            logger.info(f"Re-ranked {len(results)} results, query type: {query_type}")
            
            return reranked[:max_results]
            
        except Exception as e:
            logger.error(f"Re-ranking failed: {e}")
            return results[:max_results]  # Fallback to original order
    
    def _detect_query_type(self, query: str) -> str:
        """
        Detect the type of query for targeted re-ranking
        
        Args:
            query: User's query
            
        Returns:
            str: Detected query type
        """
        query_lower = query.lower()
        
        for query_type, patterns in self.query_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    return query_type
        
        return "general"
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract important keywords from query
        
        Args:
            query: User's query
            
        Returns:
            List[str]: Important keywords
        """
        # Remove common stop words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'but', 'and', 'or'}
        
        words = re.findall(r'\b\w+\b', query.lower())
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return keywords
    
    def _calculate_relevance_score(
        self, 
        result: Dict, 
        query: str, 
        query_type: str, 
        query_keywords: List[str]
    ) -> float:
        """
        Calculate relevance score for re-ranking
        
        Args:
            result: Search result to score
            query: Original query
            query_type: Detected query type
            query_keywords: Extracted keywords
            
        Returns:
            float: Relevance score (0.0 to 1.0)
        """
        # Start with original similarity score
        base_score = result.get("similarity_score", 0.0)
        
        content = result.get("content", "").lower()
        entry_type = result.get("entry_type", "unknown")
        title = result.get("metadata", {}).get("title", "").lower()
        
        # Boost score based on various factors
        score_boost = 0.0
        
        # 1. Query type matching
        if query_type == "error" and entry_type == "error":
            score_boost += 0.2
        elif query_type == "how_to" and entry_type == "howto":
            score_boost += 0.2
        elif query_type == "definition" and entry_type == "definition":
            score_boost += 0.2
        elif query_type == "troubleshoot" and any(word in content for word in ["fix", "solve", "troubleshoot"]):
            score_boost += 0.15
        
        # 2. Keyword density in content
        keyword_matches = sum(1 for keyword in query_keywords if keyword in content)
        if query_keywords:
            keyword_density = keyword_matches / len(query_keywords)
            score_boost += keyword_density * 0.1
        
        # 3. Title relevance (titles are usually more important)
        title_matches = sum(1 for keyword in query_keywords if keyword in title)
        if query_keywords and title_matches > 0:
            score_boost += (title_matches / len(query_keywords)) * 0.15
        
        # 4. Exact phrase matching
        query_phrases = self._extract_phrases(query.lower())
        for phrase in query_phrases:
            if phrase in content:
                score_boost += 0.1
        
        # 5. Content length penalty (prefer concise, relevant content)
        content_length = len(content.split())
        if content_length < 100:  # Short, focused content
            score_boost += 0.05
        elif content_length > 500:  # Very long content
            score_boost -= 0.05
        
        # Calculate final score (ensure it stays within 0.0-1.0 range)
        final_score = min(1.0, base_score + score_boost)
        
        return final_score
    
    def _extract_phrases(self, text: str) -> List[str]:
        """
        Extract meaningful phrases from text
        
        Args:
            text: Input text
            
        Returns:
            List[str]: Extracted phrases
        """
        # Simple phrase extraction (2-3 word combinations)
        words = text.split()
        phrases = []
        
        # Extract 2-word phrases
        for i in range(len(words) - 1):
            phrase = f"{words[i]} {words[i+1]}"
            if len(phrase) > 5:  # Skip very short phrases
                phrases.append(phrase)
        
        # Extract 3-word phrases for important concepts
        for i in range(len(words) - 2):
            phrase = f"{words[i]} {words[i+1]} {words[i+2]}"
            if len(phrase) > 8:  # Skip short 3-word phrases
                phrases.append(phrase)
        
        return phrases
    
    def get_rerank_explanation(self, result: Dict) -> str:
        """
        Get explanation of why result was ranked this way (for debugging)
        
        Args:
            result: Re-ranked result
            
        Returns:
            str: Explanation of ranking factors
        """
        original_score = result.get("similarity_score", 0.0)
        rerank_score = result.get("rerank_score", 0.0)
        boost = rerank_score - original_score
        
        explanation = f"Original: {original_score:.3f}, Re-ranked: {rerank_score:.3f}"
        
        if boost > 0:
            explanation += f" (+{boost:.3f} boost)"
        elif boost < 0:
            explanation += f" ({boost:.3f} penalty)"
        
        return explanation
