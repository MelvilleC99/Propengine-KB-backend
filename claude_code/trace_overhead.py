"""Trace where the 2190ms overhead is coming from"""

import asyncio
import time
from src.agent.orchestrator import Agent

# Monkey patch to add timing logs
original_time = time.time

call_stack = []

def traced_time():
    """Traced version of time.time()"""
    result = original_time()
    # Stack trace to see who's calling
    import traceback
    stack = traceback.extract_stack()
    if len(stack) > 2:
        caller = stack[-2]
        call_stack.append({
            'time': result,
            'file': caller.filename.split('/')[-1],
            'line': caller.lineno,
            'function': caller.name
        })
    return result

# Patch time.time
time.time = traced_time

async def trace_overhead():
    print("=" * 80)
    print("TRACING OVERHEAD - WHERE IS THE 2190ms?")
    print("=" * 80)
    print()

    session_id = f"trace_test_{int(original_time())}"
    query = "how do I upload photos"

    print(f"Query: '{query}'")
    print(f"Session: {session_id}")
    print()

    # Clear call stack
    call_stack.clear()

    # Run query
    start = original_time()
    agent = Agent()
    result = await agent.process_query(query=query, session_id=session_id)
    total_elapsed = (original_time() - start) * 1000

    print()
    print("=" * 80)
    print("TIME ANALYSIS")
    print("=" * 80)
    print()

    debug_metrics = result.get("debug_metrics", {})

    # Get reported times
    qi_time = debug_metrics.get("query_intelligence_time_ms", 0)
    resp_time = debug_metrics.get("response_generation_time_ms", 0)
    total_reported = debug_metrics.get("total_time_ms", 0)

    operations_total = qi_time + resp_time
    overhead = total_elapsed - operations_total

    print(f"Query Intelligence:    {qi_time:>6.0f}ms")
    print(f"Response Generation:   {resp_time:>6.0f}ms")
    print(f"────────────────────────────────")
    print(f"Operations Total:      {operations_total:>6.0f}ms")
    print(f"Actual Total:          {total_elapsed:>6.0f}ms")
    print(f"Reported Total:        {total_reported:>6.0f}ms")
    print(f"────────────────────────────────")
    print(f"OVERHEAD:              {overhead:>6.0f}ms")
    print()

    # Analyze call stack to find time gaps
    print("=" * 80)
    print("OVERHEAD BREAKDOWN")
    print("=" * 80)
    print()

    # Group calls by function
    from collections import defaultdict
    function_times = defaultdict(list)

    for i in range(len(call_stack) - 1):
        current = call_stack[i]
        next_call = call_stack[i + 1]

        delta_ms = (next_call['time'] - current['time']) * 1000

        if delta_ms > 50:  # Only log significant gaps (>50ms)
            function_times[current['function']].append(delta_ms)

    # Sort by total time
    sorted_functions = sorted(
        function_times.items(),
        key=lambda x: sum(x[1]),
        reverse=True
    )

    print("Top time consumers (>50ms gaps):")
    print()

    for func, times in sorted_functions[:15]:
        total = sum(times)
        count = len(times)
        avg = total / count if count > 0 else 0

        print(f"{func:40s} {total:>8.0f}ms ({count:>3} calls, avg: {avg:>6.0f}ms)")

    print()
    print("=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print()

    if overhead > 2000:
        print(f"⚠️  HIGH OVERHEAD: {overhead:.0f}ms is too much!")
        print()
        print("Likely causes:")
        print("1. Session management (Redis get/set operations)")
        print("2. Context building (retrieving message history)")
        print("3. Pydantic model validation")
        print("4. Token tracking calculations")
        print("5. Logging overhead")
        print("6. JSON serialization")
        print()
        print("This is NOT normal for a production RAG system.")
        print("Industry standard overhead: <500ms")
        print()

if __name__ == "__main__":
    asyncio.run(trace_overhead())

    # Restore original time
    time.time = original_time
