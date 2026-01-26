"""
Query Metrics Collector - Tracks detailed query execution metrics

Collects comprehensive metrics for:
- Search execution (filters, documents scanned, latency)
- Query classification and enhancement
- Source retrieval and reranking
- Response generation timing
"""

import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SearchExecutionMetrics:
    """Metrics for vector search execution"""
    filters_applied: Dict[str, str] = field(default_factory=dict)
    documents_scanned: int = 0  # Total docs in collection
    documents_matched: int = 0  # After metadata filter
    documents_returned: int = 0  # After similarity threshold
    similarity_threshold: float = 0.7
    embedding_time_ms: float = 0.0
    search_time_ms: float = 0.0
    rerank_time_ms: float = 0.0


@dataclass
class QueryExecutionMetrics:
    """Complete query execution metrics"""
    # Query metadata
    query_text: str = ""
    query_type: str = ""
    classification_confidence: float = 0.0
    
    # Enhanced query
    enhanced_query: str = ""
    query_category: Optional[str] = None
    query_intent: Optional[str] = None
    query_tags: List[str] = field(default_factory=list)
    
    # Search execution
    search_execution: SearchExecutionMetrics = field(default_factory=SearchExecutionMetrics)
    search_attempts: List[Dict] = field(default_factory=list)
    
    # Results
    sources_found: int = 0
    sources_used: int = 0
    best_confidence: float = 0.0
    retrieved_chunks: List[Dict] = field(default_factory=list)
    
    # Timing
    total_time_ms: float = 0.0
    classification_time_ms: float = 0.0
    query_building_time_ms: float = 0.0
    response_generation_time_ms: float = 0.0
    
    # Escalation
    escalated: bool = False
    escalation_reason: str = "none"
    escalation_type: str = "none"


class QueryMetricsCollector:
    """Collects and tracks query execution metrics"""
    
    def __init__(self):
        """Initialize metrics collector"""
        self.current_metrics: Optional[QueryExecutionMetrics] = None
        self._timers: Dict[str, float] = {}
        logger.info("✅ QueryMetricsCollector initialized")
    
    def start_query(self, query_text: str) -> None:
        """Start tracking a new query"""
        self.current_metrics = QueryExecutionMetrics(query_text=query_text)
        self._timers = {}
        self._start_timer("total")
        logger.debug(f"📊 Started metrics collection for query: {query_text[:50]}...")
    
    def record_classification(self, query_type: str, confidence: float) -> None:
        """Record query classification results"""
        if self.current_metrics:
            self.current_metrics.query_type = query_type
            self.current_metrics.classification_confidence = confidence
            self.current_metrics.classification_time_ms = self._stop_timer("classification")
    
    def record_query_enhancement(
        self, 
        enhanced_query: str,
        category: Optional[str] = None,
        intent: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> None:
        """Record query enhancement results"""
        if self.current_metrics:
            self.current_metrics.enhanced_query = enhanced_query
            self.current_metrics.query_category = category
            self.current_metrics.query_intent = intent
            self.current_metrics.query_tags = tags or []
            self.current_metrics.query_building_time_ms = self._stop_timer("query_building")
    
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
    
    def finalize_metrics(self) -> Dict:
        """Finalize and return complete metrics"""
        if self.current_metrics:
            self.current_metrics.total_time_ms = self._stop_timer("total")
            metrics_dict = asdict(self.current_metrics)
            logger.info(
                f"📊 Query metrics: {self.current_metrics.total_time_ms:.0f}ms total, "
                f"{self.current_metrics.sources_found} sources, "
                f"confidence: {self.current_metrics.best_confidence:.2f}"
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
            "search_execution": {
                "filters_applied": self.current_metrics.search_execution.filters_applied,
                "documents_scanned": self.current_metrics.search_execution.documents_scanned,
                "documents_matched": self.current_metrics.search_execution.documents_matched,
                "documents_returned": self.current_metrics.search_execution.documents_returned,
                "embedding_time_ms": self.current_metrics.search_execution.embedding_time_ms,
                "search_time_ms": self.current_metrics.search_execution.search_time_ms,
                "rerank_time_ms": self.current_metrics.search_execution.rerank_time_ms
            },
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
