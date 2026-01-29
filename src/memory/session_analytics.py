"""
Session Analytics Management
Handles query buffering and batch analytics writing to Firebase
"""

from typing import Dict, List, Optional
from datetime import datetime
import logging
from src.analytics.tracking import token_tracker  # Updated import

logger = logging.getLogger(__name__)


class SessionAnalytics:
    """
    Manages analytics collection and batch writing for sessions
    
    Responsibilities:
    - Buffer query metadata during session (no Firebase writes)
    - Batch write all analytics when session ends
    - Update user activity and statistics
    """
    
    def __init__(self):
        """Initialize analytics manager"""
        # Query buffer for collecting analytics in memory (no Firebase writes during session)
        self.query_buffers = {}  # session_id -> List[query_data]
        
        # Store user info for each session (needed for user document creation)
        self.session_users = {}  # session_id -> user_info
        
        # Lazy-loaded Firebase services
        self._firebase_analytics = None
        self._firebase_users = None
        
        logger.info("SessionAnalytics initialized")
    
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
    
    def store_user_info(self, session_id: str, user_info: Dict) -> None:
        """
        Store user info for a session
        
        Args:
            session_id: Session identifier
            user_info: User information dict
        """
        self.session_users[session_id] = user_info
        logger.debug(f"Stored user info for session {session_id}")
    
    def buffer_query_metadata(
        self, 
        session_id: str, 
        query_text: str,
        response_text: str,
        metadata: Dict
    ) -> None:
        """
        Buffer query metadata in memory (no Firebase write yet)
        
        Args:
            session_id: Session identifier
            query_text: User's question
            response_text: Assistant's response
            metadata: Query metadata (confidence, sources, etc.)
        """
        if session_id not in self.query_buffers:
            self.query_buffers[session_id] = []
        
        self.query_buffers[session_id].append({
            "query_text": query_text,
            "response_text": response_text,
            "timestamp": datetime.now().isoformat(),
            **metadata  # Include all metadata (confidence, sources, etc.)
        })
        
        buffer_size = len(self.query_buffers[session_id])
        logger.debug(f"📊 Buffered query metadata for session {session_id} (total: {buffer_size})")
    
    def get_buffered_queries(self, session_id: str) -> List[Dict]:
        """
        Get all buffered queries for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of query metadata dicts
        """
        return self.query_buffers.get(session_id, [])
    
    def get_query_count(self, session_id: str) -> int:
        """
        Get count of buffered queries for a session
        
        Args:
            session_id: Session identifier
            
        Returns:
            Number of buffered queries
        """
        return len(self.query_buffers.get(session_id, []))
    
    async def write_session_analytics(
        self,
        session_id: str,
        agent_id: str
    ) -> bool:
        """
        Write all buffered analytics to Firebase in ONE batch
        
        Args:
            session_id: Session to write analytics for
            agent_id: User's agent ID (e.g., BID-VXDZgFkHqzphyrg)
            
        Returns:
            bool: Success status
        """
        try:
            # Get buffered queries
            queries = self.query_buffers.get(session_id, [])
            
            if not queries:
                logger.warning(f"No queries to write for session {session_id}")
                return False
            
            # Get session costs from token_tracker
            session_costs = token_tracker.get_session_costs(session_id)
            
            logger.info(f"📊 Writing {len(queries)} queries for session {session_id}")
            
            # Write analytics batch (including costs)
            if self.firebase_analytics:
                await self.firebase_analytics.batch_write_analytics(
                    session_id=session_id,
                    agent_id=agent_id,
                    queries=queries,
                    session_costs=session_costs  # ← ADD costs
                )
                logger.info(f"✅ Analytics written for session {session_id}")
            
            # Get user info for this session
            user_data = self.session_users.get(session_id)
            
            # Update user stats (creates user if doesn't exist)
            # Include total cost for this session
            total_cost = session_costs.get("total_cost", 0.0) if session_costs else 0.0
            
            if self.firebase_users:
                await self.firebase_users.update_user_activity(
                    agent_id=agent_id,
                    num_queries=len(queries),
                    user_data=user_data,
                    total_cost=total_cost  # ← ADD cost
                )
                logger.info(f"✅ User activity updated for {agent_id} (cost: ${total_cost:.6f})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to write analytics for session {session_id}: {e}", exc_info=True)
            return False
    
    async def add_session_to_user_history(
        self,
        session_id: str,
        agent_id: str,
        summary: str
    ) -> bool:
        """
        Add session to user's recent sessions
        
        Args:
            session_id: Session identifier
            agent_id: User's agent ID
            summary: Session summary text
            
        Returns:
            bool: Success status
        """
        try:
            if self.firebase_users:
                await self.firebase_users.add_recent_session(
                    agent_id=agent_id,
                    session_summary={
                        "session_id": session_id,
                        "date": datetime.now().isoformat(),
                        "summary": summary[:200]  # Truncate to 200 chars
                    }
                )
                logger.info(f"✅ Added session to user history for {agent_id}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to add session to user history: {e}", exc_info=True)
            return False
    
    def clear_session_data(self, session_id: str) -> None:
        """
        Clear all buffered data for a session
        
        Args:
            session_id: Session to clear
        """
        # Clear query buffer
        if session_id in self.query_buffers:
            del self.query_buffers[session_id]
            logger.debug(f"Cleared query buffer for session {session_id}")
        
        # Clear user info
        if session_id in self.session_users:
            del self.session_users[session_id]
            logger.debug(f"Cleared user info for session {session_id}")
    
    def get_stats(self) -> Dict:
        """
        Get current analytics manager statistics
        
        Returns:
            Dict with current stats
        """
        total_queries = sum(len(queries) for queries in self.query_buffers.values())
        
        return {
            "active_sessions": len(self.query_buffers),
            "total_buffered_queries": total_queries,
            "sessions_with_user_info": len(self.session_users)
        }
