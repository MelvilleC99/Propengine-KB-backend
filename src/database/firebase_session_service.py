"""Firebase-based session management for PropertyEngine KB"""

import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)

class FirebaseSessionManager:
    """Manages user sessions with Firebase persistence"""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.sessions_collection = "kb_sessions"
        self.messages_collection = "kb_messages"
        self.session_timeout = timedelta(hours=2)
        self.max_messages_per_session = 50
    
    def create_session(self, user_info: Optional[Dict] = None) -> str:
        """Create a new session in Firebase"""
        session_id = str(uuid.uuid4())
        
        session_data = {
            "session_id": session_id,
            
            # User identification
            "agent_id": user_info.get("agent_id") if user_info else None,
            "user_email": user_info.get("email") if user_info else None,
            "user_name": user_info.get("name") if user_info else None,
            "company": user_info.get("company") if user_info else None,
            "division": user_info.get("division") if user_info else None,
            "agency": user_info.get("agency") if user_info else None,
            "office": user_info.get("office") if user_info else None,
            "user_type": user_info.get("user_type") if user_info else None,
            
            # Session metadata
            "created_at": SERVER_TIMESTAMP,
            "last_activity": SERVER_TIMESTAMP,
            "message_count": 0,
            "status": "active",
            
            # Conversation tracking
            "conversation_summary": "",
            "topics_discussed": [],
            
            # Analytics
            "total_queries": 0,
            "escalations": 0,
            "avg_confidence": 0.0,
            "feedback_positive": 0,
            "feedback_negative": 0
        }
        
        try:
            if self.db:
                self.db.collection(self.sessions_collection).document(session_id).set(session_data)
                logger.info(f"✅ Created Firebase session: {session_id}")
            else:
                logger.warning(f"⚠️ Firebase unavailable, session {session_id} created in-memory only")
                
        except Exception as e:
            logger.error(f"❌ Failed to create Firebase session {session_id}: {e}")
            # Continue without Firebase - fallback to in-memory
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session from Firebase with timeout check"""
        try:
            if not self.db:
                logger.warning("⚠️ Firebase unavailable for session lookup")
                return None
                
            doc_ref = self.db.collection(self.sessions_collection).document(session_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                logger.info(f"Session {session_id} not found")
                return None
            
            session_data = doc.to_dict()
            
            # Check if session expired
            if self._is_session_expired(session_data):
                logger.info(f"Session {session_id} expired, cleaning up")
                self.end_session(session_id, reason="timeout")
                return None
            
            # Update last activity
            doc_ref.update({"last_activity": SERVER_TIMESTAMP})
            session_data["last_activity"] = datetime.now()
            
            return session_data
            
        except Exception as e:
            logger.error(f"❌ Failed to get session {session_id}: {e}")
            return None
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Add message to session and Firebase messages collection"""
        try:
            if not self.db:
                logger.warning("⚠️ Firebase unavailable for message logging")
                return False
            
            message_data = {
                "session_id": session_id,
                "role": role,  # "user" or "assistant"
                "content": content,
                "timestamp": SERVER_TIMESTAMP,
                "metadata": metadata or {}
            }
            
            # Add message to messages collection
            message_ref = self.db.collection(self.messages_collection).add(message_data)
            message_id = message_ref[1].id
            
            # Update session message count and last activity
            session_ref = self.db.collection(self.sessions_collection).document(session_id)
            session_ref.update({
                "message_count": Increment(1),
                "last_activity": SERVER_TIMESTAMP,
                "total_queries": Increment(1) if role == "user" else Increment(0)
            })
            
            logger.info(f"✅ Added {role} message to session {session_id}: {message_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add message to session {session_id}: {e}")
            return False
    
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages for conversation context"""
        try:
            if not self.db:
                return []
            
            messages_query = (
                self.db.collection(self.messages_collection)
                .where("session_id", "==", session_id)
                .order_by("timestamp", direction="DESCENDING")
                .limit(limit)
            )
            
            messages = []
            for doc in messages_query.get():
                message_data = doc.to_dict()
                messages.append({
                    "role": message_data["role"],
                    "content": message_data["content"],
                    "timestamp": message_data["timestamp"],
                    "metadata": message_data.get("metadata", {})
                })
            
            # Reverse to get chronological order
            messages.reverse()
            return messages
            
        except Exception as e:
            logger.error(f"❌ Failed to get recent messages for session {session_id}: {e}")
            return []
    
    def update_session_summary(self, session_id: str, summary: str) -> bool:
        """Update conversation summary for session"""
        try:
            if not self.db:
                return False
                
            self.db.collection(self.sessions_collection).document(session_id).update({
                "conversation_summary": summary,
                "last_activity": SERVER_TIMESTAMP
            })
            
            logger.info(f"✅ Updated summary for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update summary for session {session_id}: {e}")
            return False
    
    def _is_session_expired(self, session_data: Dict) -> bool:
        """Check if session has expired"""
        try:
            last_activity = session_data.get("last_activity")
            if not last_activity:
                return True
                
            # Convert Firestore timestamp to datetime if needed
            if hasattr(last_activity, 'timestamp'):
                last_activity = datetime.fromtimestamp(last_activity.timestamp())
            elif isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
            
            return datetime.now() - last_activity > self.session_timeout
            
        except Exception as e:
            logger.error(f"❌ Error checking session expiration: {e}")
            return True
    
    def end_session(self, session_id: str, reason: str = "user_ended") -> bool:
        """Explicitly end a session with reason"""
        try:
            if not self.db:
                return False
                
            # Update session status to ended
            self.db.collection(self.sessions_collection).document(session_id).update({
                "status": "ended",
                "ended_at": SERVER_TIMESTAMP,
                "end_reason": reason,  # "user_ended", "timeout", "escalation", "completed"
                "last_activity": SERVER_TIMESTAMP
            })
            
            logger.info(f"✅ Session {session_id} ended: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to end session {session_id}: {e}")
            return False
    
    def should_end_session(self, session_data: Dict) -> tuple[bool, str]:
        """Determine if session should be ended based on criteria"""
        
        # Check message count limit
        if session_data.get("message_count", 0) >= self.max_messages_per_session:
            return True, "message_limit_reached"
        
        # Check for escalation
        if session_data.get("escalations", 0) > 0:
            return True, "escalated_to_human"
        
        # Check for explicit end signals
        if session_data.get("status") == "ending":
            return True, "user_requested_end"
            
        # Check for prolonged inactivity (beyond normal timeout)
        last_activity = session_data.get("last_activity")
        if last_activity:
            extended_timeout = timedelta(hours=24)  # 24 hours max
            if hasattr(last_activity, 'timestamp'):
                last_activity = datetime.fromtimestamp(last_activity.timestamp())
            elif isinstance(last_activity, str):
                last_activity = datetime.fromisoformat(last_activity)
                
            if datetime.now() - last_activity > extended_timeout:
                return True, "extended_inactivity"
        
        return False, "continue"
    
    def get_active_sessions_count(self) -> int:
        """Get count of active sessions (for monitoring)"""
        try:
            if not self.db:
                return 0
                
            # Get sessions active in last 2 hours
            cutoff_time = datetime.now() - self.session_timeout
            active_sessions = (
                self.db.collection(self.sessions_collection)
                .where("status", "==", "active")
                .where("last_activity", ">=", cutoff_time)
                .get()
            )
            
            return len(list(active_sessions))
            
        except Exception as e:
            logger.error(f"❌ Failed to get active sessions count: {e}")
            return 0

    def end_session_with_summary(self, session_id: str, final_summary: Dict, reason: str = "completed") -> bool:
        """
        End session and store final summary for analytics
        
        Args:
            session_id: Session to end
            final_summary: Summary dict from ChatSummarizer
            reason: End reason
            
        Returns:
            bool: Success status
        """
        try:
            if not self.db:
                return False
            
            # Update session with final summary and status
            self.db.collection(self.sessions_collection).document(session_id).update({
                "status": "ended",
                "ended_at": SERVER_TIMESTAMP,
                "end_reason": reason,
                "last_activity": SERVER_TIMESTAMP,
                # Final summary fields
                "final_summary": final_summary.get("summary", ""),
                "topics_discussed": final_summary.get("topics", []),
                "resolution_status": final_summary.get("resolution_status", "unknown"),
                "user_satisfaction": final_summary.get("user_satisfaction", "unknown"),
                "key_issues": final_summary.get("key_issues", ""),
                "outcome": final_summary.get("outcome", ""),
                "session_duration_seconds": final_summary.get("session_duration"),
                "total_messages": final_summary.get("message_count", 0)
            })
            
            logger.info(f"✅ Session {session_id} ended with final summary: {final_summary.get('resolution_status')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to end session with summary {session_id}: {e}")
            return False
