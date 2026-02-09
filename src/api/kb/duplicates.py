"""KB Duplicate Check Operations"""

from fastapi import APIRouter
from typing import Dict, List
import logging

from src.query.vector_search import VectorSearch
from src.services.firebase import FirebaseService
from .models import (
    DuplicateCheckRequest,
    DuplicateCheckResponse,
    SimilarEntry,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["kb-duplicates"])

# Similarity threshold for duplicate detection (higher than regular search)
SIMILARITY_THRESHOLD = 0.70


@router.post("/check-duplicates", response_model=DuplicateCheckResponse)
async def check_duplicates(request: DuplicateCheckRequest):
    """
    Check for duplicate or similar KB entries before creating a new entry.

    Uses vector similarity search to find semantically similar content.

    Args:
        request: Contains title, content, and type of the proposed entry

    Returns:
        - has_duplicates: True if similar entries found (similarity >= 0.70)
        - similar_entries: List of similar entries with scores and snippets

    Note: This endpoint fails gracefully - returns empty results on error
    to avoid blocking entry creation.
    """
    try:
        logger.info(f"Checking duplicates for: {request.title[:50]}...")

        # Use the content for similarity search
        vector_search = VectorSearch()

        # Search with same entry type filter
        results, _, stats = await vector_search.search(
            query=request.content,
            entry_type=request.type,  # Only compare same types
            k=10,  # Get more results to deduplicate chunks
            similarity_threshold=SIMILARITY_THRESHOLD,
        )

        logger.info(f"Vector search returned {len(results)} results")

        # Deduplicate by parent_entry_id (chunks from same entry)
        # Keep the highest similarity score per parent entry
        deduplicated: Dict[str, dict] = {}

        for result in results:
            parent_id = result.get("parent_entry_id") or result.get("entry_id")
            similarity = result.get("similarity_score", 0)

            if parent_id not in deduplicated or similarity > deduplicated[parent_id]["similarity_score"]:
                deduplicated[parent_id] = {
                    "id": parent_id,
                    "similarity_score": similarity,
                    "content": result.get("content", ""),
                    "metadata": result.get("metadata", {}),
                }

        # Fetch full entry details from Firebase for better display
        similar_entries: List[SimilarEntry] = []
        firebase_mcp = FirebaseService()

        # Sort by similarity and take top 5
        sorted_results = sorted(
            deduplicated.values(),
            key=lambda x: x["similarity_score"],
            reverse=True
        )[:5]

        for item in sorted_results:
            entry_id = item["id"]

            # Try to get full entry from Firebase
            try:
                entry_result = await firebase_mcp.get_entry(entry_id)
                if entry_result["success"]:
                    entry = entry_result["entry"]
                    title = entry.get("title", "Untitled")
                    content = entry.get("content", item["content"])
                    entry_type = entry.get("type", item["metadata"].get("entryType", "unknown"))
                    category = entry.get("metadata", {}).get("category") or entry.get("category")
                    created_at = entry.get("createdAt")
                else:
                    # Fallback to search result metadata
                    title = item["metadata"].get("title", "Untitled")
                    content = item["content"]
                    entry_type = item["metadata"].get("entryType", "unknown")
                    category = item["metadata"].get("category")
                    created_at = item["metadata"].get("createdAt")
            except Exception as e:
                logger.warning(f"Could not fetch entry {entry_id}: {e}")
                # Use search result metadata as fallback
                title = item["metadata"].get("title", "Untitled")
                content = item["content"]
                entry_type = item["metadata"].get("entryType", "unknown")
                category = item["metadata"].get("category")
                created_at = item["metadata"].get("createdAt")

            # Apply title boost if titles are similar
            similarity = item["similarity_score"]
            if _titles_similar(request.title, title):
                similarity = min(1.0, similarity + 0.05)  # 5% boost, max 1.0
                logger.info(f"Title match boost applied for: {title}")

            # Create content snippet (first 200 chars)
            snippet = content[:200] if len(content) > 200 else content
            snippet = snippet.replace('\n', ' ').strip()
            if len(content) > 200:
                snippet += "..."

            similar_entries.append(SimilarEntry(
                id=entry_id,
                title=title,
                similarity_score=round(similarity, 2),
                type=entry_type,
                category=category,
                content_snippet=snippet,
                created_at=str(created_at) if created_at else None
            ))

        # Re-sort after title boost
        similar_entries.sort(key=lambda x: x.similarity_score, reverse=True)

        has_duplicates = len(similar_entries) > 0

        logger.info(f"Duplicate check complete: {len(similar_entries)} similar entries found")

        return DuplicateCheckResponse(
            has_duplicates=has_duplicates,
            similar_entries=similar_entries
        )

    except Exception as e:
        logger.error(f"Duplicate check error: {e}", exc_info=True)
        # Fail gracefully - don't block entry creation
        return DuplicateCheckResponse(
            has_duplicates=False,
            similar_entries=[]
        )


def _titles_similar(title1: str, title2: str) -> bool:
    """
    Check if two titles are similar using simple heuristics.

    Returns True if:
    - Titles are identical (case-insensitive)
    - One title contains the other
    - Titles share significant words
    """
    t1 = title1.lower().strip()
    t2 = title2.lower().strip()

    # Exact match
    if t1 == t2:
        return True

    # One contains the other
    if t1 in t2 or t2 in t1:
        return True

    # Check word overlap (at least 50% of words match)
    words1 = set(t1.split())
    words2 = set(t2.split())

    # Remove common words
    stop_words = {"a", "an", "the", "to", "in", "on", "for", "of", "and", "or", "how"}
    words1 = words1 - stop_words
    words2 = words2 - stop_words

    if not words1 or not words2:
        return False

    overlap = len(words1 & words2)
    min_words = min(len(words1), len(words2))

    return overlap >= min_words * 0.5
