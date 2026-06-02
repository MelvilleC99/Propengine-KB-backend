"""End-to-end pipeline latency audit — runs real queries through the agent and
prints the complete per-stage timing breakdown (with the new instrumentation)."""

import asyncio
import time
import logging
from dotenv import load_dotenv

load_dotenv()

# Quiet the noise, but let warnings/errors through
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def show(label, dm, wall_ms, result):
    se = dm.get("search_execution", {}) or {}
    rows = [
        ("Classification",      dm.get("classification_time_ms", 0)),
        ("Context load",        dm.get("context_load_time_ms", 0)),
        ("Query Intelligence",  dm.get("query_intelligence_time_ms", 0)),
        ("Embedding",           se.get("embedding_time_ms", 0)),
        ("Search",              se.get("search_time_ms", 0)),
        ("Reranking",           se.get("rerank_time_ms", 0)),
        ("Response Generation", dm.get("response_generation_time_ms", 0)),
    ]
    accounted = sum(v for _, v in rows)
    total = dm.get("total_time_ms", 0)
    print(f"\n{'='*64}\nQUERY: {label}\n{'='*64}")
    print(f"Response : {(result.get('response') or '')[:160].strip()}...")
    print(f"Confidence: {result.get('confidence')}  | Sources: {len(result.get('sources', []))}"
          f"  | Escalation: {result.get('requires_escalation')}")
    print("-" * 64)
    for name, v in rows:
        bar = "█" * int(v / 100)
        print(f"  {name:<20}{v:>7.0f}ms  {bar}")
    print("-" * 64)
    print(f"  {'accounted':<20}{accounted:>7.0f}ms")
    print(f"  {'unaccounted':<20}{total - accounted:>7.0f}ms  (context-build/cost-agg/overhead)")
    print(f"  {'BACKEND TOTAL':<20}{total:>7.0f}ms")
    print(f"  {'WALL CLOCK':<20}{wall_ms:>7.0f}ms  (incl. python overhead)")


async def main():
    t_init = time.time()
    from src.agent.orchestrator import Agent
    agent = Agent()
    print(f"\n[Agent init: {(time.time()-t_init)*1000:.0f}ms]")

    # Test the SAME query across all 3 audience filters to find why results differ
    query = "how do I archive a listing"
    for filt in [None, "internal", "external"]:
        sid = agent.session_manager.create_session({})
        t0 = time.time()
        try:
            result = await agent.process_query(
                query=query, session_id=sid, user_info={}, user_type_filter=filt
            )
            wall = (time.time() - t0) * 1000
            dm = result.get("debug_metrics", {}) or {}
            show(f"{query}  [filter={filt}]", dm, wall, result)
        except Exception as e:
            print(f"\nQUERY '{query}' [filter={filt}] FAILED: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
