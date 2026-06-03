"""Audience isolation guarantee — the safety net for "customers must NEVER see internal docs".

Runs the REAL search path (including the fallback tiers and parent-document expansion)
against AstraDB and asserts:
  - a customer (external) search never returns a chunk tagged userType="internal"
  - a support  (internal) search never returns a chunk tagged userType="external"

Run directly (needs the .env / live AstraDB):
    .venv/bin/python tests/test_isolation.py
"""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from src.query.vector_search import VectorSearch
from src.agent.search import SearchStrategy, ParentDocumentRetrieval
from src.analytics import QueryMetricsCollector

# Include a "show me all the steps" style query — that one triggers parent-doc expansion,
# which is the path the isolation fix hardened.
QUERIES = [
    ("how do I create a listing", "how_to"),
    ("how do I archive a listing", "how_to"),
    ("show me all the steps to create a listing", "how_to"),
    ("I can't publish to the portals", "error"),
]


async def _user_types_for(strategy, parent, query, query_type, audience):
    results, _ = await strategy.search_with_fallback(
        query=query, query_type=query_type, user_type_filter=audience,
        parent_retrieval_handler=parent, session_id="isolation-test",
    )
    return [r.get("metadata", {}).get("userType") for r in results]


async def main():
    vs = VectorSearch()
    metrics = QueryMetricsCollector()
    parent = ParentDocumentRetrieval(vs)
    strategy = SearchStrategy(vs, metrics)

    failures = []
    for query, qtype in QUERIES:
        metrics.start_query(query)
        ext = await _user_types_for(strategy, parent, query, qtype, "external")
        metrics.start_query(query)
        intl = await _user_types_for(strategy, parent, query, qtype, "internal")

        if "internal" in ext:
            failures.append(f"LEAK: customer query {query!r} returned internal chunk(s): {ext}")
        if "external" in intl:
            failures.append(f"LEAK: support query {query!r} returned external chunk(s): {intl}")
        print(f"  {query!r}\n     external → {set(ext) or '∅'}    internal → {set(intl) or '∅'}")

    print()
    if failures:
        for f in failures:
            print("  ❌", f)
        raise SystemExit("❌ ISOLATION TEST FAILED — audience leak detected")
    print("✅ ISOLATION OK — customer never saw 'internal'; support never saw 'external'")


if __name__ == "__main__":
    asyncio.run(main())
