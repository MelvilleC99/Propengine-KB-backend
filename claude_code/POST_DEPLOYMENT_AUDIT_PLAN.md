# Post-Deployment Audit Plan

**Date:** February 1, 2026
**Purpose:** Identify and fix the 2190ms system overhead bottleneck

---

## Audit Objectives

1. **Find where 2190ms system overhead is coming from**
   - Redis operations
   - Token tracking
   - Pydantic validation
   - Session management
   - Other Python overhead

2. **Verify industry standard compliance**
   - Compare to benchmarks
   - Identify anti-patterns
   - Document improvements needed

3. **Create optimization roadmap**
   - Prioritize by impact
   - Estimate effort
   - Plan implementation

---

## Phase 1: Baseline Measurement (30 minutes)

### 1.1 Test Current Performance
```bash
cd /Users/melville/Documents/Propengine-KB-backend/claude_code

# Run timing test
python3 test_real_query_timing.py > baseline_results.txt

# Expected output:
# Query Intelligence: ~2200ms
# Response Generation: ~2000ms
# System Overhead: ~2200ms
# Total: ~6500ms
```

### 1.2 Identify Overhead Components
- [ ] Session management time
- [ ] Token tracking time
- [ ] Pydantic validation time
- [ ] Redis operation time
- [ ] JSON serialization time

---

## Phase 2: Redis Performance Audit (1 hour)

### 2.1 Check Redis Connection
```bash
# Test Redis latency
redis-cli --latency

# Should be: <10ms
# If >50ms: Redis connection issue
```

### 2.2 Audit Session Manager
**File:** `src/memory/session_manager.py`

**Check:**
1. Are Redis operations using async?
2. Is connection pooling enabled?
3. Are we using pipelines for batch operations?
4. How many Redis calls per query?

**Test Script:**
```python
# claude_code/audit_redis_performance.py
import asyncio
import time
from src.memory.session_manager import SessionManager

async def audit_redis():
    sm = SessionManager()
    session_id = "audit_test"

    # Test get_context_for_llm
    start = time.time()
    context = sm.get_context_for_llm(session_id)
    elapsed = (time.time() - start) * 1000

    print(f"get_context_for_llm: {elapsed:.0f}ms")

    # Test add_message
    start = time.time()
    await sm.add_message(session_id, "user", "test", {})
    elapsed = (time.time() - start) * 1000

    print(f"add_message: {elapsed:.0f}ms")

    # Target: Both <50ms
    # If >200ms: CRITICAL ISSUE

asyncio.run(audit_redis())
```

### 2.3 Expected Findings
- [ ] Redis operations taking 300-500ms (should be <50ms)
- [ ] Synchronous calls instead of async
- [ ] No connection pooling
- [ ] Multiple round trips instead of pipeline

---

## Phase 3: Token Tracking Audit (45 minutes)

### 3.1 Audit Token Tracker
**File:** `src/analytics/tracking/token_tracker.py`

**Check:**
1. Is tracking synchronous or async?
2. How much computation per track call?
3. Can it run in background?

**Test Script:**
```python
# claude_code/audit_token_tracking.py
import time
from src.analytics.tracking import token_tracker

# Mock response object
class MockResponse:
    def __init__(self):
        self.usage_metadata = {
            'input_tokens': 1000,
            'output_tokens': 100
        }

# Test tracking performance
session_id = "test"
response = MockResponse()

start = time.time()
for _ in range(10):
    token_tracker.track_chat_usage(
        response=response,
        model="gpt-4o-mini",
        session_id=session_id,
        operation="test"
    )
elapsed = (time.time() - start) * 1000

print(f"10 track_chat_usage calls: {elapsed:.0f}ms")
print(f"Average per call: {elapsed/10:.0f}ms")

# Target: <5ms per call
# If >30ms: ISSUE

# Test get_cost_breakdown
start = time.time()
breakdown = token_tracker.get_cost_breakdown_for_session(session_id)
elapsed = (time.time() - start) * 1000

print(f"get_cost_breakdown: {elapsed:.0f}ms")

# Target: <20ms
# If >100ms: CRITICAL ISSUE
```

### 3.2 Expected Findings
- [ ] Cost calculations taking 200ms+ (should be <20ms)
- [ ] Synchronous operations blocking response
- [ ] No background processing

---

## Phase 4: Pydantic Validation Audit (30 minutes)

### 4.1 Check Validation Overhead
**Files:** `src/analytics/models/*.py`

**Test Script:**
```python
# claude_code/audit_pydantic_validation.py
import time
from src.analytics.models.query_metrics import QueryExecutionMetrics
from src.analytics.models.cost_breakdown import CostBreakdown

# Test data
test_data = {
    "query_text": "test query",
    "query_type": "howto",
    "classification_confidence": 0.8,
    "total_time_ms": 1000.0,
    # ... full data
}

# Test WITH validation
start = time.time()
for _ in range(100):
    metrics = QueryExecutionMetrics(**test_data)
elapsed_with = (time.time() - start) * 1000

print(f"100 validations WITH validation: {elapsed_with:.0f}ms")
print(f"Average: {elapsed_with/100:.0f}ms")

# Test WITHOUT validation (model_construct)
start = time.time()
for _ in range(100):
    metrics = QueryExecutionMetrics.model_construct(**test_data)
elapsed_without = (time.time() - start) * 1000

print(f"100 validations WITHOUT validation: {elapsed_without:.0f}ms")
print(f"Average: {elapsed_without/100:.0f}ms")

print(f"\nValidation overhead per call: {(elapsed_with - elapsed_without)/100:.0f}ms")

# Target: <2ms per validation
# If >10ms: Can optimize
```

