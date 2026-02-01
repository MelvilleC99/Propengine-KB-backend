# Debug Metrics Issues and Fixes

**Date:** February 1, 2026
**Status:** 🔧 FIXING

## Issues Identified

### Issue 1: Missing Timer Starts
**Problem:** Timers are being stopped without being started

**Evidence:**
```python
# orchestrator.py line 119
query_type, classification_confidence = self.classifier.classify(query)
self.metrics_collector.record_classification(query_type, classification_confidence)

# metrics_collector.py line 46
self.current_metrics.classification_time_ms = self._stop_timer("classification")
# ❌ Timer "classification" was never started!
```

**Impact:**
- `classification_time_ms` = 0 or error
- Missing timing data in debug_metrics

---

### Issue 2: Search Execution Metrics Not Populated
**Problem:** When answering from context, search_execution fields are empty

**Evidence:**
```python
# When routing to answer_from_context, we skip search entirely
# So search_execution has all default values (0)
```

**Impact:**
- `embedding_time_ms` = 0
- `search_time_ms` = 0
- All search metrics = 0

---

### Issue 3: Prompt Tokens May Not Be Tracked
**Problem:** Need to verify token tracking includes system prompts

**Current Flow:**
```python
# response_generator.py
response = await self.llm.ainvoke([HumanMessage(content=full_prompt)])

# token_tracker.py
input_tokens = usage_metadata.get('input_tokens', 0)  # Should include everything
```

**Verification Needed:**
- Check if `input_tokens` from LLM includes system prompt
- Check if conversation context tokens are counted

---

### Issue 4: 7-Second Query Time
**Expected:** ~3-4 seconds with optimization
**Actual:** ~7 seconds

**Possible Causes:**
1. Query intelligence not being called efficiently
2. Multiple LLM calls happening
3. Network latency
4. Token tracking overhead

---

## Fixes to Implement

### Fix 1: Add Missing Timer Starts

**File:** `src/agent/orchestrator.py`

**Before:**
```python
# Line 119
query_type, classification_confidence = self.classifier.classify(query)
self.metrics_collector.record_classification(query_type, classification_confidence)
```

**After:**
```python
# Start timer before classification
self.metrics_collector._start_timer("classification")
query_type, classification_confidence = self.classifier.classify(query)
self.metrics_collector.record_classification(query_type, classification_confidence)
```

---

### Fix 2: Add Detailed Timing Breakdown Logging

**File:** `src/analytics/collectors/metrics_collector.py`

**Add to finalize_metrics():**
```python
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
```

---

### Fix 3: Verify Token Tracking Includes Prompts

**Test Script:**
```python
# Test to verify system prompt tokens are counted
import asyncio
from src.agent.orchestrator import Agent

async def test_token_tracking():
    agent = Agent()
    result = await agent.process_query(
        query="test query",
        session_id="test123"
    )

    debug = result.get("debug_metrics", {})
    cost = debug.get("cost_breakdown", {})

    print("Query Intelligence:")
    print(f"  Input tokens: {cost.get('query_intelligence_input_tokens', 0)}")
    print(f"  Output tokens: {cost.get('query_intelligence_output_tokens', 0)}")
    print(f"  (Should be > 500 if system prompt is included)")

    print("\nResponse Generation:")
    print(f"  Input tokens: {cost.get('response_input_tokens', 0)}")
    print(f"  Output tokens: {cost.get('response_output_tokens', 0)}")
    print(f"  (Should be > 800 if system+context prompt is included)")

asyncio.run(test_token_tracking())
```

---

### Fix 4: Investigate 7-Second Query Time

**Add timing instrumentation:**
```python
# In query_intelligence.py
async def analyze(...):
    import time
    start = time.time()

    response = await self.llm.ainvoke([HumanMessage(content=prompt)])

    elapsed = (time.time() - start) * 1000
    logger.info(f"🧠 Query intelligence LLM call: {elapsed:.0f}ms")

    # Track tokens...
```

---

## Expected Debug Metrics Structure

After fixes, the frontend should receive:

```json
{
  "debug_metrics": {
    "query_text": "how do I upload photos",
    "query_type": "howto",
    "classification_confidence": 0.85,
    "enhanced_query": "upload photos to listing",

    "classification_time_ms": 5,
    "query_intelligence_time_ms": 1450,
    "response_generation_time_ms": 2100,
    "total_time_ms": 4800,

    "search_execution": {
      "embedding_time_ms": 1323,
      "search_time_ms": 878,
      "rerank_time_ms": 0,
      "documents_returned": 3
    },

    "cost_breakdown": {
      "embedding_cost": 0.0001,
      "query_intelligence_cost": 0.0002,
      "query_intelligence_input_tokens": 650,
      "query_intelligence_output_tokens": 180,
      "response_generation_cost": 0.0005,
      "response_input_tokens": 1200,
      "response_output_tokens": 120,
      "total_cost": 0.0008,
      "total_tokens": 2150
    },

    "sources_found": 3,
    "sources_used": 2,
    "best_confidence": 0.82
  }
}
```

---

## Checklist

- [ ] Add timer start for classification
- [ ] Add detailed timing breakdown logging
- [ ] Verify prompt tokens are included in tracking
- [ ] Add instrumentation to query_intelligence
- [ ] Test with frontend to verify all fields populate
- [ ] Investigate any remaining slow queries

---

## Frontend Integration Notes

**Fields to Display:**

1. **Timing Breakdown** (in milliseconds):
   - Classification: `classification_time_ms`
   - Query Intelligence: `query_intelligence_time_ms`
   - Embedding: `search_execution.embedding_time_ms`
   - Search: `search_execution.search_time_ms`
   - Reranking: `search_execution.rerank_time_ms`
   - Response Generation: `response_generation_time_ms`
   - **Total**: `total_time_ms`

2. **Token/Cost Breakdown**:
   - Query Intelligence: `cost_breakdown.query_intelligence_input_tokens` + `query_intelligence_output_tokens`
   - Response Generation: `cost_breakdown.response_input_tokens` + `response_output_tokens`
   - Embedding: `cost_breakdown.embedding_tokens`
   - **Total Tokens**: `cost_breakdown.total_tokens`
   - **Total Cost**: `cost_breakdown.total_cost`

3. **Search Stats**:
   - Documents Returned: `search_execution.documents_returned`
   - Best Confidence: `best_confidence`
   - Sources Used: `sources_used`
