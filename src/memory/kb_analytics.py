"""
KB Analytics Tracker for monitoring knowledge base usage
Tracks which KB entries are used most frequently
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from src.database.firebase_session import FirebaseSessionManager

logger = logging.getLogger(__name__)

class KBAnalyticsTracker:
    """
    Tracks knowledge base entry usage for analytics and optimization
    
    Metrics tracked:
    - Entry usage count
    - Average confidence scores
    - Last used timestamps
    - User query patterns
    """
    
    def __init__(self):
        """Initialize analytics tracker with Firebase backend"""
        self.firebase_sessions = FirebaseSessionManager()
        self.analytics_collection = "kb_analytics"
        
        logger.info("✅ KB Analytics Tracker initialized")
    
    def track_kb_usage(self, sources: List[Dict], query: str, confidence: float, session_id: str) -> bool:
        """
        Track usage of KB entries from search results
        
        Args:
            sources: List of KB sources used in response
            query: User's original query
            confidence: Overall response confidence
            session_id: Session identifier
            
        Returns:
            bool: Success status
        """
        try:
            if not sources:
                return True
            
            for source in sources:
                self._update_entry_analytics(
                    source=source,
                    query=query, 
                    confidence=confidence,
                    session_id=session_id
                )
            
            logger.info(f"✅ Tracked usage for {len(sources)} KB entries")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to track KB usage: {e}")
            return False
    
    def _update_entry_analytics(self, source: Dict, query: str, confidence: float, session_id: str) -> bool:
        """
        Update analytics for a specific KB entry
        
        Args:
            source: KB source information
            query: User query
            confidence: Response confidence
            session_id: Session ID
            
        Returns:
            bool: Success status
        """
        try:
            if not self.firebase_sessions.db:
                return False
            
            # Extract entry information
            entry_title = source.get("title", "Unknown Entry")
            entry_type = source.get("entry_type", "unknown")
            similarity_score = source.get("similarity_score", 0.0)
            
            # Create entry ID from title (normalized)
            entry_id = self._normalize_entry_id(entry_title)
            
            # Prepare analytics data
            analytics_data = {
                "entry_id": entry_id,
                "entry_title": entry_title,
                "entry_type": entry_type,
                "last_used": datetime.now().isoformat(),
                "last_query": query[:200],  # Truncate long queries
                "last_similarity_score": similarity_score,
                "last_confidence": confidence,
                "last_session_id": session_id
            }
            
            # Get existing analytics document
            doc_ref = self.firebase_sessions.db.collection(self.analytics_collection).document(entry_id)
            doc = doc_ref.get()
            
            if doc.exists:
                # Update existing entry
                existing_data = doc.to_dict()
                
                # Calculate new averages
                old_count = existing_data.get("usage_count", 0)
                new_count = old_count + 1
                
                old_avg_confidence = existing_data.get("avg_confidence", 0.0)
                new_avg_confidence = ((old_avg_confidence * old_count) + confidence) / new_count
                
                old_avg_similarity = existing_data.get("avg_similarity_score", 0.0) 
                new_avg_similarity = ((old_avg_similarity * old_count) + similarity_score) / new_count
                
                # Update analytics
                analytics_data.update({
                    "usage_count": new_count,
                    "avg_confidence": round(new_avg_confidence, 3),
                    "avg_similarity_score": round(new_avg_similarity, 3),
                    "first_used": existing_data.get("first_used", analytics_data["last_used"])
                })
                
            else:
                # Create new entry
                analytics_data.update({
                    "usage_count": 1,
                    "avg_confidence": confidence,
                    "avg_similarity_score": similarity_score,
                    "first_used": analytics_data["last_used"]
                })
            
            # Write to Firebase
            doc_ref.set(analytics_data)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update entry analytics: {e}")
            return False
    
    def get_popular_entries(self, limit: int = 10, entry_type: Optional[str] = None) -> List[Dict]:
        """
        Get most popular KB entries by usage count
        
        Args:
            limit: Maximum number of entries to return
            entry_type: Optional filter by entry type
            
        Returns:
            List[Dict]: Popular entries sorted by usage count
        """
        try:
            if not self.firebase_sessions.db:
                return []
            
            query = self.firebase_sessions.db.collection(self.analytics_collection)
            
            # Filter by entry type if specified
            if entry_type:
                query = query.where("entry_type", "==", entry_type)
            
            # Order by usage count and limit results
            query = query.order_by("usage_count", direction="DESCENDING").limit(limit)
            
            popular_entries = []
            for doc in query.get():
                entry_data = doc.to_dict()
                popular_entries.append(entry_data)
            
            return popular_entries
            
        except Exception as e:
            logger.error(f"❌ Failed to get popular entries: {e}")
            return []
    
    def get_entry_analytics(self, entry_title: str) -> Optional[Dict]:
        """
        Get detailed analytics for a specific KB entry
        
        Args:
            entry_title: Title of the KB entry
            
        Returns:
            Optional[Dict]: Entry analytics or None if not found
        """
        try:
            if not self.firebase_sessions.db:
                return None
            
            entry_id = self._normalize_entry_id(entry_title)
            doc_ref = self.firebase_sessions.db.collection(self.analytics_collection).document(entry_id)
            doc = doc_ref.get()
            
            if doc.exists:
                return doc.to_dict()
            else:
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get entry analytics: {e}")
            return None
    
    def get_usage_summary(self) -> Dict:
        """
        Get overall KB usage summary statistics
        
        Returns:
            Dict: Usage summary with counts and averages
        """
        try:
            if not self.firebase_sessions.db:
                return {"error": "Firebase not available"}
            
            # Get all analytics documents
            docs = self.firebase_sessions.db.collection(self.analytics_collection).get()
            
            if not docs:
                return {"total_entries": 0}
            
            total_entries = 0
            total_usage = 0
            avg_confidence = 0.0
            entry_types = {}
            
            for doc in docs:
                data = doc.to_dict()
                total_entries += 1
                total_usage += data.get("usage_count", 0)
                avg_confidence += data.get("avg_confidence", 0.0)
                
                entry_type = data.get("entry_type", "unknown")
                entry_types[entry_type] = entry_types.get(entry_type, 0) + 1
            
            return {
                "total_entries": total_entries,
                "total_usage": total_usage,
                "avg_confidence": round(avg_confidence / total_entries, 3) if total_entries > 0 else 0.0,
                "entry_types": entry_types,
                "avg_usage_per_entry": round(total_usage / total_entries, 1) if total_entries > 0 else 0.0
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get usage summary: {e}")
            return {"error": str(e)}
    
    def _normalize_entry_id(self, title: str) -> str:
        """
        Normalize entry title to create consistent document ID
        
        Args:
            title: Original entry title
            
        Returns:
            str: Normalized entry ID
        """
        # Convert to lowercase, replace spaces and special chars with underscores
        import re
        normalized = re.sub(r'[^a-zA-Z0-9]+', '_', title.lower())
        normalized = normalized.strip('_')  # Remove leading/trailing underscores
        return normalized[:50]  # Limit length for Firestore
