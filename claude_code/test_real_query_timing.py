"""Test real query timing with proper KB search"""

import asyncio
import time
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager

async def test_real_query():
    print("=" * 80)
    print("TESTING REAL QUERY WITH KB SEARCH")
    print("=" * 80)
    print()

    # Use fresh session
    session_id = f"timing_test_{int(time.time())}"
    query = "how do I upload photos"

    print(f"Query: '{query}'")
    print(f"Session ID: {session_id} (fresh)")
    print()

    # Initialize agent
    agent = Agent()

    # Time the full query
    print("Processing query...")
    start = time.time()

    result = await agent.process_query(
        query=query,
        session_id=session_id
    )

    total_elapsed = (time.time() - start) * 1000

    print()
    print("=" * 80)
    print("TIMING RESULTS")
    print("=" * 80)
    print()

    debug_metrics = result.get("debug_metrics", {})

    # Extract timings
    classification_time = debug_metrics.get("classification_time_ms", 0)
    qi_time = debug_metrics.get("query_intelligence_time_ms", 0)

    search_exec = debug_metrics.get("search_execution", {})
    embedding_time = search_exec.get("embedding_time_ms", 0)
    search_time = search_exec.get("search_time_ms", 0)
    rerank_time = search_exec.get("rerank_time_ms", 0)

    response_time = debug_metrics.get("response_generation_time_ms", 0)
    reported_total = debug_metrics.get("total_time_ms", 0)

    print(f"  Classification:       {classification_time:>6.0f}ms")
    print(f"  Query Intelligence:   {qi_time:>6.0f}ms")
    print(f"  Embedding:            {embedding_time:>6.0f}ms")
    print(f"  Search:               {search_time:>6.0f}ms")
    print(f"  Reranking:            {rerank_time:>6.0f}ms")
    print(f"  Response Generation:  {response_time:>6.0f}ms")
    print(f"  {'─' * 40}")

    calculated_sum = (
        classification_time + qi_time + embedding_time +
        search_time + rerank_time + response_time
    )

    print(f"  Calculated Sum:       {calculated_sum:>6.0f}ms")
    print(f"  Reported Total:       {reported_total:>6.0f}ms")
    print(f"  Actual Elapsed:       {total_elapsed:>6.0f}ms")
    print()

    # Analyze performance
    print("=" * 80)
    print("PERFORMANCE ANALYSIS")
    print("=" * 80)
    print()

    # Check if KB search was performed
    sources_found = debug_metrics.get("sources_found", 0)
    from_context = debug_metrics.get("from_context", False)

    if from_context:
        print("❌ Query answered from context (no KB search)")
        print("   This shouldn't happen for a fresh session!")
        print()
    elif sources_found > 0:
        print(f"✅ KB search performed, found {sources_found} sources")
        print()
    else:
        print("⚠️  KB search performed but found 0 sources")
        print("   Your KB might not have content about uploading photos")
        print()

    # Check individual timings
    if qi_time > 1800:
        print(f"⚠️  Query Intelligence slow: {qi_time:.0f}ms (expected ~1400ms)")
        print(f"   Network latency: ~{qi_time - 1400:.0f}ms")
        print()

    if embedding_time > 0:
        if embedding_time > 1500:
            print(f"⚠️  Embedding slow: {embedding_time:.0f}ms")
        else:
            print(f"✅ Embedding time acceptable: {embedding_time:.0f}ms")
        print()

    if response_time > 2500:
        print(f"⚠️  Response Generation slow: {response_time:.0f}ms")
        print(f"   This is OpenAI API latency (network + processing)")
        print()

    # Overall assessment
    if total_elapsed < 4000:
        print(f"🎉 EXCELLENT: Total time {total_elapsed:.0f}ms (<4s)")
    elif total_elapsed < 6000:
        print(f"✅ GOOD: Total time {total_elapsed:.0f}ms (4-6s)")
    elif total_elapsed < 8000:
        print(f"⚠️  ACCEPTABLE: Total time {total_elapsed:.0f}ms (6-8s)")
        print("   This is expected with:")
        print("   - OpenAI API network latency (~1-2s)")
        print("   - Multiple LLM calls (Query Intelligence + Response)")
        print("   - Vector search operations")
    else:
        print(f"❌ SLOW: Total time {total_elapsed:.0f}ms (>8s)")
        print("   Investigate network latency or API issues")

    print()
    print("=" * 80)
    print("OPTIMIZATION SUGGESTIONS")
    print("=" * 80)
    print()

    print("🚀 To reduce latency:")
    print()
    print("1. Use GPT-4o-mini for Query Intelligence (you're already doing this)")
    print()
    print("2. Consider caching:")
    print("   - Cache query intelligence results for similar queries")
    print("   - Cache embeddings for common queries")
    print()
    print("3. Parallel processing:")
    print("   - Run Query Intelligence and Embedding in parallel")
    print("   - This could save ~1200-1500ms!")
    print()
    print("4. Network optimization:")
    print("   - Use OpenAI's batch API for non-realtime queries")
    print("   - Consider Azure OpenAI for better latency in your region")
    print()
    print("5. Reduce token usage:")
    print("   - Shorter prompts = faster responses")
    print("   - Summarize conversation context more aggressively")
    print()

    # Show response preview
    print("=" * 80)
    print("RESPONSE PREVIEW")
    print("=" * 80)
    print()
    print(result.get("response", "")[:300])
    print()

if __name__ == "__main__":
    asyncio.run(test_real_query())
