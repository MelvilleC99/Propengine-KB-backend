"""Parent Document Retrieval - Expands chunks to full parent documents

Extracted from orchestrator.py to keep logic modular.
"""

import re
import logging
from typing import Dict, List, Optional
from src.query.vector_search import VectorSearch

logger = logging.getLogger(__name__)


class ParentDocumentRetrieval:
    """Handles intelligent expansion of search results to include parent document chunks"""
    
    def __init__(self, vector_search: VectorSearch):
        """
        Initialize parent document retrieval handler
        
        Args:
            vector_search: Vector search instance
        """
        self.vector_search = vector_search
        
        logger.info("✅ Parent document retrieval handler initialized")
    
    async def expand_parent_documents(
        self, 
        results: List[Dict], 
        query: str, 
        cached_embeddings: Optional[List[float]]
    ) -> List[Dict]:
        """
        Intelligently expand results to include parent document chunks.
        
        Only fetches full parent document when query indicates user wants
        comprehensive information (e.g., "how to", "complete guide", "all steps").
        For specific queries, returns only the relevant chunks found by search.
        
        Args:
            results: Initial search results
            query: Original query
            cached_embeddings: Cached query embeddings
            
        Returns:
            Expanded results (conditionally) or original results
        """
        if not results:
            return results
        
        # Check if query needs comprehensive context (full parent retrieval)
        needs_full_context = self.query_needs_full_context(query)
        
        if not needs_full_context:
            logger.info(f"📍 Query is specific, using only relevant chunks (no parent expansion)")
            return results
        
        # Query needs comprehensive context - proceed with parent retrieval
        logger.info(f"📚 Query needs comprehensive context, expanding parent documents")
        
        # Group results by parent_entry_id
        parents = {}
        non_parent_results = []
        
        for r in results:
            parent_id = r.get("metadata", {}).get("parent_entry_id")
            if parent_id:
                if parent_id not in parents:
                    parents[parent_id] = {
                        "chunks": [],
                        "total_chunks": r.get("metadata", {}).get("total_chunks", 0)
                    }
                parents[parent_id]["chunks"].append(r)
            else:
                # Not from a parent document (manual entry)
                non_parent_results.append(r)
        
        # If no parent documents found, return original results
        if not parents:
            return results
        
        logger.info(f"📚 Found {len(parents)} parent document(s) in results")
        
        # Fetch all chunks for each parent document
        all_chunks = []
        for parent_id, parent_data in parents.items():
            current_chunks = parent_data["chunks"]
            total_chunks = parent_data["total_chunks"]
            
            # If we already have all chunks, no need to fetch more
            if len(current_chunks) >= total_chunks:
                logger.info(f"✅ Already have all {total_chunks} chunks for parent {parent_id}")
                all_chunks.extend(current_chunks)
                continue
            
            # Fetch all chunks with this parent_id
            logger.info(f"🔍 Fetching all {total_chunks} chunks for parent {parent_id} (currently have {len(current_chunks)})")
            
            try:
                parent_results, _, _ = await self.vector_search.search(
                    query=query,
                    additional_metadata_filter={"parent_entry_id": parent_id},
                    k=total_chunks + 5,  # Add buffer in case total_chunks is inaccurate
                    similarity_threshold=0.0,  # Get all chunks regardless of similarity
                    query_embeddings=cached_embeddings  # Reuse embeddings for efficiency!
                )
                
                if parent_results:
                    logger.info(f"✅ Retrieved {len(parent_results)} chunks from parent {parent_id}")
                    all_chunks.extend(parent_results)
                else:
                    # Fallback to original chunks if fetch fails
                    logger.warning(f"⚠️ Failed to fetch parent chunks, using original {len(current_chunks)} chunks")
                    all_chunks.extend(current_chunks)
                    
            except Exception as e:
                logger.error(f"❌ Error fetching parent chunks: {e}")
                # Fallback to original chunks
                all_chunks.extend(current_chunks)
        
        # Add non-parent results (manual entries)
        all_chunks.extend(non_parent_results)
        
        # Remove duplicates by chunk ID
        seen_ids = set()
        unique_chunks = []
        for chunk in all_chunks:
            chunk_id = chunk.get("metadata", {}).get("_id") or chunk.get("entry_id")
            if chunk_id and chunk_id not in seen_ids:
                seen_ids.add(chunk_id)
                unique_chunks.append(chunk)
            elif not chunk_id:
                # No ID, include anyway
                unique_chunks.append(chunk)
        
        logger.info(f"🎯 Expanded from {len(results)} to {len(unique_chunks)} chunks using parent document retrieval")
        
        return unique_chunks
    
    def query_needs_full_context(self, query: str) -> bool:
        """
        Determine if query needs comprehensive context (full parent document)
        or just specific relevant chunks.
        
        Args:
            query: User query
            
        Returns:
            True if query needs full parent document, False for specific queries
        """
        query_lower = query.lower().strip()
        
        # Patterns indicating need for comprehensive/complete information
        comprehensive_patterns = [
            # Broad how-to queries
            r'\bhow\s+(do\s+i|to|can\s+i)\s+\w+',  # "how do I create", "how to create"
            r'\bwhat\s+(is\s+the|are\s+the)\s+steps',  # "what are the steps"
            
            # Completeness indicators
            r'\b(all|entire|complete|full|whole)\b',  # "all steps", "entire process"
            r'\bstep\s+by\s+step\b',  # "step by step"
            r'\bwalk\s+me\s+through\b',  # "walk me through"
            r'\bguide\b',  # "guide to"
            
            # Process/procedure queries
            r'\bprocess\b',  # "the process"
            r'\bprocedure\b',  # "the procedure"
            
            # Broad "how" without specifics
            r'^how\s+(do\s+i|to|can\s+i)\s+\w+\s*\??$',  # Short "how to X?" queries
        ]
        
        # Patterns indicating specific/targeted queries (DON'T expand)
        specific_patterns = [
            r'\bstep\s+\d+\b',  # "step 5", "step 10"
            r'\bwhat\s+(is|does|means?)\b',  # "what is X", "what does X mean"
            r'\berror\b',  # Error-related queries
            r'\bissue\b',  # Issue-related queries
            r'\bproblem\b',  # Problem-related queries
            r'\b(which|where|when)\b',  # Specific interrogatives
        ]
        
        # Check if query is specific (don't expand if specific)
        for pattern in specific_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"Query is specific (matched: {pattern})")
                return False
        
        # Check if query needs comprehensive context
        for pattern in comprehensive_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"Query needs comprehensive context (matched: {pattern})")
                return True
        
        # Default: for safety, don't expand unless explicitly matched
        # This prevents over-fetching for ambiguous queries
        logger.debug("Query doesn't match comprehensive patterns, staying specific")
        return False
