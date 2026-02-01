"""
Query Metrics Collector - Tracks detailed query execution metrics

Collects comprehensive metrics using Pydantic models for:
- Search execution (filters, documents scanned, latency)
- Query classification and enhancement
- Source retrieval and reranking
- Response generation timing
- Cost breakdown
"""

import logging
import time
from typing import Dict, List, Optional
from ..models.query_metrics import QueryExecutionMetrics, SearchExecutionMetrics
from ..models.cost_breakdown import CostBreakdown

logger = logging.getLogger(__name__)


class QueryMetricsCollector:
    """Collects and tracks query execution metrics using Pydantic models"""
    
    def __init__(self):
        """Initialize metrics collector"""
        self.current_metrics: Optional[QueryExecutionMetrics] = None
        self._timers: Dict[str, float] = {}
        logger.info("✅ QueryMetricsCollector initialized (Pydantic)")
    
    def start_query(self, query_text: str) -> None:
        """Start tracking a new query"""
        self.current_metrics = QueryExecutionMetrics(
            query_text=query_text,
            query_type="",  # Will be set by classification
            classification_confidence=0.0
        )
        self._timers = {}
        self._start_timer("total")
        logger.debug(f"📊 Started metrics collection for query: {query_text[:50]}...")
    
    def record_classification(self, query_type: str, confidence: float) -> None:
        """Record query classification results"""
        if self.current_metrics:
            self.current_metrics.query_type = query_type
            self.current_metrics.classification_confidence = confidence
            self.current_metrics.classification_time_ms = self._stop_timer("classification")

    def record_query_intelligence(
        self,
        enhanced_query: str,
        category: Optional[str] = None,
        intent: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """Record query intelligence results (follow-up detection + enhancement)"""
        if self.current_metrics:
            self.current_metrics.enhanced_query = enhanced_query
            self.current_metrics.query_category = category
            self.current_metrics.query_intent = intent
            self.current_metrics.query_tags = tags or []
            self.current_metrics.query_intelligence_time_ms = self._stop_timer("query_intelligence")
    
    def record_search_execution(
        self,
        filters: Dict[str, str],
        docs_scanned: int,
        docs_matched: int,
        docs_returned: int,
        similarity_threshold: float,
        embedding_time_ms: float,
        search_time_ms: float
    ) -> None:
        """Record search execution metrics"""
        if self.current_metrics:
            self.current_metrics.search_execution = SearchExecutionMetrics(
                filters_applied=filters,
                documents_scanned=docs_scanned,
                documents_matched=docs_matched,
                documents_returned=docs_returned,
                similarity_threshold=similarity_threshold,
                embedding_time_ms=embedding_time_ms,
                search_time_ms=search_time_ms
            )
    
    def record_search_attempt(self, attempt_number: int, filter_type: str, results_count: int) -> None:
        """Record a search attempt (for fallback tracking)"""
        if self.current_metrics:
            self.current_metrics.search_attempts.append({
                "attempt": attempt_number,
                "filter": filter_type,
                "results": results_count
            })
    
    def record_reranking(self, rerank_time_ms: float) -> None:
        """Record reranking execution time"""
        if self.current_metrics and self.current_metrics.search_execution:
            self.current_metrics.search_execution.rerank_time_ms = rerank_time_ms
    
    def record_results(
        self, 
        sources_found: int,
        sources_used: int,
        best_confidence: float,
        retrieved_chunks: List[Dict]
    ) -> None:
        """Record search results"""
        if self.current_metrics:
            self.current_metrics.sources_found = sources_found
            self.current_metrics.sources_used = sources_used
            self.current_metrics.best_confidence = best_confidence
            self.current_metrics.retrieved_chunks = retrieved_chunks
    
    def record_escalation(
        self,
        escalated: bool,
        reason: str = "none",
        escalation_type: str = "none"
    ) -> None:
        """Record escalation decision"""
        if self.current_metrics:
            self.current_metrics.escalated = escalated
            self.current_metrics.escalation_reason = reason
            self.current_metrics.escalation_type = escalation_type
    
    def record_response_generation(self) -> None:
        """Record response generation timing"""
        if self.current_metrics:
            self.current_metrics.response_generation_time_ms = self._stop_timer("response_generation")
    
    def record_cost_breakdown(self, cost_breakdown: CostBreakdown) -> None:
        """Record cost breakdown from token tracker"""
        if self.current_metrics:
            self.current_metrics.cost_breakdown = cost_breakdown
    
    def finalize_metrics(self) -> Dict:
        """Finalize and return complete metrics as dict"""
        if self.current_metrics:
            self.current_metrics.total_time_ms = self._stop_timer("total")

            # Use Pydantic's model_dump() for clean dict conversion
            metrics_dict = self.current_metrics.model_dump()

            # ENHANCED: Log detailed breakdown
            logger.info(
                f"📊 TIMING BREAKDOWN:\n"
                f"  Classification: {self.current_metrics.classification_time_ms:.0f}ms\n"
                f"  Query Intelligence: {self.current_metrics.query_intelligence_time_ms:.0f}ms\n"
                f"  Embedding: {self.current_metrics.search_execution.embedding_time_ms:.0f}ms\n"
                f"  Search: {self.current_metrics.search_execution.search_time_ms:.0f}ms\n"
                f"  Reranking: {self.current_metrics.search_execution.rerank_time_ms:.0f}ms\n"
                f"  Response Generation: {self.current_metrics.response_generation_time_ms:.0f}ms\n"
                f"  TOTAL: {self.current_metrics.total_time_ms:.0f}ms"
            )

            logger.info(
                f"💰 COST BREAKDOWN:\n"
                f"  Query Intelligence: ${self.current_metrics.cost_breakdown.query_intelligence_cost:.6f} "
                f"({self.current_metrics.cost_breakdown.query_intelligence_input_tokens}in + "
                f"{self.current_metrics.cost_breakdown.query_intelligence_output_tokens}out)\n"
                f"  Response Generation: ${self.current_metrics.cost_breakdown.response_generation_cost:.6f} "
                f"({self.current_metrics.cost_breakdown.response_input_tokens}in + "
                f"{self.current_metrics.cost_breakdown.response_output_tokens}out)\n"
                f"  Embedding: ${self.current_metrics.cost_breakdown.embedding_cost:.6f} "
                f"({self.current_metrics.cost_breakdown.embedding_tokens}tokens)\n"
                f"  TOTAL: ${self.current_metrics.cost_breakdown.total_cost:.6f} "
                f"({self.current_metrics.cost_breakdown.total_tokens} tokens)"
            )

            return metrics_dict
        return {}
    
    def get_metrics_for_analytics(self) -> Dict:
        """Get metrics formatted for Firebase analytics storage"""
        if not self.current_metrics:
            return {}
        
        return {
            "query_type": self.current_metrics.query_type,
            "category": self.current_metrics.query_category,
            "confidence_score": self.current_metrics.best_confidence,
            "sources_found": self.current_metrics.sources_found,
            "sources_used": self.current_metrics.sources_used,
            "response_time_ms": self.current_metrics.total_time_ms,
            "escalated": self.current_metrics.escalated,
            "escalation_reason": self.current_metrics.escalation_reason,
            "escalation_type": self.current_metrics.escalation_type,
            "total_cost": self.current_metrics.cost_breakdown.total_cost,
            "search_execution": self.current_metrics.search_execution.model_dump(),
            "search_attempts": self.current_metrics.search_attempts
        }
    
    def get_metrics_for_test_agent(self) -> Dict:
        """Get full metrics for test agent debug display"""
        return self.finalize_metrics()
    
    # === TIMER HELPERS ===
    
    def _start_timer(self, timer_name: str) -> None:
        """Start a named timer"""
        self._timers[timer_name] = time.time()
    
    def _stop_timer(self, timer_name: str) -> float:
        """Stop a timer and return elapsed time in milliseconds"""
        if timer_name in self._timers:
            elapsed = (time.time() - self._timers[timer_name]) * 1000
            del self._timers[timer_name]
            return elapsed
        return 0.0
