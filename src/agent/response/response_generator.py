"""Response Generation Module

Generates LLM responses using retrieved context and conversation history.
"""

import logging
from typing import List, Optional, Dict
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.prompts.prompt_loader import prompt_loader
from src.analytics.tracking import token_tracker  # Updated import

logger = logging.getLogger(__name__)


class ResponseGenerator:
    """Generates responses using LLM with context"""
    
    def __init__(self):
        """Initialize LLM and load prompts"""
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.7
        )
        
        # Load prompts from YAML
        self.system_prompt = prompt_loader.load('system')
        self.response_prompt = prompt_loader.load('response_generator')
        
        logger.info("✅ ResponseGenerator initialized with YAML prompts")
    
    async def generate_response(
        self,
        query: str,
        contexts: List[str],
        conversation_context: str = "",
        session_id: Optional[str] = None,  # For cost tracking
        search_results: Optional[List[Dict]] = None  # NEW: For source attribution
    ) -> str:
        """
        Generate response using LLM with retrieved context

        Args:
            query: User's query
            contexts: List of context strings from search results (DEPRECATED - use search_results)
            conversation_context: Previous conversation history
            session_id: Session ID for cost tracking
            search_results: Raw search results with metadata for source attribution

        Returns:
            Generated response string
        """
        # NEW: Use formatted context with source attribution if search_results provided
        if search_results is not None:
            from src.agent.context import ContextBuilder
            if search_results:  # If not empty
                context_text = ContextBuilder.format_contexts_with_sources(search_results, max_contexts=3)

                # DEBUG: Log formatted KB context with sources
                logger.info(f"🔍 KB Context with source attribution ({len(search_results)} results):")
                for i, r in enumerate(search_results[:3], 1):
                    metadata = r.get("metadata", {})
                    title = (
                        metadata.get("parent_title") or
                        metadata.get("title") or
                        "Untitled"
                    )
                    confidence = r.get("similarity_score", 0.0)
                    logger.info(f"  Source {i}: {title} (confidence: {confidence:.2f})")
            else:
                # Empty search results (e.g., answering from context)
                context_text = "\n\n".join(contexts[:3]) if contexts else "No relevant information found."
                logger.debug("📝 No search results (context-based response)")
        else:
            # FALLBACK: Old format (plain contexts without attribution)
            context_text = "\n\n".join(contexts[:3]) if contexts else "No relevant information found."
            logger.warning("⚠️ Using legacy context format without source attribution")

        # Build full prompt (system + response generation)
        full_prompt = (
            self.system_prompt + "\n\n" +
            self.response_prompt.format(
                conversation_context=conversation_context or "No previous conversation",
                context=context_text,
                query=query
            )
        )

        logger.debug(f"Generating response for: {query[:50]}...")

        response = await self.llm.ainvoke([HumanMessage(content=full_prompt)])

        # Track token usage and cost
        token_tracker.track_chat_usage(
            response=response,
            model=settings.OPENAI_MODEL,
            session_id=session_id,
            operation="response_generation"
        )

        logger.info(f"✅ Response generated ({len(response.content)} chars)")

        return response.content
    
    async def generate_fallback_response(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Generate response when no knowledge base results found

        Args:
            query: User's query
            session_id: Session ID for token tracking

        Returns:
            Fallback response string
        """
        # Use same prompt but with empty context
        full_prompt = (
            self.system_prompt + "\n\n" +
            self.response_prompt.format(
                conversation_context="No previous conversation",
                context="",  # Empty KB content
                query=query
            )
        )

        logger.debug(f"Generating fallback response for: {query[:50]}...")

        response = await self.llm.ainvoke([HumanMessage(content=full_prompt)])

        # Track tokens for fallback response
        if session_id:
            token_tracker.track_chat_usage(
                response=response,
                model=settings.OPENAI_MODEL,
                session_id=session_id,
                operation="response_generation"
            )

        logger.info(f"✅ Fallback response generated")

        return response.content
    
    async def generate_greeting_response(self) -> str:
        """Generate friendly greeting response"""
        return "Hello! I'm here to help you with PropertyEngine. What would you like to know?"
