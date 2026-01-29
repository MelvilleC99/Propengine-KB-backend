"""
Analytics Module - Centralized Metrics, Tracking, and Cost Calculation

This module provides:
- Pydantic models for type-safe analytics
- Query execution tracking
- Token usage and cost tracking
- Metrics collection and aggregation
"""

# Export models
from .models import (
    QueryExecutionMetrics,
    SearchExecutionMetrics,
    CostBreakdown,
    TokenUsage
)

# Export collectors
from .collectors import QueryMetricsCollector

# Export trackers
from .tracking import (
    TokenTracker,
    token_tracker,
    CostCalculator,
    cost_calculator
)

__all__ = [
    # Models
    "QueryExecutionMetrics",
    "SearchExecutionMetrics",
    "CostBreakdown",
    "TokenUsage",
    # Collectors
    "QueryMetricsCollector",
    # Tracking
    "TokenTracker",
    "token_tracker",
    "CostCalculator",
    "cost_calculator"
]
