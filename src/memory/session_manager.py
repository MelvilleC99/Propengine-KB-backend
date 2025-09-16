"""Session management with Firebase persistence"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from src.database.firebase_session import FirebaseSessionManager

logger = logging.getLogger(__name__)

class SessionManager:
    """Manages user sessions with Firebase persistence and in-memory fallback"""
    
    def __init__(self):
        """Initialize session storage with Firebase backend"""
        self.firebase_sessions = FirebaseSessionManager()
        
        # Fallback in-memory storage if Firebase fails
        self.memory_sessions: Dict[str, Dict] = {}
        self.max_history_length = 20
        self.session_timeout = timedelta(hours=2)
        
        logger.info("✅ SessionManager initialized with Firebase backend")
    
    def create_session(self, user_info: Optional[Dict] = None) -> str:
        """Create a new session with Firebase persistence"""
        try:
            # Try Firebase first
            session_id = self.firebase_sessions.create_session(user_info)
            logger.info(f"✅ Created Firebase session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"❌ Firebase session creation failed: {e}")
            # Fallback to in-memory
            return self._create_memory_session(user_info)
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session from Firebase with in-memory fallback"""
        try:
            # Try Firebase first
            session = self.firebase_sessions.get_session(session_id)
            if session:
                return session
                
        except Exception as e:
            logger.error(f"❌ Firebase session lookup failed: {e}")
        
        # Fallback to in-memory
        return self._get_memory_session(session_id)
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """Add message with Firebase persistence"""
        try:
            # Try Firebase first
            success = self.firebase_sessions.add_message(session_id, role, content, metadata)
            if success:
                return True
                
        except Exception as e:
            logger.error(f"❌ Firebase message logging failed: {e}")
        
        # Fallback to in-memory
        return self._add_memory_message(session_id, role, content)
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get conversation history with Firebase persistence"""
        try:
            # Try Firebase first
            messages = self.firebase_sessions.get_recent_messages(session_id, limit)
            if messages:
                return messages
                
        except Exception as e:
            logger.error(f"❌ Firebase history lookup failed: {e}")
        
        # Fallback to in-memory
        return self._get_memory_history(session_id, limit)
    
    def update_metadata(self, session_id: str, key: str, value) -> bool:
        """Update session metadata"""
        # For now, this is primarily used for in-memory sessions
        # Firebase sessions have their own metadata structure
        session = self._get_memory_session(session_id)
        if session:
            session["metadata"][key] = value
            return True
        return False
    
    def get_active_sessions(self) -> List[Dict]:
        """Get all active sessions (Firebase + in-memory)"""
        try:
            # Get Firebase active count
            firebase_count = self.firebase_sessions.get_active_sessions_count()
            memory_count = len([s for s in self.memory_sessions.values() 
                             if datetime.now() - s["last_activity"] <= self.session_timeout])
            
            return [{
                "firebase_sessions": firebase_count,
                "memory_sessions": memory_count,
                "total_sessions": firebase_count + memory_count
            }]
            
        except Exception as e:
            logger.error(f"❌ Error getting active sessions: {e}")
            return []
    
    def clear_expired_sessions(self):
        """Remove expired in-memory sessions (Firebase handles its own cleanup)"""
        expired = []
        for session_id, session in self.memory_sessions.items():
            if datetime.now() - session["last_activity"] > self.session_timeout:
                expired.append(session_id)
        
        for session_id in expired:
            del self.memory_sessions[session_id]
            logger.info(f"Cleared expired memory session: {session_id}")
        
        return len(expired)
    
    # In-memory fallback methods
    def _create_memory_session(self, user_info: Optional[Dict] = None) -> str:
        """Fallback: Create session in memory"""
        import uuid
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
    
    def _get_memory_session(self, session_id: str) -> Optional[Dict]:
        """Fallback: Get session from memory"""
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
    
    def _add_memory_message(self, session_id: str, role: str, content: str) -> bool:
        """Fallback: Add message to memory"""
        session = self._get_memory_session(session_id)
        if not session:
            # Create new session if doesn't exist
            session_id = self._create_memory_session()
            session = self.memory_sessions[session_id]
        
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
    
    def _get_memory_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Fallback: Get history from memory"""
        session = self._get_memory_session(session_id)
        if session:
            return session["messages"][-limit:]
        return []
