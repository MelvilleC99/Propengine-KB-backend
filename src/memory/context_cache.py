"""
Redis-based context cache for fast conversation memory
Handles immediate message storage and retrieval for conversational context
"""

import json
import redis
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from src.config.settings import settings

logger = logging.getLogger(__name__)

class RedisContextCache:
    """
    Fast Redis-based cache for conversation context
    Stores last 8 messages per session with 2-hour TTL
    """
    
    def __init__(self):
        """Initialize Redis connection with fallback to in-memory storage"""
        self.redis_client = None
        self.memory_fallback = {}  # Fallback if Redis fails
        self.max_messages_per_session = 8
        self.session_ttl = 7200  # 2 hours in seconds
        
        try:
            # Connect to Redis Cloud using environment variables
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                db=settings.REDIS_DB,
                decode_responses=True,  # Auto-decode strings
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            
            # Test connection
            self.redis_client.ping()
            logger.info("✅ Redis Context Cache connected successfully")
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.warning("⚠️ Falling back to in-memory cache")
            self.redis_client = None
    
    def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add message to cache (Redis first, fallback to memory)
        
        Args:
            session_id: Unique session identifier
            role: "user" or "assistant" 
            content: Message content
            metadata: Optional metadata (confidence, sources, etc.)
        
        Returns:
            bool: Success status
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        try:
            if self.redis_client:
                # Use Redis for primary storage
                return self._add_to_redis(session_id, message)
            else:
                # Fallback to in-memory storage
                return self._add_to_memory(session_id, message)
                
        except Exception as e:
            logger.error(f"Error adding message to cache: {e}")
            # Try memory fallback if Redis fails
            return self._add_to_memory(session_id, message)
    
    def get_context(self, session_id: str, max_messages: int = 4) -> str:
        """
        Get formatted conversation context for LLM
        
        Args:
            session_id: Session to get context for
            max_messages: Maximum number of recent messages to include
            
        Returns:
            str: Formatted conversation context
        """
        try:
            messages = self.get_messages(session_id, max_messages)
            
            if not messages:
                return ""
            
            # Format for LLM consumption
            context_lines = []
            for msg in messages:
                context_lines.append(f"{msg['role']}: {msg['content']}")
            
            return "\n".join(context_lines)
            
        except Exception as e:
            logger.error(f"Error getting context for session {session_id}: {e}")
            return ""
    
    def get_messages(self, session_id: str, limit: int = 8) -> List[Dict]:
        """
        Get recent messages from cache
        
        Args:
            session_id: Session to get messages for
            limit: Maximum number of messages to return
            
        Returns:
            List[Dict]: Recent messages in chronological order
        """
        try:
            if self.redis_client:
                return self._get_from_redis(session_id, limit)
            else:
                return self._get_from_memory(session_id, limit)
                
        except Exception as e:
            logger.error(f"Error getting messages for session {session_id}: {e}")
            # Try memory fallback
            return self._get_from_memory(session_id, limit)
    
    def get_session_stats(self, session_id: str) -> Dict:
        """
        Get session statistics from cache
        
        Returns:
            Dict: Session stats (message count, duration, etc.)
        """
        messages = self.get_messages(session_id)
        
        if not messages:
            return {"message_count": 0, "duration_minutes": 0}
        
        first_message = messages[0]
        last_message = messages[-1]
        
        start_time = datetime.fromisoformat(first_message["timestamp"])
        end_time = datetime.fromisoformat(last_message["timestamp"])
        duration = (end_time - start_time).total_seconds() / 60
        
        return {
            "message_count": len(messages),
            "duration_minutes": round(duration, 1),
            "user_messages": len([m for m in messages if m["role"] == "user"]),
            "assistant_messages": len([m for m in messages if m["role"] == "assistant"])
        }
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear all messages for a session
        
        Args:
            session_id: Session to clear
            
        Returns:
            bool: Success status
        """
        try:
            if self.redis_client:
                key = f"context:{session_id}"
                self.redis_client.delete(key)
                logger.info(f"Cleared Redis cache for session {session_id}")
            
            # Also clear from memory fallback
            if session_id in self.memory_fallback:
                del self.memory_fallback[session_id]
                
            return True
            
        except Exception as e:
            logger.error(f"Error clearing session {session_id}: {e}")
            return False
    
    def _add_to_redis(self, session_id: str, message: Dict) -> bool:
        """Add message to Redis list with TTL"""
        key = f"context:{session_id}"
        
        # Add message to beginning of list (most recent first)
        self.redis_client.lpush(key, json.dumps(message))
        
        # Trim to keep only max_messages_per_session
        self.redis_client.ltrim(key, 0, self.max_messages_per_session - 1)
        
        # Set expiration
        self.redis_client.expire(key, self.session_ttl)
        
        return True
    
    def _get_from_redis(self, session_id: str, limit: int) -> List[Dict]:
        """Get messages from Redis list"""
        key = f"context:{session_id}"
        
        # Get messages (most recent first due to lpush)
        raw_messages = self.redis_client.lrange(key, 0, limit - 1)
        
        messages = []
        for raw_msg in reversed(raw_messages):  # Reverse to get chronological order
            try:
                messages.append(json.loads(raw_msg))
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing Redis message: {e}")
                continue
        
        return messages
    
    def _add_to_memory(self, session_id: str, message: Dict) -> bool:
        """Fallback: Add message to in-memory storage"""
        if session_id not in self.memory_fallback:
            self.memory_fallback[session_id] = []
        
        self.memory_fallback[session_id].append(message)
        
        # Keep only recent messages
        if len(self.memory_fallback[session_id]) > self.max_messages_per_session:
            self.memory_fallback[session_id] = self.memory_fallback[session_id][-self.max_messages_per_session:]
        
        return True
    
    def _get_from_memory(self, session_id: str, limit: int) -> List[Dict]:
        """Fallback: Get messages from in-memory storage"""
        messages = self.memory_fallback.get(session_id, [])
        return messages[-limit:] if limit else messages
    
    def health_check(self) -> Dict:
        """
        Check Redis health and return status
        
        Returns:
            Dict: Health status information
        """
        try:
            if self.redis_client:
                self.redis_client.ping()
                info = self.redis_client.info()
                return {
                    "status": "healthy",
                    "redis_connected": True,
                    "memory_usage": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "fallback_sessions": len(self.memory_fallback)
                }
            else:
                return {
                    "status": "degraded",
                    "redis_connected": False,
                    "fallback_sessions": len(self.memory_fallback)
                }
                
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e),
                "fallback_sessions": len(self.memory_fallback)
            }
