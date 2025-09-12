"""Session management for conversation history"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import uuid
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions and conversation history"""
    
    def __init__(self):
        """Initialize session storage"""
        self.sessions: Dict[str, Dict] = {}
        self.max_history_length = 20  # Keep last 20 messages per session
        self.session_timeout = timedelta(hours=2)  # Sessions expire after 2 hours
    
    def create_session(self, user_info: Optional[Dict] = None) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "messages": [],
            "user_info": user_info or {},
            "metadata": {
                "total_queries": 0,
                "collections_used": [],
                "escalated": False
            }
        }
        logger.info(f"Created new session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID"""
        session = self.sessions.get(session_id)
        if session:
            # Check if session expired
            if datetime.now() - session["last_activity"] > self.session_timeout:
                logger.info(f"Session {session_id} expired")
                del self.sessions[session_id]
                return None
            # Update last activity
            session["last_activity"] = datetime.now()
        return session
    
    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """Add a message to session history"""
        session = self.get_session(session_id)
        if not session:
            # Create new session if doesn't exist
            session_id = self.create_session()
            session = self.sessions[session_id]
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        session["messages"].append(message)
        
        # Keep only last N messages
        if len(session["messages"]) > self.max_history_length:
            session["messages"] = session["messages"][-self.max_history_length:]
        
        # Update metadata
        if role == "user":
            session["metadata"]["total_queries"] += 1
        
        return True
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history for a session"""
        session = self.get_session(session_id)
        if session:
            return session["messages"][-limit:]
        return []
    
    def update_metadata(self, session_id: str, key: str, value) -> bool:
        """Update session metadata"""
        session = self.get_session(session_id)
        if session:
            session["metadata"][key] = value
            return True
        return False
    
    def get_active_sessions(self) -> List[Dict]:
        """Get all active sessions"""
        active = []
        for session_id, session in list(self.sessions.items()):
            if datetime.now() - session["last_activity"] <= self.session_timeout:
                active.append({
                    "id": session_id,
                    "created_at": session["created_at"].isoformat(),
                    "last_activity": session["last_activity"].isoformat(),
                    "total_queries": session["metadata"]["total_queries"]
                })
        return active
    
    def clear_expired_sessions(self):
        """Remove expired sessions"""
        expired = []
        for session_id, session in self.sessions.items():
            if datetime.now() - session["last_activity"] > self.session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            del self.sessions[session_id]
            logger.info(f"Cleared expired session: {session_id}")
        
        return len(expired)
