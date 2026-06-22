"""Agent Orchestrator - Coordinates query processing pipeline

OPTIMIZED: Single query intelligence call for follow-up detection + enhancement
- Query intelligence → query_processing/query_intelligence.py (single LLM call)
- Context responder → context/context_responder.py
- Search strategy → search/search_strategy.py
- Parent retrieval → search/parent_retrieval.py
"""

from typing import Dict, Optional
import asyncio
import re
import time
from src.query.vector_search import VectorSearch
from src.query.reranker import SearchReranker
from src.memory.session_manager import SessionManager
from src.memory.kb_analytics import KBAnalyticsTracker
from src.agent.classification import QueryClassifier
from src.agent.query_processing.query_intelligence import QueryIntelligence, QueryAnalysis
from src.agent.context import ContextBuilder
from src.agent.context.context_responder import ContextResponder
from src.agent.search import SearchStrategy, ParentDocumentRetrieval
from src.agent.response import ResponseGenerator
from src.agent.escalation.escalation_handler import EscalationHandler
from src.analytics import QueryMetricsCollector, token_tracker
from src.utils.logging_helper import get_logger

logger = get_logger(__name__)


def _run_in_background(coro, description: str) -> None:
    """Run a coroutine fire-and-forget, but log any error instead of letting it vanish.

    Background tasks started with asyncio.create_task() have no one awaiting them,
    so an exception inside them disappears silently. Wrapping them here ensures any
    failure (e.g. a session write or analytics write) is logged loudly instead.
    """
    async def _wrapper():
        try:
            await coro
        except Exception as e:
            logger.error(f"Background task failed ({description}): {e}", exc_info=True)
    asyncio.create_task(_wrapper())


