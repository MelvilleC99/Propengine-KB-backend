"""Session management with Redis caching and Firebase persistence"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging
from src.database.firebase_session_service import FirebaseSessionManager
from src.memory.context_cache import RedisContextCache
from src.utils.chat_summary import chat_summarizer

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
        
        # Firebase for persistence (lazy initialization)
        self._firebase_sessions = None
        self._firebase_users = None
        self._firebase_analytics = None
        
        # Fallback in-memory storage if both Redis and Firebase fail
        self.memory_sessions: Dict[str, Dict] = {}
        self.max_history_length = 20
        self.session_timeout = timedelta(minutes=30)  # Changed from 2 hours to 30 minutes
        
        # Query buffer for collecting analytics in memory (no Firebase writes during session)
        self.query_buffers = {}  # session_id -> List[query_data]
        
        # Store user info for each session (needed for user document creation)
        self.session_users = {}  # session_id -> user_info
        
        # Rolling summary configuration
        self.summary_interval = 5  # Generate summary every 5 messages
        self.summary_counter = {}  # session_id -> messages since last summary
        
        logger.info("SessionManager initialized with Redis cache + rolling summaries")
    
    @property
    def firebase_sessions(self):
        """Lazy load Firebase sessions (only when first used)"""
        if self._firebase_sessions is None:
            try:
                self._firebase_sessions = FirebaseSessionManager()
                logger.info("✅ Firebase session manager connected")
            except Exception as e:
                logger.warning(f"⚠️ Firebase session manager unavailable: {e}")
                self._firebase_sessions = None
        return self._firebase_sessions
    
    @property
    def firebase_users(self):
        """Lazy load Firebase user service"""
        if self._firebase_users is None:
            try:
                from src.database.firebase_user_service import FirebaseUserService
                self._firebase_users = FirebaseUserService()
                logger.info("✅ Firebase user service connected")
            except Exception as e:
                logger.warning(f"⚠️ Firebase user service unavailable: {e}")
                self._firebase_users = None
        return self._firebase_users

    @property
    def firebase_analytics(self):
        """Lazy load Firebase analytics service"""
        if self._firebase_analytics is None:
            try:
                from src.database.firebase_analytics_service import FirebaseAnalyticsService
                self._firebase_analytics = FirebaseAnalyticsService()
                logger.info("✅ Firebase analytics service connected")
            except Exception as e:
                logger.warning(f"⚠️ Firebase analytics service unavailable: {e}")
                self._firebase_analytics = None
        return self._firebase_analytics
    
    def create_session(self, user_info: Optional[Dict] = None) -> str:
        """Create a new session with Firebase persistence"""
        try:
            # Try Firebase first
            session_id = self.firebase_sessions.create_session(user_info)
            
            # Store user info for later use (when ending session)
            if user_info:
                self.session_users[session_id] = user_info
            
            logger.info(f"✅ Created Firebase session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"❌ Firebase session creation failed: {e}")
            # Fallback to in-memory
            session_id = self._create_memory_session(user_info)
            if user_info:
                self.session_users[session_id] = user_info
            return session_id
    
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
    
    async def add_message(self, session_id: str, role: str, content: str, metadata: Optional[Dict] = None) -> bool:
        """
        Add message with Redis cache (immediate) + in-memory query buffer
        NO MORE Firebase writes during session!
        
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
            
            # 2. NEW: Collect query metadata in memory buffer (not Firebase yet!)
            if role == "assistant" and metadata:
                if session_id not in self.query_buffers:
                    self.query_buffers[session_id] = []
                
                # Get the previous user message to use as query_text
                messages = self.context_cache.get_messages(session_id, limit=2)
                user_query = messages[-2].get("content") if len(messages) >= 2 else "Unknown query"
                
                self.query_buffers[session_id].append({
                    "query_text": user_query,  # User's question, not assistant's answer
                    "response_text": content,  # Assistant's response
                    "timestamp": datetime.now().isoformat(),
                    **metadata  # Include all metadata (confidence, sources, etc.)
                })
                logger.debug(f"📊 Buffered query metadata for session {session_id} (total: {len(self.query_buffers[session_id])})")
            
            # 3. Increment summary counter
            self.summary_counter[session_id] = self.summary_counter.get(session_id, 0) + 1
            
            # 4. Check if we should generate rolling summary (Redis only)
            if self._should_update_summary(session_id):
                await self._update_rolling_summary(session_id)
                self.summary_counter[session_id] = 0
            
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

    # === ROLLING SUMMARY METHODS (NEW) ===
    
    def _should_update_summary(self, session_id: str) -> bool:
        """Check if rolling summary should be updated"""
        count = self.summary_counter.get(session_id, 0)
        return count >= self.summary_interval
    
    async def _update_rolling_summary(self, session_id: str) -> None:
        """
        Generate and store rolling summary
        
        Called every N messages to keep context compact
        """
        try:
            logger.info(f"🔄 Generating rolling summary for session: {session_id}")
            
            # Get previous summary (if exists)
            previous_summary = self.context_cache.get_rolling_summary(session_id)
            prev_text = previous_summary.get("summary", "") if previous_summary else None
            
            logger.debug(f"Previous summary exists: {prev_text is not None}")
            
            # Get recent messages since last summary
            recent_messages = self.context_cache.get_messages(session_id, limit=self.summary_interval)
            
            if not recent_messages:
                logger.debug(f"No messages to summarize for session: {session_id}")
                return
            
            logger.debug(f"Summarizing {len(recent_messages)} messages for {session_id}")
            
            # Generate rolling summary
            summary_data = await chat_summarizer.generate_rolling_summary(
                previous_summary=prev_text,
                new_messages=recent_messages,
                session_id=session_id
            )
            
            # Store in Redis
            self.context_cache.store_rolling_summary(session_id, summary_data)
            
            logger.info(
                f"✅ Rolling summary updated for {session_id}:\n"
                f"   Topic: {summary_data.get('current_topic')}\n"
                f"   State: {summary_data.get('conversation_state')}\n"
                f"   Summary: {summary_data.get('summary', '')[:100]}..."
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to update rolling summary for {session_id}: {e}", exc_info=True)
    
    def get_context_for_llm(self, session_id: str) -> Dict:
        """
        Get optimized context for LLM (messages + summary)
        
        Returns recent messages + rolling summary for compact context.
        This is what the orchestrator should use when calling the LLM.
        
        Args:
            session_id: Session identifier
            
        Returns:
            {
                "messages": [...],  # Last 5 messages
                "summary": {...},   # Rolling summary
                "has_summary": bool,
                "formatted_context": str  # Pre-formatted for LLM
            }
        """
        context = self.context_cache.get_context_with_summary(session_id, max_messages=5)
        
        # Format for LLM
        formatted = self._format_context_for_llm(context)
        
        return {
            **context,
            "formatted_context": formatted
        }
    
    def _format_context_for_llm(self, context: Dict) -> str:
        """Format context into readable text for LLM prompt"""
        lines = []
        
        # Add summary if exists
        if context.get("has_summary") and context.get("summary"):
            summary = context["summary"]
            lines.append("=== CONVERSATION SUMMARY ===")
            lines.append(f"Overview: {summary.get('summary', '')}")
            lines.append(f"Current Topic: {summary.get('current_topic', 'unknown')}")
            lines.append(f"State: {summary.get('conversation_state', 'unknown')}")
            if summary.get("key_facts"):
                lines.append(f"Key Facts: {', '.join(summary['key_facts'])}")
            lines.append("")
        
        # Add recent messages
        if context.get("messages"):
            lines.append("=== RECENT MESSAGES ===")
            for msg in context["messages"]:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                lines.append(f"{role}: {content}")
        
        return "\n".join(lines)
    
    async def end_session_with_analytics(
        self, 
        session_id: str, 
        agent_id: str,
        reason: str = "completed"
    ) -> bool:
        """
        End session and write ALL analytics to Firebase in ONE batch
        
        Args:
            session_id: Session to end
            agent_id: User's agent ID (e.g., BID-VXDZgFkHqzphyrg)
            reason: End reason (timeout, completed, etc.)
        
        Returns:
            bool: Success status
        """
        try:
            logger.info(f"🔚 Ending session {session_id} for agent {agent_id} (reason: {reason})")
            
            # 1. Get all messages from Redis for final summary
            all_messages = self.context_cache.get_messages(session_id, limit=100)
            
            if not all_messages:
                logger.warning(f"No messages found for session: {session_id}")
                return False
            
            # 2. Get query buffer (metadata collected during session)
            queries = self.query_buffers.get(session_id, [])
            logger.info(f"📊 Collected {len(queries)} queries for analytics")
            
            # 3. Generate final session summary
            session_info = self.get_session(session_id) or {"session_id": session_id}
            final_summary = await chat_summarizer.generate_final_summary(
                all_messages=all_messages,
                session_info=session_info
            )
            
            # 4. BATCH WRITE to Firebase (ONE operation)
            if self.firebase_sessions and self.firebase_analytics and self.firebase_users:
                
                # Write session summary
                success = self.firebase_sessions.end_session_with_summary(
                    session_id=session_id,
                    final_summary=final_summary,
                    reason=reason
                )
                
                if success:
                    # Write analytics batch
                    await self.firebase_analytics.batch_write_analytics(
                        session_id=session_id,
                        agent_id=agent_id,
                        queries=queries
                    )
                    
                    # Get user info for this session
                    user_data = self.session_users.get(session_id)
                    
                    # Update user stats (creates user if doesn't exist)
                    await self.firebase_users.update_user_activity(
                        agent_id=agent_id,
                        num_queries=len(queries),
                        user_data=user_data
                    )
                    
                    # Add to user's recent sessions
                    await self.firebase_users.add_recent_session(
                        agent_id=agent_id,
                        session_summary={
                            "session_id": session_id,
                            "date": datetime.now().isoformat(),
                            "summary": final_summary.get("summary", "")[:200]  # Truncate
                        }
                    )
                    
                    logger.info(f"✅ Session {session_id} analytics written to Firebase")
            
            # 5. Clear Redis cache
            self.context_cache.clear_session(session_id)
            logger.info(f"🧹 Cleared Redis cache for session {session_id}")
            
            # 6. Clear query buffer
            if session_id in self.query_buffers:
                del self.query_buffers[session_id]
            
            # 7. Clear session user info
            if session_id in self.session_users:
                del self.session_users[session_id]
            
            # 8. Clear summary counter
            if session_id in self.summary_counter:
                del self.summary_counter[session_id]
            
            logger.info(f"✅ Session {session_id} ended successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to end session {session_id}: {e}", exc_info=True)
            return False
    
    async def end_session_with_summary(self, session_id: str, reason: str = "completed") -> bool:
        """
        End session and generate final summary for Firebase
        
        Args:
            session_id: Session to end
            reason: Why session ended
            
        Returns:
            bool: Success status
        """
        try:
            # Get all messages from Redis
            all_messages = self.context_cache.get_messages(session_id, limit=100)
            
            if not all_messages:
                logger.warning(f"No messages found for session: {session_id}")
                return False
            
            # Get session info
            session_info = self.get_session(session_id) or {"session_id": session_id}
            
            # Generate final summary
            final_summary = await chat_summarizer.generate_final_summary(
                all_messages=all_messages,
                session_info=session_info
            )
            
            # Save to Firebase
            if self.firebase_sessions:
                success = self.firebase_sessions.end_session_with_summary(
                    session_id=session_id,
                    final_summary=final_summary,
                    reason=reason
                )
                
                if success:
                    logger.info(f"✅ Session {session_id} ended with final summary")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to end session with summary: {e}")
            return False
