"""Agent Orchestrator - Coordinates query processing pipeline

REFACTORED: Logic extracted into separate modules for better maintainability.
- Context analysis → context/context_analyzer.py
- Search strategy → search/search_strategy.py
- Parent retrieval → search/parent_retrieval.py
"""

from typing import Dict, List, Optional
import logging
import time
from src.config.settings import settings
from src.query.vector_search import VectorSearch
from src.query.reranker import SearchReranker
from src.memory.session_manager import SessionManager
from src.memory.kb_analytics import KBAnalyticsTracker
from src.agent.classification import QueryClassifier
from src.agent.query_processing import QueryBuilder, StructuredQuery
from src.agent.context import ContextBuilder, ContextAnalyzer
from src.agent.search import SearchStrategy, ParentDocumentRetrieval
from src.agent.response import ResponseGenerator
from src.analytics import QueryMetricsCollector, token_tracker  # NEW: Updated import
from src.utils.logging_helper import get_logger

logger = get_logger(__name__)


class Agent:
    """Main agent orchestrator - coordinates the query processing pipeline"""
    
    def __init__(self):
        """Initialize orchestrator with all required components"""
        # Classification & Query Building
        self.classifier = QueryClassifier()
        self.query_builder = QueryBuilder()
        
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
        self.context_analyzer = ContextAnalyzer()
        self.response_generator = ResponseGenerator()
        
        # Memory & Analytics
        self.session_manager = SessionManager()
        self.kb_analytics = KBAnalyticsTracker()
        
        logger.info("✅ Agent orchestrator initialized (refactored modular architecture)")
    
    async def process_query(
        self, 
        query: str, 
        session_id: str,
        user_info: Optional[Dict] = None,
        user_type_filter: Optional[str] = None
    ) -> Dict:
        """
        Process user query through the complete pipeline
        
        Pipeline (refactored):
        1. Store user message
        2. Get conversation context
        3. Try answer from context (if followup)
        4. Classify query type
        5. Enhance query for search  
        6. Search with fallback
        7. Re-rank results
        8. Build context
        9. Generate response
        10. Store and return
        
        Args:
            query: User's question
            session_id: Conversation session ID
            user_info: Optional user metadata
            user_type_filter: Filter by user type (internal/external)
            
        Returns:
            Dict with response, confidence, sources, etc.
        """
        # Start timing
        start_time = time.time()
        self.metrics_collector.start_query(query)
        
        try:
            # === STEP 1: Store user message ===
            logger.log_query_start(session_id, query)
            await self.session_manager.add_message(session_id, "user", query)
            logger.log_message_stored(session_id, "user", query)
            
            # === STEP 2: Get conversation context ===
            context_data = self.session_manager.get_context_for_llm(session_id)
            conversation_context = context_data.get("formatted_context", "")
            
            message_count = context_data.get("message_count", 0)
            has_summary = context_data.get("has_summary", False)
            context_length = len(conversation_context)
            
            logger.log_context_retrieval(session_id, message_count, context_length, has_summary)
            
            if context_length == 0:
                logger.log_context_empty(session_id, "No messages found in Redis/Firebase")
            else:
                logger.log_context_preview(session_id, conversation_context)
            
            # === STEP 3: Classify query ===
            query_type, classification_confidence = self.classifier.classify(query)
            logger.log_query_classification(query_type, classification_confidence)
            self.metrics_collector.record_classification(query_type, classification_confidence)
            
            # === STEP 5: Handle greetings (no search needed) ===
            if query_type == "greeting":
                response = await self.response_generator.generate_greeting_response()
                
                elapsed_ms = (time.time() - start_time) * 1000
                metadata = {
                    "query_type": query_type,
                    "category": "greeting",
                    "confidence_score": 1.0,
                    "sources_found": 0,
                    "sources_used": [],
                    "response_time_ms": elapsed_ms,
                    "escalated": False
                }
                
                await self.session_manager.add_message(session_id, "assistant", response, metadata)
                
                return {
                    "response": response,
                    "confidence": 1.0,
                    "sources": [],
                    "query_type": query_type,
                    "classification_confidence": classification_confidence
                }
            
            # === STEP 6: Build structured query (optional) ===
            if settings.ENABLE_QUERY_ENHANCEMENT:
                structured_query = await self.query_builder.build(
                    query, 
                    query_type,
                    conversation_context
                )
                logger.info(
                    f"🔍 Query enhanced: '{query}' → '{structured_query.enhanced}'"
                )
                search_query = structured_query.enhanced
                
                self.metrics_collector.record_query_enhancement(
                    enhanced_query=structured_query.enhanced,
                    category=structured_query.category,
                    tags=structured_query.tags,
                    intent=structured_query.user_intent
                )
            else:
                # Use raw query directly
                logger.info(f"🔍 Query enhancement DISABLED, using raw query: '{query}'")
                from src.agent.query_processing import StructuredQuery
                structured_query = StructuredQuery(
                    original=query,      # Required: original query
                    enhanced=query,      # Use same as original
                    query_type=query_type,  # Required: from classification
                    category="unknown",
                    tags=[],
                    user_intent="search"
                )
                search_query = query
            
            # === STEP 7: Search with fallback ===
            results, search_attempts = await self.search_strategy.search_with_fallback(
                query=search_query,  # Use either enhanced or raw query
                query_type=query_type,
                user_type_filter=user_type_filter,
                parent_retrieval_handler=self.parent_retrieval,
                session_id=session_id  # NOW PASSED FOR COST TRACKING
            )
            
            # === STEP 8: No results - generate fallback ===
            if not results:
                logger.warning(f"❌ No results found for query: {query}")
                
                self.metrics_collector.record_results(
                    sources_found=0,
                    sources_used=0,
                    best_confidence=0.0,
                    retrieved_chunks=[]
                )
                
                fallback_response = await self.response_generator.generate_fallback_response(query)
                
                elapsed_ms = (time.time() - start_time) * 1000
                debug_metrics = self.metrics_collector.finalize_metrics()
                
                metadata = {
                    "query_type": query_type,
                    "category": structured_query.category,
                    "confidence_score": 0.0,
                    "sources_found": 0,
                    "sources_used": [],
                    "response_time_ms": elapsed_ms,
                    "escalated": True
                }
                
                await self.session_manager.add_message(session_id, "assistant", fallback_response, metadata)
                
                return {
                    "response": fallback_response,
                    "confidence": 0.0,
                    "sources": [],
                    "query_type": query_type,
                    "classification_confidence": classification_confidence,
                    "requires_escalation": True,
                    "search_attempts": search_attempts,
                    "enhanced_query": structured_query.enhanced,
                    "query_metadata": {
                        "category": structured_query.category,
                        "intent": structured_query.user_intent,
                        "tags": structured_query.tags
                    },
                    "debug_metrics": debug_metrics
                }
            
            # === STEP 9: Re-rank results ===
            rerank_start = time.time()
            results = self.reranker.rerank_results(results, structured_query.enhanced)
            rerank_time_ms = (time.time() - rerank_start) * 1000
            logger.info(f"📊 Re-ranked {len(results)} results")
            self.metrics_collector.record_reranking(rerank_time_ms)
            
            # === STEP 10: Build context from results ===
            contexts = self.context_builder.extract_contexts(results, query)
            sources = self.context_builder.build_sources(results)
            best_confidence = self.context_builder.calculate_best_confidence(results)
            
            scores = [r.get("similarity_score", 0.0) for r in results]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            
            self.metrics_collector.record_results(
                sources_found=len(results),
                sources_used=len(sources),
                best_confidence=best_confidence,
                retrieved_chunks=results
            )
            
            # === STEP 11: Generate response (with timing!) ===
            self.metrics_collector._start_timer("response_generation")
            response = await self.response_generator.generate_response(
                query, contexts, conversation_context,
                session_id=session_id  # NOW PASSED FOR COST TRACKING
            )
            self.metrics_collector.record_response_generation()  # Records timing
            
            # === STEP 12: Aggregate cost breakdown ===
            cost_breakdown = token_tracker.get_cost_breakdown_for_session(session_id)
            logger.info(f"💰 Cost breakdown for session {session_id}: {cost_breakdown}")
            self.metrics_collector.record_cost_breakdown(cost_breakdown)
            
            # === STEP 13: Calculate timing ===
            elapsed_ms = (time.time() - start_time) * 1000
            debug_metrics = self.metrics_collector.finalize_metrics()
            
            # Log cost to verify it's in debug_metrics
            if debug_metrics.get("cost_breakdown"):
                logger.info(f"✅ Cost in debug_metrics: ${debug_metrics['cost_breakdown']['total_cost']:.6f}")
            else:
                logger.warning("⚠️ No cost_breakdown in debug_metrics!")
            
            # === STEP 14: Build metadata ===
            requires_escalation = best_confidence < 0.7
            metadata = {
                "query_type": query_type,
                "category": structured_query.category,
                "subcategory": structured_query.tags[0] if structured_query.tags else None,
                "confidence_score": best_confidence,
                "sources_found": len(results),
                "sources_used": [s.get("title") for s in sources],
                "response_time_ms": elapsed_ms,
                "escalated": requires_escalation,
                "user_feedback": None
            }
            
            # === STEP 14: Store assistant message ===
            await self.session_manager.add_message(session_id, "assistant", response, metadata)
            
            # === STEP 15: Track analytics ===
            self.kb_analytics.track_kb_usage(sources, query, best_confidence, session_id)
            
            logger.info(f"✅ Response generated (confidence: {best_confidence:.2f}, escalation: {requires_escalation}, time: {elapsed_ms:.0f}ms)")
            
            return {
                "response": response,
                "confidence": best_confidence,
                "sources": sources,
                "query_type": query_type,
                "classification_confidence": classification_confidence,
                "requires_escalation": requires_escalation,
                "search_attempts": search_attempts,
                "enhanced_query": structured_query.enhanced,
                "query_metadata": {
                    "category": structured_query.category,
                    "intent": structured_query.user_intent,
                    "tags": structured_query.tags
                },
                "debug_metrics": debug_metrics
            }
            
        except Exception as e:
            logger.error(f"❌ Error processing query: {e}", exc_info=True)
            error_response = "I apologize, but I encountered an error. Please try again."
            
            elapsed_ms = (time.time() - start_time) * 1000
            metadata = {
                "query_type": "error",
                "category": "system_error",
                "confidence_score": 0.0,
                "sources_found": 0,
                "sources_used": [],
                "response_time_ms": elapsed_ms,
                "escalated": True,
                "error": str(e)
            }
            
            await self.session_manager.add_message(session_id, "assistant", error_response, metadata)
            
            return {
                "response": error_response,
                "confidence": 0.0,
                "sources": [],
                "error": str(e),
                "requires_escalation": True
            }
