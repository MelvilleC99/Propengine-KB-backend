"""
Session Fallback Management
Handles in-memory session storage when Redis/Firebase are unavailable
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)


class SessionFallback:
    """
    Manages in-memory fallback sessions when Redis/Firebase fail
    
    Responsibilities:
    - Create and manage in-memory sessions
    - Store messages when primary storage fails
    - Handle session expiration
    - Provide fallback history retrieval
    """
    
    def __init__(self):
        """Initialize fallback storage"""
        # In-memory storage if both Redis and Firebase fail
        self.memory_sessions: Dict[str, Dict] = {}
        self.max_history_length = 20
        self.session_timeout = timedelta(minutes=30)
        
        logger.info("SessionFallback initialized")
    
    def create_session(self, user_info: Optional[Dict] = None) -> str:
        """
        Create session in memory (fallback mode)
        
        Args:
            user_info: Optional user information
            
        Returns:
            str: Session ID
        """
        session_id = str(uuid.uuid4())
        self.memory_sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "messages": [],
            "user_info": user_info or {},
            "metadata": {
                "total_queries": 0,
                "collections_used": [],
                "escalated": False,
                "fallback": True  # Mark as fallback session
            }
        }
        logger.warning(f"⚠️ Created fallback memory session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get session from memory with expiration check
        
        Args:
            session_id: Session to retrieve
            
        Returns:
            Session dict or None if expired/not found
        """
        session = self.memory_sessions.get(session_id)
        if session:
            # Check if session expired
            if datetime.now() - session["last_activity"] > self.session_timeout:
                logger.info(f"Memory session {session_id} expired")
                del self.memory_sessions[session_id]
                return None
            # Update last activity
            session["last_activity"] = datetime.now()
        return session
    
    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """
        Add message to in-memory session
        
        Args:
            session_id: Session identifier
            role: "user" or "assistant"
            content: Message content
            
        Returns:
            bool: Success status
        """
        session = self.get_session(session_id)
        if not session:
            # Create new session if doesn't exist
            new_session_id = self.create_session()
            session = self.memory_sessions[new_session_id]
        
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
        
        logger.debug(f"Added message to fallback session {session_id}")
        return True
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """
        Get message history from in-memory session
        
        Args:
            session_id: Session identifier
            limit: Maximum messages to return
            
        Returns:
            List of recent messages
        """
        session = self.get_session(session_id)
        if session:
            return session["messages"][-limit:]
        return []
    
    def get_context(self, session_id: str, max_messages: int = 4) -> str:
        """
        Get formatted conversation context for LLM
        
        Args:
            session_id: Session identifier
            max_messages: Maximum recent messages to include
            
        Returns:
            Formatted conversation string
        """
        messages = self.get_history(session_id, max_messages)
        if not messages:
            return ""
        
        context_lines = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context_lines.append(f"{role}: {content}")
        
        return "\n".join(context_lines)
    
    def update_metadata(self, session_id: str, key: str, value) -> bool:
        """
        Update session metadata
        
        Args:
            session_id: Session identifier
            key: Metadata key
            value: Metadata value
            
        Returns:
            bool: Success status
        """
        session = self.get_session(session_id)
        if session:
            session["metadata"][key] = value
            return True
        return False
    
    def get_active_sessions_count(self) -> int:
        """
        Get count of active (non-expired) sessions
        
        Returns:
            Number of active sessions
        """
        active_count = 0
        for session in self.memory_sessions.values():
            if datetime.now() - session["last_activity"] <= self.session_timeout:
                active_count += 1
        return active_count
    
    def clear_expired_sessions(self) -> int:
        """
        Remove expired in-memory sessions
        
        Returns:
            Number of sessions cleared
        """
        expired = []
        for session_id, session in self.memory_sessions.items():
            if datetime.now() - session["last_activity"] > self.session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            del self.memory_sessions[session_id]
            logger.info(f"Cleared expired memory session: {session_id}")
        
        return len(expired)
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a specific session from memory
        
        Args:
            session_id: Session to clear
            
        Returns:
            bool: Success status
        """
        if session_id in self.memory_sessions:
            del self.memory_sessions[session_id]
            logger.debug(f"Cleared fallback session {session_id}")
            return True
        return False
    
    def get_stats(self) -> Dict:
        """
        Get fallback storage statistics
        
        Returns:
            Dict with current stats
        """
        total_messages = sum(len(s["messages"]) for s in self.memory_sessions.values())
        active = self.get_active_sessions_count()
        
        return {
            "total_sessions": len(self.memory_sessions),
            "active_sessions": active,
            "total_messages": total_messages,
            "storage_mode": "in-memory"
        }
