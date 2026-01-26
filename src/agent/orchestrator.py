"""Agent Orchestrator - Coordinates query processing pipeline

This is the main coordinator that delegates to specialized modules.
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
from src.agent.context import ContextBuilder
from src.agent.response import ResponseGenerator
from src.admin.query_metrics import QueryMetricsCollector

logger = logging.getLogger(__name__)


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
        
        # Context & Response
        self.context_builder = ContextBuilder()
        self.response_generator = ResponseGenerator()
        
        # Memory & Analytics
        self.session_manager = SessionManager()
        self.kb_analytics = KBAnalyticsTracker()
        
        logger.info("✅ Agent orchestrator initialized (modular architecture with YAML prompts)")
    
    async def process_query(
        self, 
        query: str, 
        session_id: str,
        user_info: Optional[Dict] = None,
        user_type_filter: Optional[str] = None
    ) -> Dict:
        """
        Process user query through the complete pipeline
        
        Pipeline:
        1. Store user message
        2. Check conversation context
        3. Classify query type
        4. Enhance query for search
        5. Search vector database
        6. Re-rank results
        7. Build context
        8. Generate response
        9. Track analytics
        10. Return result
        
        Args:
            query: User's question
            session_id: Conversation session ID
            user_info: Optional user metadata
            user_type_filter: Filter by user type (internal/external)
            
        Returns:
            Dict with response, confidence, sources, etc.
        """
        # Start timing for analytics
        start_time = time.time()
        
        # Start metrics collection
        self.metrics_collector.start_query(query)
        
        try:
            # === STEP 1: Store user message ===
            await self.session_manager.add_message(session_id, "user", query)
            
            # === STEP 2: Get conversation context (messages + summary) ===
            context_data = self.session_manager.get_context_for_llm(session_id)
            conversation_context = context_data.get("formatted_context", "")
            
            # Try answering from context first
            if conversation_context.strip():
                context_answer = await self._try_answer_from_context(
                    query, conversation_context, session_id
                )
                if context_answer:
                    return context_answer
            
            # === STEP 3: Classify query ===
            query_type, classification_confidence = self.classifier.classify(query)
            logger.info(f"📋 Query classified as '{query_type}' (confidence: {classification_confidence})")
            
            # Record classification
            self.metrics_collector.record_classification(query_type, classification_confidence)
            
            # === STEP 4: Handle greetings (no search needed) ===
            if query_type == "greeting":
                response = await self.response_generator.generate_greeting_response()
                
                # Build metadata for greeting
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
            
            # === STEP 5: Build structured query ===
            structured_query = await self.query_builder.build(
                query, 
                query_type,
                conversation_context
            )
            logger.info(
                f"🔍 Query structured: '{query}' → "
                f"enhanced='{structured_query.enhanced}', "
                f"category={structured_query.category}"
            )
            
            # Record query enhancement
            self.metrics_collector.record_query_enhancement(
                enhanced_query=structured_query.enhanced,
                category=structured_query.category,
                tags=structured_query.tags,
                intent=structured_query.user_intent
            )
            
            # === STEP 6: Search vector database ===
            results, search_attempts = await self._search_with_fallback(
                structured_query.enhanced,
                query_type,
                user_type_filter
            )
            
            # === STEP 7: No results - generate fallback ===
            if not results:
                logger.warning(f"❌ No results found for query: {query}")
                
                # Record no results
                self.metrics_collector.record_results(
                    sources_found=0,
                    sources_used=0,
                    best_confidence=0.0,
                    retrieved_chunks=[]
                )
                
                fallback_response = await self.response_generator.generate_fallback_response(query)
                
                # Build metadata for fallback
                elapsed_ms = (time.time() - start_time) * 1000
                
                # Finalize metrics
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
            
            # === STEP 8: Re-rank results ===
            rerank_start = time.time()
            results = self.reranker.rerank_results(results, structured_query.enhanced)
            rerank_time_ms = (time.time() - rerank_start) * 1000
            logger.info(f"📊 Re-ranked {len(results)} results")
            
            # Record reranking
            self.metrics_collector.record_reranking(rerank_time_ms)
            
            # === STEP 9: Build context from results ===
            contexts = self.context_builder.extract_contexts(results, query)
            sources = self.context_builder.build_sources(results)
            best_confidence = self.context_builder.calculate_best_confidence(results)
            
            # Calculate average score
            scores = [r.get("similarity_score", 0.0) for r in results]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            
            # Record results
            self.metrics_collector.record_results(
                sources_found=len(results),
                sources_used=len(sources),
                best_confidence=best_confidence,
                retrieved_chunks=results
            )
            
            # === STEP 10: Generate response ===
            response = await self.response_generator.generate_response(
                query, contexts, conversation_context
            )
            
            # === STEP 11: Calculate timing ===
            elapsed_ms = (time.time() - start_time) * 1000
            
            # Finalize metrics
            debug_metrics = self.metrics_collector.finalize_metrics()
            
            # === STEP 12: Build metadata for analytics ===
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
                "user_feedback": None  # Will be updated by frontend if user gives feedback
            }
            
            # === STEP 13: Store assistant message with metadata ===
            await self.session_manager.add_message(session_id, "assistant", response, metadata)
            
            # === STEP 14: Track analytics (legacy - can be removed later) ===
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
            
            # Build metadata for error case
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

    async def _try_answer_from_context(
        self, 
        query: str, 
        conversation_context: str, 
        session_id: str
    ) -> Optional[Dict]:
        """Try to answer from conversation context if it's a follow-up"""
        if not self._is_followup_query(query, conversation_context):
            return None
        
        logger.info("📝 Detected follow-up query, attempting to answer from context")
        
        try:
            response = await self.response_generator.generate_response(
                query, 
                [conversation_context],  # Use context as source
                conversation_context
            )
            
            self.session_manager.add_message(session_id, "assistant", response)
            
            return {
                "response": response,
                "confidence": 0.9,
                "sources": [{"title": "Conversation Context", "confidence": 0.9}],
                "query_type": "followup",
                "from_context": True
            }
        except Exception as e:
            logger.error(f"Error answering from context: {e}")
            return None
    
    async def _search_with_fallback(
        self,
        query: str,
        query_type: str,
        user_type_filter: Optional[str]
    ) -> tuple[List[Dict], List[str]]:
        """
        Search with fallback strategy
        
        Returns:
            Tuple of (results, search_attempts)
        """
        search_attempts = []
        cached_embeddings = None
        
        # Primary search with entry_type filter
        search_attempts.append(f"primary:{query_type}")
        results, cached_embeddings, search_stats = await self.vector_search.search(
            query=query,
            entry_type=query_type,
            user_type=user_type_filter,
            k=settings.MAX_SEARCH_RESULTS
        )
        
        # Record search execution
        if search_stats:
            self.metrics_collector.record_search_execution(
                filters=search_stats.get("filters_applied", {}),
                docs_scanned=search_stats.get("documents_requested", 0),
                docs_matched=search_stats.get("documents_matched", 0),
                docs_returned=search_stats.get("documents_returned", 0),
                similarity_threshold=search_stats.get("similarity_threshold", 0.7),
                embedding_time_ms=search_stats.get("embedding_time_ms", 0.0),
                search_time_ms=search_stats.get("search_time_ms", 0.0)
            )
        
        if results:
            return results, search_attempts
        
        # Fallback 1: Remove entry_type filter
        logger.info(f"No results for {query_type}, trying without entry_type filter")
        search_attempts.append("fallback:no_filter")
        results, _, search_stats = await self.vector_search.search(
            query=query,
            user_type=user_type_filter,
            k=settings.MAX_SEARCH_RESULTS,
            query_embeddings=cached_embeddings
        )
        
        if results:
            return results, search_attempts
        
        # Fallback 2: If howto, try error
        if query_type == "howto":
            logger.info("Trying error type as fallback for howto")
            search_attempts.append("fallback:error")
            results, _, search_stats = await self.vector_search.search(
                query=query,
                entry_type="error",
                user_type=user_type_filter,
                k=settings.MAX_SEARCH_RESULTS,
                query_embeddings=cached_embeddings
            )
        
        # Fallback 3: If definition contains "error", try error type
        if query_type == "definition" and "error" in query.lower():
            logger.info("Definition query contains 'error', trying error type")
            search_attempts.append("fallback:error_detected")
            results, _, search_stats = await self.vector_search.search(
                query=query,
                entry_type="error",
                user_type=user_type_filter,
                k=settings.MAX_SEARCH_RESULTS,
                query_embeddings=cached_embeddings
            )
        
        return results, search_attempts
    
    def _is_followup_query(self, query: str, conversation_context: str) -> bool:
        """Detect if query is a follow-up question"""
        if not conversation_context.strip():
            return False
        
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        
        # Follow-up indicators
        followup_patterns = [
            r'\bso\b.*\bonly\b',
            r'\bso\b.*\bjust\b',
            r'\bthat\s+(means|is)\b',
            r'^\s*(only|just|so)\b',
            r'\byes\b.*\?',
            r'\band\b.*\?',
            r'\bwhat about\b',
            r'\bhow about\b',
            r'\bwhy\s+(only|not|just)\b',
        ]
        
        import re
        for pattern in followup_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Short queries with pronouns
        if (len(query_words) <= 6 and 
            any(pronoun in query_words for pronoun in ['it', 'that', 'this', 'they'])):
            return True
        
        return False
