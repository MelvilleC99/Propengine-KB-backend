"""Test script to verify debug metrics are complete

Run this to see exactly what debug_metrics the backend returns.
This will help determine if it's a backend or frontend issue.
"""

import asyncio
import json
from src.agent.orchestrator import Agent

async def test_debug_metrics():
    """Test agent and print complete debug metrics"""

    print("=" * 80)
    print("TESTING AGENT DEBUG METRICS")
    print("=" * 80)
    print()

    # Initialize agent
    agent = Agent()

    # Test query
    query = "how do I upload images"
    session_id = "test_debug_metrics_123"

    print(f"Query: '{query}'")
    print(f"Session ID: {session_id}")
    print()
    print("Processing...")
    print()

    # Process query
    result = await agent.process_query(
        query=query,
        session_id=session_id
    )

    # Extract debug metrics
    debug_metrics = result.get("debug_metrics", {})

    if not debug_metrics:
        print("❌ ERROR: No debug_metrics in response!")
        print()
        print("Response keys:", list(result.keys()))
        return

    print("=" * 80)
    print("TIMING BREAKDOWN")
    print("=" * 80)
    print()

    # Classification
    classification_time = debug_metrics.get("classification_time_ms", 0)
    print(f"  Classification:      {classification_time:>8.0f}ms")

    # Query Intelligence (THIS IS THE MISSING ONE!)
    query_intelligence_time = debug_metrics.get("query_intelligence_time_ms", 0)
    print(f"  Query Intelligence:  {query_intelligence_time:>8.0f}ms  ⭐ (This should be ~1400ms)")

    # Search execution
    search_exec = debug_metrics.get("search_execution", {})
    embedding_time = search_exec.get("embedding_time_ms", 0)
    search_time = search_exec.get("search_time_ms", 0)
    rerank_time = search_exec.get("rerank_time_ms", 0)

    print(f"  Embedding:           {embedding_time:>8.0f}ms")
    print(f"  Search:              {search_time:>8.0f}ms")
    print(f"  Reranking:           {rerank_time:>8.0f}ms")

    # Response generation
    response_gen_time = debug_metrics.get("response_generation_time_ms", 0)
    print(f"  Response Generation: {response_gen_time:>8.0f}ms")

    # Total
    total_time = debug_metrics.get("total_time_ms", 0)
    print(f"  {'─' * 40}")
    print(f"  TOTAL:               {total_time:>8.0f}ms")

    # Calculate sum to verify
    calculated_sum = (
        classification_time +
        query_intelligence_time +
        embedding_time +
        search_time +
        rerank_time +
        response_gen_time
    )
    print(f"  Calculated sum:      {calculated_sum:>8.0f}ms")

    if abs(calculated_sum - total_time) > 50:
        print(f"  ⚠️  WARNING: {abs(calculated_sum - total_time):.0f}ms discrepancy!")
    else:
        print(f"  ✅ Times match!")

    print()
    print("=" * 80)
    print("COST BREAKDOWN")
    print("=" * 80)
    print()

    cost_breakdown = debug_metrics.get("cost_breakdown", {})

    # Query Intelligence tokens/cost
    qi_input = cost_breakdown.get("query_intelligence_input_tokens", 0)
    qi_output = cost_breakdown.get("query_intelligence_output_tokens", 0)
    qi_cost = cost_breakdown.get("query_intelligence_cost", 0)
    print(f"  Query Intelligence:")
    print(f"    Input tokens:  {qi_input:>6} (should be >500 if prompt included)")
    print(f"    Output tokens: {qi_output:>6}")
    print(f"    Cost:          ${qi_cost:.6f}")
    print()

    # Response generation tokens/cost
    resp_input = cost_breakdown.get("response_input_tokens", 0)
    resp_output = cost_breakdown.get("response_output_tokens", 0)
    resp_cost = cost_breakdown.get("response_generation_cost", 0)
    print(f"  Response Generation:")
    print(f"    Input tokens:  {resp_input:>6} (should be >800 if prompt+context included)")
    print(f"    Output tokens: {resp_output:>6}")
    print(f"    Cost:          ${resp_cost:.6f}")
    print()

    # Embedding tokens/cost
    emb_tokens = cost_breakdown.get("embedding_tokens", 0)
    emb_cost = cost_breakdown.get("embedding_cost", 0)
    print(f"  Embedding:")
    print(f"    Tokens:        {emb_tokens:>6}")
    print(f"    Cost:          ${emb_cost:.6f}")
    print()

    # Total
    total_tokens = cost_breakdown.get("total_tokens", 0)
    total_cost = cost_breakdown.get("total_cost", 0)
    print(f"  {'─' * 40}")
    print(f"  TOTAL:")
    print(f"    Tokens:        {total_tokens:>6}")
    print(f"    Cost:          ${total_cost:.6f}")

    print()
    print("=" * 80)
    print("OTHER DEBUG FIELDS")
    print("=" * 80)
    print()

    print(f"  Query text:              {debug_metrics.get('query_text', 'N/A')}")
    print(f"  Query type:              {debug_metrics.get('query_type', 'N/A')}")
    print(f"  Classification conf:     {debug_metrics.get('classification_confidence', 0):.2f}")
    print(f"  Enhanced query:          {debug_metrics.get('enhanced_query', 'N/A')}")
    print(f"  Sources found:           {debug_metrics.get('sources_found', 0)}")
    print(f"  Sources used:            {debug_metrics.get('sources_used', 0)}")
    print(f"  Best confidence:         {debug_metrics.get('best_confidence', 0):.2f}")
    print(f"  From context:            {debug_metrics.get('from_context', False)}")

    print()
    print("=" * 80)
    print("FULL DEBUG_METRICS JSON")
    print("=" * 80)
    print()
    print(json.dumps(debug_metrics, indent=2))

    print()
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()

    # Check for missing query_intelligence_time_ms
    if query_intelligence_time == 0:
        print("❌ ISSUE: query_intelligence_time_ms is 0 or missing!")
        print("   This explains the ~3765ms gap in your frontend.")
        print("   Backend is not populating this field correctly.")
        print()
    else:
        print(f"✅ query_intelligence_time_ms present: {query_intelligence_time:.0f}ms")
        print()

    # Check prompt token inclusion
    if qi_input < 500:
        print(f"⚠️  ISSUE: query_intelligence_input_tokens is only {qi_input}")
        print("   This seems low - system prompt should add ~500+ tokens")
        print("   Verify token tracking includes full prompt context")
        print()
    else:
        print(f"✅ Query intelligence input tokens look reasonable: {qi_input}")
        print()

    if resp_input < 800:
        print(f"⚠️  ISSUE: response_input_tokens is only {resp_input}")
        print("   This seems low - system prompt + KB context should be ~800+ tokens")
        print("   Verify token tracking includes full prompt context")
        print()
    else:
        print(f"✅ Response input tokens look reasonable: {resp_input}")
        print()

    # Check total time
    if total_time > 5000:
        print(f"⚠️  ISSUE: Total time is {total_time:.0f}ms (>{5000}ms)")
        print("   Expected ~3000-4000ms after optimization")
        print("   Possible causes:")
        print("   - Query intelligence taking too long")
        print("   - Network latency")
        print("   - Multiple LLM calls happening")
        print()
    else:
        print(f"✅ Total time is reasonable: {total_time:.0f}ms")
        print()

    print("=" * 80)
    print("RESPONSE TEXT (first 200 chars)")
    print("=" * 80)
    print()
    print(result.get("response", "")[:200])
    print()


if __name__ == "__main__":
    asyncio.run(test_debug_metrics())
