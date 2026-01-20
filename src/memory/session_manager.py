"""Session management with Redis caching and Firebase persistence"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from src.database.firebase_session import FirebaseSessionManager
from src.memory.context_cache import RedisContextCache

logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages user sessions with Redis cache for speed and Firebase for persistence
    
    Architecture:
    - Redis: Fast context cache (last 8 messages per session)
    - Firebase: Persistent storage (all messages, analytics)
    - Memory: Fallback if both Redis and Firebase fail
    """
    
    def __init__(self):
        """Initialize session storage with Redis cache + Firebase persistence"""
        # Fast Redis cache for immediate context
        self.context_cache = RedisContextCache()
        
        # Firebase for persistence and analytics
        self.firebase_sessions = FirebaseSessionManager()
        
        # Fallback in-memory storage if both Redis and Firebase fail
        self.memory_sessions: Dict[str, Dict] = {}
        self.max_history_length = 20
        self.session_timeout = timedelta(hours=2)
        
        # Batch writing configuration
        self.batch_counter = {}  # session_id -> message_count
        self.batch_threshold = 5  # Write to Firebase every 5 messages
        
        logger.info("✅ SessionManager initialized with Redis cache + Firebase persistence")
    
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
        """
        Add message with Redis cache (immediate) + Firebase batch writing
        
        Args:
            session_id: Session identifier
            role: "user" or "assistant"
            content: Message content  
            metadata: Optional metadata (confidence, sources, etc.)
            
        Returns:
            bool: Success status
        """
        try:
            # 1. Always add to Redis cache first (immediate, fast)
            cache_success = self.context_cache.add_message(session_id, role, content, metadata)
            
            # 2. Increment batch counter
            self.batch_counter[session_id] = self.batch_counter.get(session_id, 0) + 1
            
            # 3. Batch write to Firebase every N messages
            if self.batch_counter[session_id] >= self.batch_threshold:
                self._batch_write_to_firebase(session_id)
                self.batch_counter[session_id] = 0
            
            return cache_success
            
        except Exception as e:
            logger.error(f"❌ Error adding message to session {session_id}: {e}")
            # Fallback to memory
            return self._add_memory_message(session_id, role, content)
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """
        Get conversation history (Redis first, Firebase fallback)
        
        Args:
            session_id: Session to get history for
            limit: Maximum number of messages to return
            
        Returns:
            List[Dict]: Recent messages in chronological order
        """
        try:
            # Try Redis cache first (fastest)
            messages = self.context_cache.get_messages(session_id, limit)
            if messages:
                return messages
                
        except Exception as e:
            logger.error(f"❌ Redis history lookup failed: {e}")
        
        try:
            # Fallback to Firebase
            messages = self.firebase_sessions.get_recent_messages(session_id, limit)
            if messages:
                return messages
                
        except Exception as e:
            logger.error(f"❌ Firebase history lookup failed: {e}")
        
        # Final fallback to in-memory
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
    
    def _batch_write_to_firebase(self, session_id: str) -> bool:
        """
        Batch write recent messages from Redis cache to Firebase
        Called every N messages for performance optimization
        
        Args:
            session_id: Session to write messages for
            
        Returns:
            bool: Success status
        """
        try:
            # Get recent messages from Redis cache
            messages = self.context_cache.get_messages(session_id, self.batch_threshold)
            
            if not messages:
                return True
            
            # Write batch to Firebase (background task would be better)
            success = True
            for msg in messages:
                try:
                    self.firebase_sessions.add_message(
                        session_id, 
                        msg["role"], 
                        msg["content"], 
                        msg.get("metadata")
                    )
                except Exception as e:
                    logger.error(f"Failed to write message to Firebase: {e}")
                    success = False
            
            if success:
                logger.info(f"✅ Batch wrote {len(messages)} messages to Firebase for session {session_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ Batch write to Firebase failed for session {session_id}: {e}")
            return False
    
    def get_context_for_llm(self, session_id: str, max_messages: int = 4) -> str:
        """
        Get formatted conversation context for LLM processing
        Uses Redis cache for fastest retrieval
        
        Args:
            session_id: Session to get context for
            max_messages: Maximum recent messages to include
            
        Returns:
            str: Formatted conversation context
        """
        return self.context_cache.get_context(session_id, max_messages)
    
    def force_write_to_firebase(self, session_id: str) -> bool:
        """
        Force immediate write of all cached messages to Firebase
        Useful for session end or critical errors
        
        Args:
            session_id: Session to force write
            
        Returns:
            bool: Success status
        """
        try:
            messages = self.context_cache.get_messages(session_id)
            if messages:
                self._batch_write_to_firebase(session_id)
                self.batch_counter[session_id] = 0
                logger.info(f"Force wrote session {session_id} to Firebase")
            return True
        except Exception as e:
            logger.error(f"Force write failed for session {session_id}: {e}")
            return False
    
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
