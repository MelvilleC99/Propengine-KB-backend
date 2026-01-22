"""Query Builder Module

Uses LLM to analyze queries and build structured metadata for search.
"""

import logging
import json
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.prompts.prompt_loader import prompt_loader
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
            
            # Parse JSON response
            response_text = response.content.strip()
            
            # Remove markdown formatting if present
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()
            
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
            logger.debug(f"Response was: {response.content}")
            return self._build_simple(query, query_type)
        
        except Exception as e:
            logger.error(f"Error in query analysis: {e}")
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
