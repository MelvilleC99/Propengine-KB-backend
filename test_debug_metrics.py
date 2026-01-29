"""
Test script to show exact debug_metrics structure
"""
from src.analytics.models import QueryExecutionMetrics, SearchExecutionMetrics, CostBreakdown
import json

# Create example metrics (what orchestrator creates)
metrics = QueryExecutionMetrics(
    query_text='how do I resize a photo',
    query_type='howto',
    classification_confidence=0.80,
    enhanced_query='how do I resize a photo',
    query_category='listing_management',
    query_intent='howto',
    query_tags=['resize', 'photo'],
    search_execution=SearchExecutionMetrics(
        filters_applied={'entryType': 'how_to'},
        documents_scanned=6,
        documents_matched=6,
        documents_returned=2,
        similarity_threshold=0.7,
        embedding_time_ms=11175.0,
        search_time_ms=801.0,
        rerank_time_ms=0.0
    ),
    sources_found=2,
    sources_used=2,
    best_confidence=0.83,
    total_time_ms=15014.0,
    classification_time_ms=0.0,
    query_building_time_ms=0.0,
    response_generation_time_ms=1908.0,
    cost_breakdown=CostBreakdown(
        embedding_cost=0.0001,
        query_building_cost=0.0,
        response_generation_cost=0.0005,
        total_cost=0.0006,
        embedding_tokens=100,
        response_input_tokens=800,
        response_output_tokens=50,
        total_tokens=950
    ),
    escalated=False,
    escalation_reason='none'
)

# Convert to dict (what finalize_metrics() does)
metrics_dict = metrics.model_dump()

# Pretty print
print('=== FULL DEBUG_METRICS SENT TO FRONTEND ===\n')
print(json.dumps(metrics_dict, indent=2))

print('\n\n=== COST BREAKDOWN (HIGHLIGHTED) ===\n')
print(json.dumps(metrics_dict['cost_breakdown'], indent=2))

print('\n\n=== SIZE ANALYSIS ===')
print(f"Total JSON size: {len(json.dumps(metrics_dict))} bytes")
print(f"Cost breakdown size: {len(json.dumps(metrics_dict['cost_breakdown']))} bytes")
