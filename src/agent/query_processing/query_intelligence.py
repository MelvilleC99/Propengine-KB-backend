"""Query Intelligence - Unified query analysis with follow-up detection

Combines multiple analysis steps into a single LLM call:
- Follow-up detection
- Context answering capability
- Related document matching
- Query enhancement
- Routing decision

Replaces separate follow-up detection + query enhancement to reduce latency.
"""

import logging
import json
from typing import Dict, Optional, List
from dataclasses import dataclass
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
from src.config.settings import settings
from src.analytics.tracking import token_tracker
from .query_builder import StructuredQuery

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysis:
    """Complete query analysis with routing decision"""

    # Follow-up analysis
    is_followup: bool
    can_answer_from_context: bool
    matched_related_doc: Optional[str]

    # Routing decision
    routing: str  # "answer_from_context", "search_kb_targeted", "full_rag"

    # Enhanced query (for search if needed)
    structured_query: StructuredQuery

    # Metadata
    confidence: float


class QueryIntelligence:
    """Intelligent query analysis - single LLM call for everything"""

    def __init__(self):
        """Initialize LLM"""
        self.llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            temperature=0.3
        )
        logger.info("✅ Query Intelligence initialized")

    async def analyze(
        self,
        query: str,
        query_type: str,
        conversation_context: str = "",
        available_related_docs: List[str] = None,
        session_id: Optional[str] = None
    ) -> QueryAnalysis:
        """
        Analyze query with single LLM call - intelligent and efficient

        Args:
            query: User's query
            query_type: Classified type (howto, error, etc.)
            conversation_context: Previous conversation
            available_related_docs: Related documents from previous responses
            session_id: Session for cost tracking

        Returns:
            QueryAnalysis with routing decision and enhanced query
        """
        # Build context sections
        has_context = bool(conversation_context.strip())
        has_related = bool(available_related_docs)

        # Build smart, concise prompt (no keyword bloat)
        prompt = self._build_analysis_prompt(
            query=query,
            query_type=query_type,
            conversation_context=conversation_context if has_context else None,
            related_docs=available_related_docs if has_related else None
        )

        try:
            # Single LLM call for everything
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])

            # Track tokens
            token_tracker.track_chat_usage(
                response=response,
                model=settings.OPENAI_MODEL,
                session_id=session_id,
                operation="query_intelligence"
            )

            # Parse response
            analysis_data = self._parse_response(response.content)

            # Build StructuredQuery from analysis
            structured_query = StructuredQuery(
                original=query,
                enhanced=analysis_data.get("enhanced_query", query),
                query_type=query_type,
                category=analysis_data.get("category", "unknown"),
                tags=analysis_data.get("tags", []),
                user_intent=analysis_data.get("intent", "search")
            )

            # Build QueryAnalysis
            return QueryAnalysis(
                is_followup=analysis_data.get("is_followup", False),
                can_answer_from_context=analysis_data.get("can_answer_from_context", False),
                matched_related_doc=analysis_data.get("matched_related_doc"),
                routing=analysis_data.get("routing", "full_rag"),
                structured_query=structured_query,
                confidence=analysis_data.get("confidence", 0.8)
            )

        except Exception as e:
            logger.error(f"Query intelligence error: {e}")
            # Fallback to basic analysis
            return self._fallback_analysis(query, query_type)

    def _build_analysis_prompt(
        self,
        query: str,
        query_type: str,
        conversation_context: Optional[str],
        related_docs: Optional[List[str]]
    ) -> str:
        """Build intelligent analysis prompt without keyword bloat"""

        prompt_parts = [
            "Analyze this user query and provide a routing decision.",
            "",
            f"Query: \"{query}\"",
            f"Type: {query_type}",
        ]

        # Add conversation context if available
        if conversation_context:
            prompt_parts.extend([
                "",
                "Previous conversation:",
                conversation_context
            ])

        # Add related docs if available
        if related_docs:
            docs_list = "\n".join([f"  - {doc}" for doc in related_docs])
            prompt_parts.extend([
                "",
                "Related documents from previous responses:",
                docs_list
            ])

        # Analysis instructions (concise, intelligent)
        prompt_parts.extend([
            "",
            "Determine:",
            "1. Is this a follow-up to the conversation above? (true/false)",
            "2. Can it be answered using ONLY the conversation history? (true/false)",
            "3. Does it match any related document by topic? (document title or null)",
            "4. What's the best route:",
            "   - answer_from_context: Answer exists in conversation",
            "   - search_kb_targeted: Matches a related document",
            "   - full_rag: Needs fresh knowledge base search",
            "",
            "5. Enhance the query for search (if route needs KB):",
            "   - Add context from conversation",
            "   - Clarify intent",
            "   - Keep it concise",
            "",
            "6. Extract:",
            "   - category: main topic area",
            "   - intent: what user wants to accomplish",
            "   - tags: key concepts (max 3)",
            "",
            "Respond with JSON:",
            "{",
            '  "is_followup": true/false,',
            '  "can_answer_from_context": true/false,',
            '  "matched_related_doc": "title" or null,',
            '  "routing": "answer_from_context" | "search_kb_targeted" | "full_rag",',
            '  "enhanced_query": "...",',
            '  "category": "...",',
            '  "intent": "...",',
            '  "tags": [...],',
            '  "confidence": 0.0-1.0',
            "}"
        ])

        return "\n".join(prompt_parts)

    def _parse_response(self, response_text: str) -> Dict:
        """Parse LLM response (handles markdown code blocks)"""
        try:
            # Remove markdown code blocks if present
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end != -1:
                    response_text = response_text[start:end].strip()

            # Parse JSON
            return json.loads(response_text.strip())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse query intelligence response: {e}")
            logger.debug(f"Response was: {response_text[:200]}")
            return {}

    def _fallback_analysis(self, query: str, query_type: str) -> QueryAnalysis:
        """Fallback when LLM analysis fails"""
        logger.warning("Using fallback query analysis")

        return QueryAnalysis(
            is_followup=False,
            can_answer_from_context=False,
            matched_related_doc=None,
            routing="full_rag",
            structured_query=StructuredQuery(
                original=query,
                enhanced=query,
                query_type=query_type,
                category="unknown",
                tags=[],
                user_intent="search"
            ),
            confidence=0.5
        )
