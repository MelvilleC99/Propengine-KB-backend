"""Firebase Feedback Service - Writes response feedback to Firestore"""

import logging
from datetime import datetime
from typing import Dict, Optional, List
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)


class FirebaseFeedbackService:
    """
    Manages response feedback documents in Firebase
    
    Collection: 'response_feedback'
    
    Tracks:
    - User thumbs up/down on agent responses
    - Query and response context
    - Analytics flags for dashboard
    """
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection_name = "response_feedback"
    
    def write_feedback(
        self,
        session_id: str,
        message_id: str,
        feedback_type: str,  # 'positive' or 'negative'
        query: str,
        response: str,
        agent_id: str,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        agent_type: Optional[str] = None,
        confidence_score: Optional[float] = None,
        sources_used: Optional[List[str]] = None
    ) -> Dict:
        """
        Write feedback to Firebase
        
        Args:
            session_id: Session identifier
            message_id: Message identifier
            feedback_type: 'positive' or 'negative'
            query: The user's original question
            response: The agent's response
            agent_id: User's agent ID (e.g., BID-xxx)
            user_email: User's email
            user_name: User's display name
            agent_type: 'test', 'support', or 'customer'
            confidence_score: Response confidence (0-1)
            sources_used: List of KB entry titles used
            
        Returns:
            Dict with success status and feedback_id
        """
        try:
            if not self.db:
                logger.error("Firebase not available")
                return {"success": False, "error": "Firebase not available"}
            
            # Build feedback document
            feedback_doc = {
                # Identity
                "session_id": session_id,
                "message_id": message_id,
                "agent_id": agent_id,
                "user_email": user_email,
                "user_name": user_name,
                
                # The interaction
                "query": query,
                "response": response,
                
                # Feedback
                "feedback_type": feedback_type,
                
                # Context
                "agent_type": agent_type,
                "confidence_score": confidence_score,
                "sources_used": sources_used or [],
                
                # Timestamps
                "created_at": SERVER_TIMESTAMP,
                "timestamp": datetime.now().isoformat(),
                
                # Analytics flags (computed)
                "response_helpful": feedback_type == "positive",
                "needs_improvement": feedback_type == "negative"
            }
            
            # Write to Firebase
            doc_ref = self.db.collection(self.collection_name).add(feedback_doc)
            feedback_id = doc_ref[1].id
            
            logger.info(f"✅ Feedback saved: {feedback_id} ({feedback_type})")
            
            return {
                "success": True,
                "feedback_id": feedback_id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to write feedback: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_feedback_stats(self, days: int = 7) -> Dict:
        """
        Get feedback statistics for dashboard
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dict with feedback counts and rates
        """
        try:
            if not self.db:
                return {"error": "Firebase not available"}
            
            # Get all feedback (could add date filtering)
            docs = self.db.collection(self.collection_name).get()
            
            total = 0
            positive = 0
            negative = 0
            
            for doc in docs:
                data = doc.to_dict()
                total += 1
                if data.get("feedback_type") == "positive":
                    positive += 1
                else:
                    negative += 1
            
            return {
                "total_feedback": total,
                "positive": positive,
                "negative": negative,
                "positive_rate": round(positive / total * 100, 1) if total > 0 else 0,
                "negative_rate": round(negative / total * 100, 1) if total > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get feedback stats: {e}")
            return {"error": str(e)}
    
    def get_negative_feedback(self, limit: int = 20) -> List[Dict]:
        """
        Get recent negative feedback for review
        
        Args:
            limit: Maximum results to return
            
        Returns:
            List of negative feedback documents
        """
        try:
            if not self.db:
                return []
            
            docs = (
                self.db.collection(self.collection_name)
                .where("feedback_type", "==", "negative")
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .get()
            )
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to get negative feedback: {e}")
            return []
