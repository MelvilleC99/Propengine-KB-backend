"""Context Analyzer - Analyzes conversation context and follow-up queries

UPDATED: Using LLM instead of regex for followup detection
"""

import logging
from typing import Dict, Optional
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.agent.response import ResponseGenerator
from src.memory.session_manager import SessionManager

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """Analyzes conversation context to detect follow-ups and handle context-based responses"""
    
    def __init__(self):
        """Initialize context analyzer with required components"""
        self.response_generator = ResponseGenerator()
        self.session_manager = SessionManager()
        
        # LLM for followup detection
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.3
        )
        
        logger.info("✅ Context analyzer initialized (LLM-powered)")
    
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
            Response dict with full analytics if answerable from context, None otherwise
        """
        if not await self.is_followup_query(query, conversation_context):
            return None
        
        logger.info("📝 Detected follow-up query, attempting to answer from context")
        
        try:
            import time
            start_time = time.time()
            
            response = await self.response_generator.generate_response(
                query, 
                [conversation_context],  # Use context as source
                conversation_context
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Build proper metadata
            metadata = {
                "query_type": "followup",
                "category": "conversation_context",
                "confidence_score": 0.9,
                "sources_found": 1,
                "sources_used": ["Conversation Context"],
                "response_time_ms": elapsed_ms,
                "escalated": False,
                "user_feedback": None
            }
            
            await self.session_manager.add_message(session_id, "assistant", response, metadata)
            
            # Return complete response dict matching orchestrator format
            return {
                "response": response,
                "confidence": 0.9,
                "sources": [{"title": "Conversation Context", "confidence": 0.9}],
                "query_type": "followup",
                "classification_confidence": 1.0,  # We're certain it's a followup
                "requires_escalation": False,
                "search_attempts": [],  # No search needed
                "enhanced_query": query,  # No enhancement
                "query_metadata": {
                    "category": "conversation_context",
                    "intent": "followup",
                    "tags": []
                },
                "debug_metrics": {
                    "from_context": True,
                    "response_time_ms": elapsed_ms
                }
            }
        except Exception as e:
            logger.error(f"Error answering from context: {e}")
            return None
    
    async def is_followup_query(self, query: str, conversation_context: str) -> bool:
        """
        Detect if query is a follow-up question using LLM
        
        Args:
            query: User's query
            conversation_context: Previous conversation history
            
        Returns:
            True if follow-up, False otherwise
        """
        if not conversation_context.strip():
            return False
        
        # Check if context has meaningful content (not just errors)
        if "encountered an error" in conversation_context.lower() and len(conversation_context) < 300:
            logger.debug("Context contains only errors, treating as new query")
            return False
        
        # Use LLM to detect followup
        prompt = f"""Previous conversation:
{conversation_context}

New user query: "{query}"

Is this a follow-up question about the same topic as the conversation above?

IMPORTANT:
- If the conversation above only has errors or apologies, answer "no"
- If this seems like a brand new question unrelated to conversation, answer "no"  
- Only answer "yes" if the user is clearly continuing the same topic

Consider these as follow-ups:
- Requests for "more", "other", "additional" information about SAME topic
- Questions about specific parts mentioned before ("what about step 3?")
- Clarifications about something already discussed ("why is that?")
- Short questions that reference the previous topic ("how?", "when?")

Answer with just: yes or no"""

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            answer = response.content.strip().lower()
            
            is_followup = answer.startswith("yes")
            logger.debug(f"Followup detection: query='{query[:50]}', context_len={len(conversation_context)}, result={is_followup}")
            
            return is_followup
            
        except Exception as e:
            logger.error(f"Error in followup detection: {e}")
            # Fallback to simple heuristic
            return self._simple_followup_check(query, conversation_context)
    
    def _simple_followup_check(self, query: str, context: str) -> bool:
        """Simple fallback for followup detection if LLM fails"""
        query_lower = query.lower()
        
        # Simple keywords that usually indicate followup
        followup_words = ['other', 'more', 'another', 'else', 'also', 'what about', 'how about']
        
        # Short questions with followup words
        if len(query.split()) <= 8:
            if any(word in query_lower for word in followup_words):
                return True
        
        return False
