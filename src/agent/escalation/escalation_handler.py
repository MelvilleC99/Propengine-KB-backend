"""
Escalation Handler - Determines when and how to escalate queries

Handles three escalation scenarios:
1. No results found (immediate escalation offer)
2. Low confidence with results (asks if answer helps first)
3. User explicitly requests human help (immediate escalation)
"""

import logging
from typing import Dict, Optional, List
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings

logger = logging.getLogger(__name__)


class EscalationHandler:
    """Handles escalation logic and reasoning"""
    
    def __init__(self):
        """Initialize LLM for intent detection"""
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.3  # Low temperature for consistent detection
        )
        
        logger.info("✅ EscalationHandler initialized")
    
    async def check_escalation(
        self,
        query: str,
        results: List[Dict],
        confidence: float,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Check if query requires escalation and determine response strategy
        
        Args:
            query: User's query
            results: Search results found
            confidence: Best similarity score
            conversation_history: Recent conversation for context
            
        Returns:
            {
                "should_escalate": bool,
                "escalation_reason": str,
                "escalation_type": str,  # "immediate", "conditional", "none"
                "response_strategy": str  # "offer_ticket", "ask_if_helps", "none"
            }
        """
        # Scenario 1: User explicitly requests human help
        user_requested = await self._detect_escalation_request(query, conversation_history)
        if user_requested:
            return {
                "should_escalate": True,
                "escalation_reason": "user_requested",
                "escalation_type": "immediate",
                "response_strategy": "offer_ticket"
            }
        
        # Scenario 2: No results found
        if not results or len(results) == 0:
            return {
                "should_escalate": True,
                "escalation_reason": "no_results_found",
                "escalation_type": "immediate",
                "response_strategy": "offer_ticket"
            }
        
        # Scenario 3: Low confidence (< 0.7) with results
        if confidence < settings.MIN_CONFIDENCE_SCORE:
            return {
                "should_escalate": True,
                "escalation_reason": "low_confidence",
                "escalation_type": "conditional",  # Only escalate if user confirms answer didn't help
                "response_strategy": "ask_if_helps"
            }
        
        # Scenario 4: Good confidence, no escalation needed
        return {
            "should_escalate": False,
            "escalation_reason": "none",
            "escalation_type": "none",
            "response_strategy": "none"
        }
    
    async def _detect_escalation_request(
        self, 
        query: str, 
        conversation_history: Optional[List[Dict]] = None
    ) -> bool:
        """
        Use LLM to detect if user is requesting human help
        
        Args:
            query: Current user query
            conversation_history: Recent messages for context
            
        Returns:
            bool: True if user wants human help
        """
        # Build context from history
        context = ""
        if conversation_history:
            recent = conversation_history[-3:]  # Last 3 messages
            context = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
                for msg in recent
            ])
        
        prompt = f"""Analyze this user message and determine if they are requesting to speak with a human agent or raise a support ticket.

Conversation Context:
{context if context else "No previous context"}

Current User Message:
{query}

User is requesting escalation if they:
- Explicitly ask to speak with a human/agent/support
- Ask to create/raise/submit a ticket
- Say the bot isn't helping and want human help
- Express frustration and want to escalate
- Say "yes" after being asked if they want to raise a ticket

User is NOT requesting escalation if they:
- Just have a question (even if phrased negatively)
- Are clarifying or asking follow-ups
- Say "no" to escalation offers

Return ONLY "YES" or "NO" (no other text).
"""
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            answer = response.content.strip().upper()
            
            is_escalation_request = answer == "YES"
            
            if is_escalation_request:
                logger.info(f"🎫 Escalation request detected: {query[:50]}...")
            
            return is_escalation_request
            
        except Exception as e:
            logger.error(f"Error detecting escalation request: {e}")
            # Fail safe: don't escalate if detection fails
            return False
    
    def format_escalation_response(
        self,
        base_response: str,
        escalation_info: Dict
    ) -> str:
        """
        Format response based on escalation strategy
        
        Args:
            base_response: The main agent response
            escalation_info: Dict from check_escalation()
            
        Returns:
            str: Formatted response with appropriate escalation message
        """
        escalation_type = escalation_info.get("escalation_type")
        strategy = escalation_info.get("response_strategy")
        
        # Immediate escalation (no results or user requested)
        if escalation_type == "immediate" and strategy == "offer_ticket":
            if escalation_info.get("escalation_reason") == "user_requested":
                return "I'll help you raise a support ticket right away. Our team will get back to you shortly. Would you like to proceed?"
            else:
                return f"{base_response}\n\nI don't have enough information to fully answer this. Would you like me to create a support ticket so our team can help you directly?"
        
        # Conditional escalation (low confidence - ask if answer helps)
        if escalation_type == "conditional" and strategy == "ask_if_helps":
            return f"{base_response}\n\nDoes this help answer your question, or would you like me to create a support ticket for more detailed assistance?"
        
        # No escalation needed
        return base_response
    
    def get_escalation_metadata(self, escalation_info: Dict) -> Dict:
        """
        Get metadata for analytics tracking
        
        Args:
            escalation_info: Dict from check_escalation()
            
        Returns:
            Dict with escalation metadata
        """
        return {
            "escalated": escalation_info.get("should_escalate", False),
            "escalation_reason": escalation_info.get("escalation_reason", "none"),
            "escalation_type": escalation_info.get("escalation_type", "none"),
            "response_strategy": escalation_info.get("response_strategy", "none")
        }