### 4.2 Expected Findings
- [ ] Validation taking 150-250ms per query
- [ ] Running in production (should skip)
- [ ] Can save 200ms+ by using model_construct

---

## Phase 5: Complete Trace Analysis (1 hour)

### 5.1 Add Detailed Timing Logs

**Add to orchestrator.py temporarily:**
```python
import time

async def process_query(self, query: str, session_id: str, user_type: str = "both"):
    start_total = time.time()

    # Step 1: Store message
    t1 = time.time()
    await self.session_manager.add_message(session_id, "user", query, {})
    logger.warning(f"⏱️  Store message: {(time.time()-t1)*1000:.0f}ms")

    # Step 2: Get context
    t1 = time.time()
    context_data = self.session_manager.get_context_for_llm(session_id)
    logger.warning(f"⏱️  Get context: {(time.time()-t1)*1000:.0f}ms")

    # ... add timing for EVERY major operation

    # At the end:
    logger.warning(f"⏱️  TOTAL (measured): {(time.time()-start_total)*1000:.0f}ms")
```

### 5.2 Run Full Trace
```bash
# Run query and check logs
python3 test_real_query_timing.py 2>&1 | grep "⏱️"

# Should show timing for each step
```

### 5.3 Build Timing Waterfall
Create a visual breakdown:
```
0ms ────────────────────────────────────── 6500ms
│
├─ Store message:           250ms  ████████
├─ Get context:             300ms  ██████████
├─ Classification:           2ms   █
├─ Query Intelligence:    2200ms  ████████████████████████████████████████████████████████████████████████
├─ Search:                    0ms
├─ Response Generation:   2100ms  ██████████████████████████████████████████████████████████████████████
├─ Token tracking:          350ms  ███████████
├─ Build debug metrics:     100ms  ███
├─ Store response:          250ms  ████████
└─ Other overhead:          950ms  ██████████████████████
```

---

## Phase 6: Analysis & Recommendations (30 minutes)

### 6.1 Summarize Findings

**Expected bottlenecks:**
1. Redis operations: 500-600ms
2. Token tracking: 350ms
3. Pydantic validation: 250ms
4. Other overhead: 1000ms

### 6.2 Create Optimization Priority List

**High Priority (>500ms savings):**
- [ ] Optimize Redis operations
- [ ] Make token tracking async

**Medium Priority (200-500ms savings):**
- [ ] Skip Pydantic validation in production
- [ ] Reduce context building overhead

**Low Priority (<200ms savings):**
- [ ] Optimize logging
- [ ] Reduce JSON serialization

### 6.3 Document Industry Gaps

Create comparison table:
```
| Component | Current | Industry | Gap | Fix |
|-----------|---------|----------|-----|-----|
| Redis ops | 500ms   | 50ms     | 450ms | Async + pool |
| Token track | 350ms | 20ms     | 330ms | Background |
| Validation | 250ms  | 0ms      | 250ms | Skip in prod |
```

---

## Phase 7: Create Implementation Plan (30 minutes)

### 7.1 Quick Wins (Can do today)
1. Skip Pydantic validation in production
2. Move token tracking to background

**Estimated savings:** 600ms
**Effort:** 2 hours

### 7.2 Medium Term (Can do this week)
1. Optimize Redis connection
2. Add Redis connection pooling
3. Use Redis pipelines

**Estimated savings:** 450ms
**Effort:** 1 day

### 7.3 Long Term (Strategic improvements)
1. Consider local vector DB (Qdrant)
2. Switch to local embeddings
3. Regional API optimization

**Estimated savings:** 2500ms
**Effort:** 1-2 weeks

---

## Deliverables

After audit, create:

1. **AUDIT_RESULTS.md**
   - Findings summary
   - Bottleneck breakdown
   - Performance comparison

2. **OPTIMIZATION_ROADMAP.md**
   - Prioritized improvements
   - Effort estimates
   - Expected impact

3. **QUICK_WINS_IMPLEMENTATION.md**
   - Code changes for immediate fixes
   - Testing plan
   - Deployment steps

---

## Timeline

- **Phase 1-2:** 1.5 hours (Redis audit)
- **Phase 3-4:** 1.25 hours (Token tracking + Pydantic)
- **Phase 5-6:** 1.5 hours (Complete trace + analysis)
- **Phase 7:** 0.5 hours (Implementation plan)

**Total:** ~4.75 hours

---

## Success Metrics

Audit is successful if we:
1. ✅ Identify exact source of 2190ms overhead
2. ✅ Create actionable optimization plan
3. ✅ Find 1000ms+ of easy savings
4. ✅ Document gap to industry standards

**Ready to audit after deployment!** 🔍
