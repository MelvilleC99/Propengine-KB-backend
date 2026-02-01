"""Context Responder - Generates responses from conversation context

When query_intelligence determines a query can be answered from conversation
history alone, this module generates the response without KB lookup.
"""

import logging
import time
from typing import Dict, Optional, TYPE_CHECKING
from src.agent.response import ResponseGenerator
from src.memory.session_manager import SessionManager

if TYPE_CHECKING:
    from src.analytics.collectors.metrics_collector import QueryMetricsCollector

logger = logging.getLogger(__name__)


class ContextResponder:
    """Generates responses from conversation context only"""

    def __init__(self):
        """Initialize with response generator and session manager"""
        self.response_generator = ResponseGenerator()
        self.session_manager = SessionManager()
        logger.info("✅ Context responder initialized")

    async def answer_from_conversation(
        self,
        query: str,
        conversation_context: str,
        session_id: str,
        metrics_collector: Optional['QueryMetricsCollector'] = None
    ) -> Dict:
        """
        Generate response using only conversation context (no KB lookup)

        Args:
            query: User's query
            conversation_context: Previous conversation history
            session_id: Session identifier

        Returns:
            Response dict matching orchestrator format with full metrics
        """
        try:
            start_time = time.time()

            # Start response generation timer if metrics_collector provided
            if metrics_collector:
                metrics_collector._start_timer("response_generation")

            # Generate response from context (pass empty search_results to avoid warning)
            response = await self.response_generator.generate_response(
                query,
                [conversation_context],
                conversation_context,
                session_id=session_id,
                search_results=[]  # No KB search for context-based responses
            )

            # Stop response generation timer
            if metrics_collector:
                metrics_collector.record_response_generation()

            elapsed_ms = (time.time() - start_time) * 1000

            # Build metadata
            metadata = {
                "query_type": "followup",
                "category": "conversation_context",
                "confidence_score": 0.9,
                "sources_found": 1,
                "sources_used": ["Conversation Context"],
                "related_documents": [],
                "response_time_ms": elapsed_ms,
                "escalated": False,
                "user_feedback": None
            }

            # Store in session
            await self.session_manager.add_message(
                session_id,
                "assistant",
                response,
                metadata
            )

            # Return complete response dict
            return {
                "response": response,
                "confidence": 0.9,
                "sources": [{
                    "title": "Conversation Context",
                    "confidence": 0.9,
                    "entry_type": "context",
                    "user_type": "internal",
                    "content_preview": (
                        conversation_context[:200] + "..."
                        if len(conversation_context) > 200
                        else conversation_context
                    ),
                    "metadata": {
                        "title": "Conversation Context",
                        "category": "conversation"
                    }
                }],
                "query_type": "followup",
                "classification_confidence": 1.0,
                "requires_escalation": False,
                "search_attempts": ["conversation_context"],
                "enhanced_query": query,
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
            logger.error(f"Error answering from conversation: {e}")
            return None