class Agent:
    """Main agent orchestrator - coordinates the query processing pipeline"""
    
    def __init__(self):
        """Initialize orchestrator with all required components"""
        # Classification & Query Intelligence
        self.classifier = QueryClassifier()
        self.query_intelligence = QueryIntelligence()

        # Metrics Collection
        self.metrics_collector = QueryMetricsCollector()

        # Search & Ranking
        self.vector_search = VectorSearch()
        self.reranker = SearchReranker()
        self.parent_retrieval = ParentDocumentRetrieval(self.vector_search)
        self.search_strategy = SearchStrategy(
            self.vector_search,
            self.metrics_collector
        )

        # Context & Response
        self.context_builder = ContextBuilder()
        self.context_responder = ContextResponder()
        self.response_generator = ResponseGenerator()

        # Escalation decision (single source of truth — pure rules, no LLM)
        self.escalation_handler = EscalationHandler()

        # Memory & Analytics
        self.session_manager = SessionManager()
        self.kb_analytics = KBAnalyticsTracker()

        logger.info("✅ Agent orchestrator initialized (optimized with query intelligence)")

    # === Follow-up detection patterns (fast, local, no LLM) ===
    FOLLOWUP_PATTERNS = [
        r"^(yes|no|yeah|nah|ok|okay|sure|right|exactly)\b",  # Short affirmative/negative
        r"\b(you said|you mentioned|you told me|as you said)\b",
        r"\b(what about|how about|and also|also what|tell me more)\b",
        r"\b(no i meant|i meant|i mean|actually i)\b",
        r"\b(that one|the one you|which one|the same)\b",
        r"\b(can you explain|explain that|more detail|elaborate)\b",
        r"\b(follow.?up|going back to|earlier you)\b",
    ]
    # Pronoun-heavy short queries suggest follow-up (e.g. "what does it do", "is that correct")
    PRONOUN_PATTERN = r"\b(it|that|this|they|those|these|its|their)\b"

    @classmethod
    def _is_likely_followup(cls, query: str, message_count: int, conversation_context: str) -> bool:
        """
        Fast local follow-up detection (<1ms) — no LLM call.

        Returns True if the query looks like a follow-up to existing conversation.
        Uses message_count from Redis + regex patterns on the query text.
        """
        # No conversation history → can't be a follow-up
        if message_count <= 1 or not conversation_context.strip():
            return False

        query_lower = query.lower().strip()

        # Check explicit follow-up patterns
        for pattern in cls.FOLLOWUP_PATTERNS:
            if re.search(pattern, query_lower):
                return True

        # Short query with pronouns (e.g. "what does it cost", "is that for owners")
        word_count = len(query_lower.split())
        if word_count <= 6 and re.search(cls.PRONOUN_PATTERN, query_lower):
            return True

        return False

    def _create_skip_qi_analysis(self, query: str, query_type: str) -> 'QueryAnalysis':
        """
        Create a default QueryAnalysis when skipping the QI LLM call.
        Uses the raw query as-is — no enhancement, no routing override.
        """
        from src.agent.query_processing.query_intelligence import QueryAnalysis
        from src.agent.query_processing.query_builder import StructuredQuery

        return QueryAnalysis(
            is_followup=False,
            can_answer_from_context=False,
            matched_related_doc=None,
            routing="full_rag",
            structured_query=StructuredQuery(
                original=query,
                enhanced=query,  # Raw query — no LLM enhancement
                query_type=query_type,
                category=query_type,
                tags=[],
                user_intent="search"
            ),
            confidence=0.8
        )

    def _build_context_debug(self, session_id, conversation_context, message_count,
                             has_summary, context_length) -> Dict:
        """Build the context-debug block (recent sources + related docs from the last few
        assistant messages). One place, so every response path returns the same debug shape."""
        recent_sources, all_related_docs = [], []
        for msg in self.session_manager.context_cache.get_messages(session_id, limit=5):
            if msg.get("role") == "assistant":
                md = msg.get("metadata", {})
                recent_sources.extend(md.get("sources_used", []) or [])
                all_related_docs.extend(md.get("related_documents", []) or [])
        return {
            "conversation_context": conversation_context,
            "message_count": message_count,
            "has_summary": has_summary,
            "context_length": context_length,
            "recent_sources_used": list(dict.fromkeys(recent_sources))[:5],
            "available_related_documents": list(dict.fromkeys(all_related_docs))[:10],
        }

    async def process_query_stream(
        self,
        query: str,
        session_id: str,
        user_info: Optional[Dict] = None,
        user_type_filter: Optional[str] = None,
    ):
        """
        Streaming variant of process_query. Yields frame dicts in a fixed order:
            {"type": "session", ...} -> {"type": "sources", ...}
            -> {"type": "token", ...}* -> {"type": "metadata", ...} -> {"type": "done"}
        (or {"type": "error", ...} on failure).

        The retrieval/ranking pipeline is identical to process_query; only the final
        answer is streamed token-by-token. NOTE: this duplicates the orchestration of
        process_query — they should be unified once the orchestrator is decomposed.
        """
        start_time = time.time()
        self.metrics_collector.start_query(query)
        yield {"type": "session", "session_id": session_id}

        try:
            # STEP 1-2: store message + load context (timed)
            context_load_start = time.time()
            await self.session_manager.add_message(session_id, "user", query)
            context_data = self.session_manager.get_context_for_llm(session_id)
            conversation_context = context_data.get("formatted_context", "")
            self.metrics_collector.record_context_load((time.time() - context_load_start) * 1000)
            message_count = context_data.get("message_count", 0)
            has_summary = context_data.get("has_summary", False)
            context_length = len(conversation_context)

            # STEP 3: classify
            self.metrics_collector._start_timer("classification")
            query_type, classification_confidence = self.classifier.classify(query)
            self.metrics_collector.record_classification(query_type, classification_confidence)

            # STEP 4: greeting / farewell / escalation — templated, emitted as one chunk
            if query_type in ("greeting", "farewell", "escalation"):
                if query_type == "greeting":
                    text = await self.response_generator.generate_greeting_response()
                elif query_type == "farewell":
                    text = await self.response_generator.generate_farewell_response()
                else:
                    text = await self.response_generator.generate_escalation_response()
                self.metrics_collector.record_cost_breakdown(token_tracker.get_cost_breakdown_for_session(session_id))
                debug_metrics = self.metrics_collector.finalize_metrics()
                metadata = {
                    "query_type": query_type, "category": query_type, "confidence_score": 1.0,
                    "sources_found": 0, "sources_used": [],
                    "response_time_ms": (time.time() - start_time) * 1000,
                    "escalated": query_type == "escalation",
                }
                _run_in_background(self.session_manager.add_message(session_id, "assistant", text, metadata),
                                   "session write (greeting/escalation stream)")
                yield {"type": "sources", "sources": []}
                yield {"type": "token", "text": text}
                yield {"type": "metadata", "confidence": 1.0,
                       "requires_escalation": query_type == "escalation",
                       "escalation_reason": "user_requested" if query_type == "escalation" else "none",
                       "query_type": query_type, "classification_confidence": classification_confidence,
                       "debug_metrics": debug_metrics}
                yield {"type": "done"}
                return

            # STEP 5: follow-up detection + conditional Query Intelligence
            is_followup = self._is_likely_followup(query, message_count, conversation_context)
            if is_followup:
                available_related_docs = []
                if conversation_context:
                    recent_messages = self.session_manager.context_cache.get_messages(session_id, limit=5)
                    for msg in recent_messages:
                        if msg.get("role") == "assistant":
                            md = msg.get("metadata", {})
                            if md.get("related_documents"):
                                available_related_docs.extend(md.get("related_documents", []))
                    available_related_docs = list(dict.fromkeys(available_related_docs))
                self.metrics_collector._start_timer("query_intelligence")
                analysis = await self.query_intelligence.analyze(
                    query=query, query_type=query_type, conversation_context=conversation_context,
                    available_related_docs=available_related_docs, session_id=session_id,
                )
                self.metrics_collector.record_query_intelligence(
                    enhanced_query=analysis.structured_query.enhanced,
                    category=analysis.structured_query.category,
                    tags=analysis.structured_query.tags, intent=analysis.structured_query.user_intent,
                )
            else:
                analysis = self._create_skip_qi_analysis(query, query_type)
                self.metrics_collector.record_query_intelligence(
                    enhanced_query=query, category=query_type, tags=[], intent="search")

            # STEP 6: answer from conversation context (non-streamed — emitted as one chunk)
            if analysis.routing == "answer_from_context":
                response_dict = await self.context_responder.answer_from_conversation(
                    query=query, conversation_context=conversation_context,
                    session_id=session_id, metrics_collector=self.metrics_collector)
                self.metrics_collector.record_cost_breakdown(token_tracker.get_cost_breakdown_for_session(session_id))
                debug_metrics = self.metrics_collector.finalize_metrics()
                yield {"type": "sources", "sources": response_dict.get("sources", [])}
                yield {"type": "token", "text": response_dict.get("response", "")}
                context_debug = self._build_context_debug(
                    session_id, conversation_context, message_count, has_summary, context_length)
                yield {"type": "metadata",
                       "confidence": response_dict.get("confidence", 0.9),
                       "requires_escalation": response_dict.get("requires_escalation", False),
                       "escalation_reason": "low_confidence" if response_dict.get("requires_escalation") else "none",
                       "query_type": query_type, "classification_confidence": classification_confidence,
                       "debug_metrics": debug_metrics, "context_debug": context_debug}
                yield {"type": "done"}
                return

            structured_query = analysis.structured_query

            # STEP 7: search with fallback
            results, search_attempts = await self.search_strategy.search_with_fallback(
                query=structured_query.enhanced, query_type=query_type,
                user_type_filter=user_type_filter, parent_retrieval_handler=self.parent_retrieval,
                session_id=session_id)

            # STEP 8: no results — templated fallback
            if not results:
                self.metrics_collector.record_results(0, 0, 0.0, [])
                self.metrics_collector._start_timer("response_generation")
                text = await self.response_generator.generate_fallback_response(query=query, session_id=session_id)
                self.metrics_collector.record_response_generation()
                self.metrics_collector.record_cost_breakdown(token_tracker.get_cost_breakdown_for_session(session_id))
                debug_metrics = self.metrics_collector.finalize_metrics()
                metadata = {
                    "query_type": query_type, "category": structured_query.category,
                    "confidence_score": 0.0, "sources_found": 0, "sources_used": [],
                    "response_time_ms": (time.time() - start_time) * 1000, "escalated": True,
                }
                _run_in_background(self.session_manager.add_message(session_id, "assistant", text, metadata),
                                   "session write (fallback stream)")
                yield {"type": "sources", "sources": []}
                yield {"type": "token", "text": text}
                yield {"type": "metadata", "confidence": 0.0, "requires_escalation": True,
                       "escalation_reason": "no_results",
                       "query_type": query_type, "classification_confidence": classification_confidence,
                       "enhanced_query": structured_query.enhanced, "debug_metrics": debug_metrics}
                yield {"type": "done"}
                return

            # STEP 9: rerank
            rerank_start = time.time()
            results = self.reranker.rerank_results(results, structured_query.enhanced)
            self.metrics_collector.record_reranking((time.time() - rerank_start) * 1000)

            # STEP 9.5: clarification detection — when the query is broad and the top matches are
            # a CLUSTER of similar error/troubleshooting entries (e.g. "my listing won't sync"
            # hitting many "Can't sync to portals - X" entries), ask the user to narrow it down
            # instead of guessing one. Keyed off the RESULTS (entryType=error), not just the
            # query_type — vague problem statements often classify as "general", not "error".
            clarification_type = None
            top = results[:4]
            error_hits = sum(1 for r in top if (r.get("metadata", {}) or {}).get("entryType") == "error")
            if len(results) >= 3 and (query_type == "error" or error_hits >= 2):
                top_scores = [r.get("similarity_score", 0.0) for r in top]
                score_spread = max(top_scores) - min(top_scores) if len(top_scores) >= 2 else 1.0
                has_specific_id = bool(re.search(
                    r'\b(error\s*\d+|\d{3,4}|rc[-\s]?\d+|reason\s*code|code\s*\d+)\b',
                    query.lower().strip()))
                if score_spread < 0.15 and not has_specific_id:
                    clarification_type = "error_specifics"

            # STEP 10: build context + sources
            contexts = self.context_builder.extract_contexts(results, query)
            sources = self.context_builder.build_sources(results)
            best_confidence = self.context_builder.calculate_best_confidence(results)
            self.metrics_collector.record_results(
                sources_found=len(results), sources_used=len(sources),
                best_confidence=best_confidence, retrieved_chunks=results)

            # Emit sources BEFORE the answer streams (UI can show source cards immediately)
            yield {"type": "sources", "sources": sources}

            # STEP 11: STREAM the answer token-by-token
            self.metrics_collector._start_timer("response_generation")
            response_parts = []
            async for tok in self.response_generator.generate_response_stream(
                query, contexts, conversation_context, session_id=session_id,
                search_results=results, clarification_type=clarification_type):
                response_parts.append(tok)
                yield {"type": "token", "text": tok}
            self.metrics_collector.record_response_generation()
            response = "".join(response_parts)

            # STEP 12-14: cost, escalation decision, metadata
            self.metrics_collector.record_cost_breakdown(token_tracker.get_cost_breakdown_for_session(session_id))
            debug_metrics = self.metrics_collector.finalize_metrics()

            # Escalation decision via the EscalationHandler (single source of truth).
            escalation = self.escalation_handler.check_escalation(query_type, results, best_confidence)
            requires_escalation = escalation["should_escalate"]
            escalation_reason = escalation["escalation_reason"] if requires_escalation else "none"
            # Also escalate if the LLM produced a non-answer despite confident retrieval —
            # rerank score can be high on topically-near-but-irrelevant docs (e.g. "create a
            # contact" matching lead/listing entries), so the score alone misses these.
            if not requires_escalation and self.escalation_handler.is_non_answer(response):
                requires_escalation = True
                escalation_reason = "non_answer"
                logger.info("⚠️ Escalating: LLM returned a non-answer despite confident retrieval")

            related_documents = []
            for source in sources:
                related_documents.extend(source.get("metadata", {}).get("related_documents", []))
            related_documents = list(dict.fromkeys(related_documents))

            metadata = {
                "query_type": query_type, "category": structured_query.category,
                "subcategory": structured_query.tags[0] if structured_query.tags else None,
                "confidence_score": best_confidence, "sources_found": len(results),
                "sources_used": [s.get("title") for s in sources],
                "related_documents": related_documents,
                "response_time_ms": (time.time() - start_time) * 1000,
                "escalated": requires_escalation, "user_feedback": None,
            }
            _run_in_background(self.session_manager.add_message(session_id, "assistant", response, metadata),
                               "session write (stream)")
            _run_in_background(asyncio.to_thread(self.kb_analytics.track_kb_usage, sources, query, best_confidence, session_id),
                               "kb analytics (stream)")

            context_debug = self._build_context_debug(
                session_id, conversation_context, message_count, has_summary, context_length)
            yield {"type": "metadata", "confidence": best_confidence,
                   "requires_escalation": requires_escalation, "escalation_reason": escalation_reason,
                   "query_type": query_type,
                   "classification_confidence": classification_confidence,
                   "enhanced_query": structured_query.enhanced,
                   "query_metadata": {
                       "category": structured_query.category,
                       "intent": structured_query.user_intent, "tags": structured_query.tags},
                   "debug_metrics": debug_metrics, "context_debug": context_debug}
            yield {"type": "done"}

        except Exception as e:
            logger.error(f"❌ Error in streaming query: {e}", exc_info=True)
            yield {"type": "error", "message": "I apologize, but I encountered an error. Please try again."}
