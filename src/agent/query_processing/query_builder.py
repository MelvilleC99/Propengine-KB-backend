"""Query Builder Module

Uses LLM to analyze queries and build structured metadata for search.
"""

import logging
import json
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.prompts.prompt_loader import prompt_loader
from src.analytics.tracking import token_tracker  # Updated import
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StructuredQuery:
    """Structured query with metadata"""
    original: str
    enhanced: str
    query_type: str
    category: Optional[str] = None
    subcategory: Optional[str] = None
    tags: List[str] = None
    user_intent: Optional[str] = None
    search_keywords: List[str] = None


class QueryBuilder:
    """Builds structured queries using LLM analysis"""
    
    def __init__(self):
        """Initialize LLM and load prompts"""
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.3  # Lower temperature for consistent analysis
        )
        
        # Load prompts from YAML
        self.system_prompt = prompt_loader.load('system')
        self.query_prompt = prompt_loader.load('query_builder')
        
        logger.info("✅ QueryBuilder initialized with YAML prompts")
    
    async def build(
        self, 
        query: str, 
        query_type: str,
        conversation_context: str = ""
    ) -> StructuredQuery:
        """
        Build structured query using LLM analysis
        
        Args:
            query: Original user query
            query_type: Classified query type (error, definition, etc.)
            conversation_context: Previous conversation for context
            
        Returns:
            StructuredQuery with metadata
        """
        # Skip analysis for very short queries
        if len(query.split()) <= 2:
            logger.debug(f"Skipping LLM analysis for short query: {query}")
            return self._build_simple(query, query_type)
        
        try:
            # Build full prompt (system + query analysis)
            full_prompt = (
                self.system_prompt + "\n\n" +
                self.query_prompt.format(
                    query=query,
                    query_type=query_type,
                    context=conversation_context or "None"
                )
            )
            
            logger.debug(f"Analyzing query: {query}")
            
            # Call LLM
            response = await self.llm.ainvoke([HumanMessage(content=full_prompt)])
            
            # Track token usage
            token_tracker.track_chat_usage(
                response=response,
                model=settings.OPENAI_MODEL,
                session_id=None,  # Will be added by caller if needed
                operation="query_enhancement"
            )
            
            # Parse JSON response
            response_text = response.content.strip()
            
            # Log raw response for debugging
            logger.debug(f"Raw LLM response (first 300 chars): {response_text[:300]}")
            
            # More aggressive cleanup
            # 1. Remove markdown code blocks
            if "```json" in response_text:
                # Extract content between ```json and ```
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                # Extract content between ``` and ```
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()
            
            # 2. Remove any leading/trailing text before/after JSON
            # Find the FIRST { and LAST }
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            
            if first_brace == -1 or last_brace == -1:
                raise ValueError(f"No valid JSON object found in response")
            
            response_text = response_text[first_brace:last_brace+1]
            
            # 3. Final cleanup
            response_text = response_text.strip()
            
            # Log cleaned JSON before parsing
            logger.debug(f"Cleaned JSON (first 300 chars): {response_text[:300]}")
            
            structured_data = json.loads(response_text)
            
            logger.info(
                f"✅ Query analyzed: '{query}' → "
                f"category={structured_data.get('category')}, "
                f"intent={structured_data.get('user_intent')}"
            )
            
            return StructuredQuery(
                original=query,
                enhanced=structured_data.get("enhanced_query", query),
                query_type=query_type,
                category=structured_data.get("category"),
                subcategory=structured_data.get("subcategory"),
                tags=structured_data.get("tags", []),
                user_intent=structured_data.get("user_intent"),
                search_keywords=structured_data.get("search_keywords", [])
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            logger.error(f"Raw response: {response.content if 'response' in locals() else 'N/A'}")
            logger.error(f"Attempted to parse: {response_text if 'response_text' in locals() else 'N/A'}")
            return self._build_simple(query, query_type)
        
        except Exception as e:
            logger.error(f"Error in query analysis: {e}")
            logger.error(f"Raw response: {response.content if 'response' in locals() else 'N/A'}")
            return self._build_simple(query, query_type)
    
    def _build_simple(self, query: str, query_type: str) -> StructuredQuery:
        """Fallback: Build simple structured query without LLM"""
        return StructuredQuery(
            original=query,
            enhanced=query,
            query_type=query_type,
            category=None,
            subcategory=None,
            tags=[],
            user_intent=query_type,
            search_keywords=query.lower().split()
        )
