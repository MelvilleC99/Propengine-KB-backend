"""Response Generation Module

Generates LLM responses using retrieved context and conversation history.
"""

import logging
from typing import List
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.prompts.prompt_loader import prompt_loader

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
        conversation_context: str = ""
    ) -> str:
        """
        Generate response using LLM with retrieved context
        
        Args:
            query: User's query
            contexts: List of context strings from search results
            conversation_context: Previous conversation history
            
        Returns:
            Generated response string
        """
        # Use top 3 contexts for response generation
        context_text = "\n\n".join(contexts[:3]) if contexts else "No relevant information found."
        
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
        
        logger.info(f"✅ Response generated ({len(response.content)} chars)")
        
        return response.content
    
    async def generate_fallback_response(self, query: str) -> str:
        """
        Generate response when no knowledge base results found
        
        Args:
            query: User's query
            
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
        
        logger.info(f"✅ Fallback response generated")
        
        return response.content
    
    async def generate_greeting_response(self) -> str:
        """Generate friendly greeting response"""
        return "Hello! I'm here to help you with PropertyEngine. What would you like to know?"
