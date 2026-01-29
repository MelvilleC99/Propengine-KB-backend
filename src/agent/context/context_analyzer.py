"""Context Analyzer - Analyzes conversation context and follow-up queries

Extracted from orchestrator.py to keep logic modular.
"""

import re
import logging
from typing import Dict, Optional
from src.agent.response import ResponseGenerator
from src.memory.session_manager import SessionManager

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """Analyzes conversation context to detect follow-ups and handle context-based responses"""
    
    def __init__(self):
        """Initialize context analyzer with required components"""
        self.response_generator = ResponseGenerator()
        self.session_manager = SessionManager()
        
        logger.info("✅ Context analyzer initialized")
    
    async def try_answer_from_context(
        self, 
        query: str, 
        conversation_context: str, 
        session_id: str
    ) -> Optional[Dict]:
        """
        Try to answer from conversation context if it's a follow-up
        
        Args:
            query: User's query
            conversation_context: Previous conversation history
            session_id: Session identifier
            
        Returns:
            Response dict if answerable from context, None otherwise
        """
        if not self.is_followup_query(query, conversation_context):
            return None
        
        logger.info("📝 Detected follow-up query, attempting to answer from context")
        
        try:
            response = await self.response_generator.generate_response(
                query, 
                [conversation_context],  # Use context as source
                conversation_context
            )
            
            await self.session_manager.add_message(session_id, "assistant", response)
            
            return {
                "response": response,
                "confidence": 0.9,
                "sources": [{"title": "Conversation Context", "confidence": 0.9}],
                "query_type": "followup",
                "from_context": True
            }
        except Exception as e:
            logger.error(f"Error answering from context: {e}")
            return None
    
    def is_followup_query(self, query: str, conversation_context: str) -> bool:
        """
        Detect if query is a follow-up question
        
        Args:
            query: User's query
            conversation_context: Previous conversation history
            
        Returns:
            True if follow-up, False otherwise
        """
        if not conversation_context.strip():
            return False
        
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        
        # Follow-up indicators (regex patterns)
        followup_patterns = [
            r'\bso\b.*\bonly\b',
            r'\bso\b.*\bjust\b',
            r'\bthat\s+(means|is)\b',
            r'^\s*(only|just|so)\b',
            r'\byes\b.*\?',
            r'\band\b.*\?',
            r'\bwhat about\b',
            r'\bhow about\b',
            r'\bwhy\s+(only|not|just)\b',
        ]
        
        for pattern in followup_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"Follow-up detected (pattern: {pattern})")
                return True
        
        # Short queries with pronouns
        if (len(query_words) <= 6 and 
            any(pronoun in query_words for pronoun in ['it', 'that', 'this', 'they'])):
            logger.debug("Follow-up detected (short query with pronoun)")
            return True
        
        return False
