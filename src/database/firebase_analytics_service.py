"""Firebase Analytics Service - Batch write query analytics"""

import logging
from typing import List, Dict
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)

class FirebaseAnalyticsService:
    """Manages analytics documents in Firebase"""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.analytics_collection = "kb_analytics"
    
    def batch_write_analytics(self, session_id: str, agent_id: str, queries: List[Dict]) -> bool:
        """
        Write all query analytics in ONE batch at session end
        
        Args:
            session_id: Session ID
            agent_id: Agent ID
            queries: List of query metadata dicts
        """
        try:
            if not self.db or not queries:
                return False
            
            # Use batch write for efficiency
            batch = self.db.batch()
            
            for query_data in queries:
                # Generate unique query ID
                query_ref = self.db.collection(self.analytics_collection).document()
                
                analytics_doc = {
                    "query_id": query_ref.id,
                    "session_id": session_id,
                    "agent_id": agent_id,
                    "timestamp": query_data.get("timestamp", SERVER_TIMESTAMP),
                    
                    # Query details
                    "query_text": query_data.get("query_text"),
                    "query_type": query_data.get("query_type"),
                    "category": query_data.get("category"),
                    
                    # Performance metrics
                    "confidence_score": query_data.get("confidence_score", 0.0),
                    "sources_found": query_data.get("sources_found", 0),
                    "sources_used": query_data.get("sources_used", []),
                    "response_time_ms": query_data.get("response_time_ms", 0),
                    
                    # Outcomes
                    "escalated": query_data.get("escalated", False),
                    "user_feedback": query_data.get("user_feedback")  # from thumbs up/down
                }
                
                batch.set(query_ref, analytics_doc)
            
            # Commit batch
            batch.commit()
            logger.info(f"✅ Batch wrote {len(queries)} analytics docs for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to batch write analytics: {e}")
            return False
