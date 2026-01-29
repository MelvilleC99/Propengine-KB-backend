"""
Query Execution Metrics - Pydantic Models

Complete metrics for query execution including search, timing, and costs
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from .cost_breakdown import CostBreakdown


class SearchExecutionMetrics(BaseModel):
    """Vector search execution metrics with validation"""
    
    filters_applied: Dict[str, str] = Field(
        default_factory=dict,
        description="Metadata filters applied to search"
    )
    documents_scanned: int = Field(
        default=0,
        ge=0,
        description="Total documents in collection"
    )
    documents_matched: int = Field(
        default=0,
        ge=0,
        description="Documents matching metadata filters"
    )
    documents_returned: int = Field(
        default=0,
        ge=0,
        description="Documents above similarity threshold"
    )
    similarity_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score required"
    )
    embedding_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time to generate query embedding (ms)"
    )
    search_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time to execute vector search (ms)"
    )
    rerank_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Time to rerank results (ms)"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "filters_applied": {"entryType": "how_to"},
                "documents_scanned": 6,
                "documents_matched": 6,
                "documents_returned": 2,
                "similarity_threshold": 0.7,
                "embedding_time_ms": 1294.5,
                "search_time_ms": 735.2,
                "rerank_time_ms": 0.0
            }
        }
    }


class QueryExecutionMetrics(BaseModel):
    """Complete query execution metrics"""
    
    # Query metadata
    query_text: str = Field(description="Original user query")
    query_type: str = Field(description="Classified query type (e.g., 'howto', 'error')")
    classification_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Classification confidence score"
    )
    
    # Enhanced query
    enhanced_query: str = Field(
        default="",
        description="LLM-enhanced query (if query building enabled)"
    )
    query_category: Optional[str] = Field(
        default=None,
        description="Query category from enhancement"
    )
    query_intent: Optional[str] = Field(
        default=None,
        description="User intent from enhancement"
    )
    query_tags: List[str] = Field(
        default_factory=list,
        description="Tags extracted from query"
    )
    
    # Search execution
    search_execution: SearchExecutionMetrics = Field(
        default_factory=SearchExecutionMetrics,
        description="Vector search metrics"
    )
    search_attempts: List[Dict] = Field(
        default_factory=list,
        description="Search attempts with fallback tracking"
    )
    
    # Results
    sources_found: int = Field(
        default=0,
        ge=0,
        description="Number of sources found"
    )
    sources_used: int = Field(
        default=0,
        ge=0,
        description="Number of sources used in response"
    )
    best_confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Best source confidence score"
    )
    retrieved_chunks: List[Dict] = Field(
        default_factory=list,
        description="Retrieved document chunks"
    )
    
    # Timing (with LLM generation time!)
    total_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total query processing time (ms)"
    )
    classification_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Query classification time (ms)"
    )
    query_building_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Query enhancement time (ms)"
    )
    response_generation_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="LLM response generation time (ms)"
    )
    
    # Cost breakdown (NEW!)
    cost_breakdown: CostBreakdown = Field(
        default_factory=CostBreakdown,
        description="Cost and token usage breakdown"
    )
    
    # Escalation
    escalated: bool = Field(
        default=False,
        description="Whether query was escalated"
    )
    escalation_reason: str = Field(
        default="none",
        description="Reason for escalation"
    )
    escalation_type: str = Field(
        default="none",
        description="Type of escalation"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query_text": "how do I upload photos",
                "query_type": "howto",
                "classification_confidence": 0.85,
                "enhanced_query": "upload photos to listing",
                "query_category": "listing_management",
                "query_intent": "howto",
                "sources_found": 2,
                "sources_used": 1,
                "best_confidence": 0.72,
                "total_time_ms": 4958.0,
                "response_generation_time_ms": 2900.0,
                "cost_breakdown": {
                    "total_cost": 0.0006
                }
            }
        }
    }
