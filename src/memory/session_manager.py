"""
Session Orchestrator - Coordinates all session management components
Uses Redis for caching, Firebase for persistence, and memory for fallback
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging

from src.database.firebase_session_service import FirebaseSessionManager
from src.memory.redis_message_store import RedisContextCache
from src.memory.session_analytics import SessionAnalytics
from src.memory.session_fallback import SessionFallback
from src.utils.chat_summary import chat_summarizer

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Orchestrates session management across multiple storage layers
    
    Architecture:
    - Redis: Fast message cache (via RedisContextCache)
    - Firebase: Persistent storage (via FirebaseSessionManager)
    - Analytics: Query buffering and batch writing (via SessionAnalytics)
    - Fallback: In-memory backup (via SessionFallback)
    
    Responsibilities:
    - Coordinate session lifecycle (create/end)
    - Route messages to appropriate storage
    - Manage rolling summaries
    - Orchestrate batch analytics writing
    """
    
    def __init__(self):
        """Initialize session orchestrator with all components"""
        # Core components
        self.context_cache = RedisContextCache()  # Redis message store
        self.analytics = SessionAnalytics()  # Analytics buffering
        self.fallback = SessionFallback()  # In-memory backup
        
        # Firebase (lazy loaded)
        self._firebase_sessions = None
        
        # Rolling summary configuration
        self.summary_interval = 5  # Generate summary every 5 messages
        self.summary_counter = {}  # session_id -> messages since last summary
        
        logger.info("SessionManager initialized (orchestrator mode)")
    
    @property
    def firebase_sessions(self):
        """Lazy load Firebase session manager"""
        if self._firebase_sessions is None:
            try:
                self._firebase_sessions = FirebaseSessionManager()
                logger.info("✅ Firebase session manager connected")
            except Exception as e:
                logger.warning(f"⚠️ Firebase session manager unavailable: {e}")
                self._firebase_sessions = None
        return self._firebase_sessions
    
    # ==================== SESSION LIFECYCLE ====================
    
    def create_session(self, user_info: Optional[Dict] = None) -> str:
        """
        Create a new session
        
        Args:
            user_info: Optional user information
            
        Returns:
            str: Session ID
        """
        try:
            # Try Firebase first
            session_id = self.firebase_sessions.create_session(user_info)
            
            # Store user info for analytics
            if user_info:
                self.analytics.store_user_info(session_id, user_info)
            
            logger.info(f"✅ Created Firebase session: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"❌ Firebase session creation failed: {e}")
            # Fallback to in-memory
            session_id = self.fallback.create_session(user_info)
            if user_info:
                self.analytics.store_user_info(session_id, user_info)
            return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """
        Get session information
        
        Args:
            session_id: Session to retrieve
            
        Returns:
            Session dict or None
        """
        try:
            # Try Firebase first
            session = self.firebase_sessions.get_session(session_id)
            if session:
                return session
        except Exception as e:
            logger.error(f"❌ Firebase session lookup failed: {e}")
        
        # Fallback to in-memory
        return self.fallback.get_session(session_id)
    
    # ==================== MESSAGE HANDLING ====================
    
    async def add_message(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Add message to session (Redis cache + analytics buffer)
        
        Args:
            session_id: Session identifier
            role: "user" or "assistant"
            content: Message content
            metadata: Optional metadata (confidence, sources, etc.)
            
        Returns:
            bool: Success status
        """
        try:
            # 1. Add to Redis cache (immediate, fast)
            cache_success = self.context_cache.add_message(session_id, role, content, metadata)
            
            # 2. Buffer query metadata for analytics (if assistant response)
            if role == "assistant" and metadata:
                # Get previous user message
                messages = self.context_cache.get_messages(session_id, limit=2)
                user_query = messages[-2].get("content") if len(messages) >= 2 else "Unknown query"
                
                # Buffer the query metadata
                self.analytics.buffer_query_metadata(
                    session_id=session_id,
                    query_text=user_query,
                    response_text=content,
                    metadata=metadata
                )
            
            # 3. Update rolling summary if needed
            self.summary_counter[session_id] = self.summary_counter.get(session_id, 0) + 1
            if self._should_update_summary(session_id):
                await self._update_rolling_summary(session_id)
                self.summary_counter[session_id] = 0
            
            return cache_success
            
        except Exception as e:
            logger.error(f"❌ Error adding message to session {session_id}: {e}")
            # Fallback to in-memory
            return self.fallback.add_message(session_id, role, content)
    
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """
        Get conversation history
        
        Args:
            session_id: Session identifier
            limit: Maximum messages to return
            
        Returns:
            List of recent messages
        """
        try:
            # Try Redis first (fastest)
            messages = self.context_cache.get_messages(session_id, limit)
            if messages:
                return messages
        except Exception as e:
            logger.error(f"❌ Redis history lookup failed: {e}")
        
        try:
            # Try Firebase
            messages = self.firebase_sessions.get_recent_messages(session_id, limit)
            if messages:
                return messages
        except Exception as e:
            logger.error(f"❌ Firebase history lookup failed: {e}")
        
        # Final fallback to in-memory
        return self.fallback.get_history(session_id, limit)
    
    # ==================== CONTEXT FOR LLM ====================
    
    def get_context_for_llm(self, session_id: str) -> Dict:
        """
        Get optimized context for LLM (messages + rolling summary)
        
        Args:
            session_id: Session identifier
            
        Returns:
            {
                "messages": [...],
                "summary": {...},
                "has_summary": bool,
                "formatted_context": str
            }
        """
        context = self.context_cache.get_context_with_summary(session_id, max_messages=5)
        formatted = self._format_context_for_llm(context)
        
        return {
            **context,
            "formatted_context": formatted
        }
    
    def _format_context_for_llm(self, context: Dict) -> str:
        """Format context into readable text for LLM prompt with KB source awareness"""
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

        # Add recent messages WITH KB source attribution
        if context.get("messages"):
            lines.append("=== RECENT MESSAGES ===")
            for msg in context["messages"]:
                role = msg.get("role", "unknown").upper()
                content = msg.get("content", "")
                metadata = msg.get("metadata", {})

                # Build message line
                message_line = f"{role}: {content}"

                # NEW: Add KB source info for assistant responses
                if role == "ASSISTANT" and metadata.get("sources_used"):
                    sources = metadata.get("sources_used", [])
                    confidence = metadata.get("confidence_score", 0.0)
                    related_docs = metadata.get("related_documents", [])

                    # Add source attribution
                    if sources:
                        source_names = ", ".join(sources[:3])  # Limit to 3
                        message_line += f"\n   📚 Sources: {source_names} (confidence: {confidence:.2f})"

                    # Add related documents for follow-up awareness
                    if related_docs:
                        related_names = ", ".join(related_docs[:5])  # Limit to 5
                        message_line += f"\n   📌 Related: {related_names}"

                lines.append(message_line)

        return "\n".join(lines)
    
    # ==================== ROLLING SUMMARIES ====================
    
    def _should_update_summary(self, session_id: str) -> bool:
        """Check if rolling summary should be updated"""
        count = self.summary_counter.get(session_id, 0)
        return count >= self.summary_interval
    
    async def _update_rolling_summary(self, session_id: str) -> None:
        """Generate and store rolling summary"""
        try:
            logger.info(f"🔄 Generating rolling summary for session: {session_id}")
            
            # Get previous summary (if exists)
            previous_summary = self.context_cache.get_rolling_summary(session_id)
            prev_text = previous_summary.get("summary", "") if previous_summary else None
            
            # Get recent messages
            recent_messages = self.context_cache.get_messages(session_id, limit=self.summary_interval)
            
            if not recent_messages:
                return
            
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
                f"   Summary: {summary_data.get('summary', '')[:100]}..."
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to update rolling summary: {e}", exc_info=True)
    
    # ==================== SESSION ENDING ====================
    
    async def end_session_with_analytics(
        self,
        session_id: str,
        agent_id: str,
        reason: str = "completed"
    ) -> bool:
        """
        End session with batch analytics write
        
        Args:
            session_id: Session to end
            agent_id: User's agent ID
            reason: End reason
            
        Returns:
            bool: Success status
        """
        try:
            logger.info(f"🔚 Ending session {session_id} for agent {agent_id} (reason: {reason})")
            
            # 1. Get all messages for final summary
            all_messages = self.context_cache.get_messages(session_id, limit=100)
            
            if not all_messages:
                logger.warning(f"No messages found for session: {session_id}")
                return False
            
            # 2. Generate final summary
            session_info = self.get_session(session_id) or {"session_id": session_id}
            final_summary = await chat_summarizer.generate_final_summary(
                all_messages=all_messages,
                session_info=session_info
            )
            
            # 3. Write session summary to Firebase
            if self.firebase_sessions:
                success = self.firebase_sessions.end_session_with_summary(
                    session_id=session_id,
                    final_summary=final_summary,
                    reason=reason
                )
                
                if success:
                    logger.info(f"✅ Session summary written")
            
            # 4. Write analytics batch
            await self.analytics.write_session_analytics(
                session_id=session_id,
                agent_id=agent_id
            )
            
            # 5. Add to user history
            await self.analytics.add_session_to_user_history(
                session_id=session_id,
                agent_id=agent_id,
                summary=final_summary.get("summary", "")
            )
            
            # 6. Cleanup all buffers
            self.context_cache.clear_session(session_id)
            self.analytics.clear_session_data(session_id)
            
            if session_id in self.summary_counter:
                del self.summary_counter[session_id]
            
            logger.info(f"✅ Session {session_id} ended successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to end session: {e}", exc_info=True)
            return False
    
    async def end_session_with_summary(self, session_id: str, reason: str = "completed") -> bool:
        """
        End session with summary (simpler version without full analytics)
        
        Args:
            session_id: Session to end
            reason: End reason
            
        Returns:
            bool: Success status
        """
        try:
            all_messages = self.context_cache.get_messages(session_id, limit=100)
            
            if not all_messages:
                logger.warning(f"No messages found for session: {session_id}")
                return False
            
            session_info = self.get_session(session_id) or {"session_id": session_id}
            final_summary = await chat_summarizer.generate_final_summary(
                all_messages=all_messages,
                session_info=session_info
            )
            
            if self.firebase_sessions:
                success = self.firebase_sessions.end_session_with_summary(
                    session_id=session_id,
                    final_summary=final_summary,
                    reason=reason
                )
                
                if success:
                    logger.info(f"✅ Session {session_id} ended with summary")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to end session with summary: {e}")
            return False
    
    # ==================== UTILITY METHODS ====================
    
    def update_metadata(self, session_id: str, key: str, value) -> bool:
        """Update session metadata (fallback sessions only)"""
        return self.fallback.update_metadata(session_id, key, value)
    
    def get_active_sessions(self) -> List[Dict]:
        """Get count of active sessions"""
        try:
            firebase_count = self.firebase_sessions.get_active_sessions_count() if self.firebase_sessions else 0
            memory_count = self.fallback.get_active_sessions_count()
            
            return [{
                "firebase_sessions": firebase_count,
                "memory_sessions": memory_count,
                "total_sessions": firebase_count + memory_count
            }]
        except Exception as e:
            logger.error(f"❌ Error getting active sessions: {e}")
            return []
    
    def clear_expired_sessions(self):
        """Clear expired in-memory sessions"""
        return self.fallback.clear_expired_sessions()
