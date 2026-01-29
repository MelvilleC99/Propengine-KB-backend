# 🎯 COMPREHENSIVE ANALYTICS REFACTOR PLAN

**Date:** January 29, 2026  
**Status:** 📋 PLANNING

---

## **YOUR CONCERNS (ALL VALID!)**

1. ✅ **Missing LLM generation time** - Not being tracked
2. ✅ **Cost tracking not in debug** - Tracked but not displayed
3. ✅ **Should use Pydantic** - Currently using dataclasses
4. ✅ **Too many analytics files** - Scattered across codebase

---

## **CURRENT STATE ANALYSIS**

### **Analytics Files:**

```
/src/admin/query_metrics.py
- QueryExecutionMetrics (dataclass)
- SearchExecutionMetrics (dataclass)
- QueryMetricsCollector (collector class)

/src/utils/token_tracker.py
- TokenUsage (dataclass)
- TokenTracker (tracker class)
- Tracks: input_tokens, output_tokens, cost per operation

/src/utils/cost_calculator.py
- CostCalculator (class)
- Reads pricing from YAML
- Calculates costs

/src/analytics/kb_analytics.py (if exists)
- KB usage tracking
- Query patterns
```

### **Current Data Flow:**

```
User Query
    ↓
Orchestrator starts
    ↓
[Track classification time]     ← ✅ Tracked
    ↓
[Track query building time]     ← ✅ Tracked
    ↓
[Track embedding time]          ← ✅ Tracked
    ↓
[Track search time]             ← ✅ Tracked
    ↓
[Track reranking time]          ← ✅ Tracked
    ↓
[Generate LLM response]         ← ❌ NOT TRACKED!
    ↓
[Calculate total time]          ← ✅ Tracked
```

### **Cost Tracking:**

```python
# In token_tracker.py - THIS EXISTS!
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost: float                    # ← COST IS TRACKED!
    operation: str                 # ← "response_generation", "embedding", etc.
```

**Problem:** Cost is tracked per LLM call but NOT aggregated into QueryExecutionMetrics!

---

## **THE PROBLEMS**

### **Problem 1: LLM Generation Time Missing**

**Location:** `/src/agent/orchestrator.py` line ~253

**Current:**
```python
# === STEP 11: Generate response ===
response = await self.response_generator.generate_response(
    query, contexts, conversation_context
)
# No timing tracked!
```

**Should be:**
```python
# === STEP 11: Generate response ===
llm_start = time.time()
response = await self.response_generator.generate_response(
    query, contexts, conversation_context
)
llm_time_ms = (time.time() - llm_start) * 1000
self.metrics_collector.record_response_time(llm_time_ms)
```

---

### **Problem 2: Cost Not in Metrics**

**Current QueryExecutionMetrics (query_metrics.py):**
```python
@dataclass
class QueryExecutionMetrics:
    # Timing
    total_time_ms: float = 0.0
    classification_time_ms: float = 0.0
    # ... but NO COST FIELDS!
```

**Should have:**
```python
@dataclass  
class QueryExecutionMetrics:
    # Timing
    total_time_ms: float = 0.0
    
    # Cost breakdown
    embedding_cost: float = 0.0
    query_building_cost: float = 0.0  # If using LLM
    response_generation_cost: float = 0.0
    total_cost: float = 0.0
```

---

### **Problem 3: Dataclasses vs Pydantic**

**Current (dataclasses):**
```python
from dataclasses import dataclass, field, asdict

@dataclass
class QueryExecutionMetrics:
    query_text: str = ""
    sources_found: int = 0
```

**Pydantic (better):**
```python
from pydantic import BaseModel, Field

class QueryExecutionMetrics(BaseModel):
    query_text: str = ""
    sources_found: int = Field(default=0, ge=0)  # Validation!
    
    model_config = {
        "json_schema_extra": {
            "example": {...}
        }
    }
```

**Why Pydantic is better:**
- ✅ Built-in validation
- ✅ Better JSON serialization
- ✅ Type coercion
- ✅ Better FastAPI integration
- ✅ JSON schema generation
- ✅ Immutability options
- ✅ Better error messages

---

### **Problem 4: Fragmented Analytics**

**Current structure:**
```
query_metrics.py       → Query execution metrics
token_tracker.py       → Token & cost tracking
cost_calculator.py     → Cost calculation
kb_analytics.py        → KB usage tracking
```

**Should be unified:**
```
/src/analytics/
    __init__.py
    models.py          → All Pydantic models
    collectors.py      → Metric collection
    trackers.py        → Token/cost tracking
    aggregators.py     → Combine metrics
```

---

## **THE SOLUTION - COMPREHENSIVE REFACTOR**

### **Phase 1: Add Missing Tracking (Quick Win)**

**Files to modify:**
1. `/src/agent/orchestrator.py` - Add LLM timing
2. `/src/admin/query_metrics.py` - Add cost fields
3. Frontend already ready to display!

**Estimated time:** 30 minutes

---

### **Phase 2: Migrate to Pydantic (Medium Effort)**

**New file structure:**
```python
# /src/analytics/models.py
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime

class SearchExecutionMetrics(BaseModel):
    """Vector search execution metrics"""
    filters_applied: Dict[str, str] = Field(default_factory=dict)
    documents_scanned: int = Field(default=0, ge=0)
    documents_matched: int = Field(default=0, ge=0)
    documents_returned: int = Field(default=0, ge=0)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    embedding_time_ms: float = Field(default=0.0, ge=0.0)
    search_time_ms: float = Field(default=0.0, ge=0.0)
    rerank_time_ms: float = Field(default=0.0, ge=0.0)

class CostBreakdown(BaseModel):
    """Cost breakdown for query execution"""
    embedding_cost: float = Field(default=0.0, ge=0.0)
    query_building_cost: float = Field(default=0.0, ge=0.0)
    response_generation_cost: float = Field(default=0.0, ge=0.0)
    total_cost: float = Field(default=0.0, ge=0.0)
    
    # Token details
    embedding_tokens: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)

class QueryExecutionMetrics(BaseModel):
    """Complete query execution metrics with validation"""
    # Query metadata
    query_text: str
    query_type: str
    classification_confidence: float = Field(ge=0.0, le=1.0)
    
    # Enhanced query
    enhanced_query: str = ""
    query_category: Optional[str] = None
    query_intent: Optional[str] = None
    query_tags: List[str] = Field(default_factory=list)
    
    # Search execution
    search_execution: SearchExecutionMetrics = Field(
        default_factory=SearchExecutionMetrics
    )
    search_attempts: List[Dict] = Field(default_factory=list)
    
    # Results
    sources_found: int = Field(default=0, ge=0)
    sources_used: int = Field(default=0, ge=0)
    best_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    
    # Timing
    total_time_ms: float = Field(default=0.0, ge=0.0)
    classification_time_ms: float = Field(default=0.0, ge=0.0)
    query_building_time_ms: float = Field(default=0.0, ge=0.0)
    response_generation_time_ms: float = Field(default=0.0, ge=0.0)  # NEW!
    
    # Cost breakdown (NEW!)
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    
    # Escalation
    escalated: bool = False
    escalation_reason: str = "none"
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query_text": "how do I upload photos",
                "query_type": "howto",
                "classification_confidence": 0.85,
                # ...
            }
        }
    }
```

**Estimated time:** 2-3 hours

---

### **Phase 3: Unified Analytics Module (Longer Term)**

Consolidate all analytics into single module.

**Estimated time:** 4-6 hours

---

## **RECOMMENDED APPROACH**

### **Option A: Quick Fix (30 min)**

Just add the missing pieces to existing code:
1. Track LLM generation time
2. Add cost fields to existing dataclass
3. Pass to frontend

**Pros:** Fast, minimal changes  
**Cons:** Still using dataclasses, still fragmented

---

### **Option B: Pydantic Migration (3 hours)**

Migrate to Pydantic properly:
1. Create new `/src/analytics/models.py` with Pydantic
2. Add LLM timing + cost tracking
3. Update collectors to use new models
4. Keep old files for backward compat initially
5. Gradually migrate

**Pros:** Better structure, validation, future-proof  
**Cons:** Takes longer, more testing needed

---

### **Option C: Full Refactor (6+ hours)**

Complete analytics overhaul:
1. Unified analytics module
2. Pydantic models
3. Better separation of concerns
4. Comprehensive testing

**Pros:** Perfect architecture  
**Cons:** Long time investment

---

## **MY RECOMMENDATION**

### **Do Option B (Pydantic Migration)**

**Why:**
- You're right that Pydantic is better
- 3 hours is manageable
- Sets up for future improvements
- Still gets you cost tracking today

**Steps:**
1. Create new Pydantic models (30 min)
2. Add LLM timing tracking (15 min)
3. Integrate cost tracking (30 min)
4. Update collectors (45 min)
5. Test & validate (45 min)
6. Frontend already ready! (0 min)

---

## **IMMEDIATE ACTION PLAN**

**If you want to start NOW:**

1. **Create `/src/analytics/models.py`** with Pydantic models
2. **Update orchestrator** to track LLM time
3. **Add cost aggregation** to metrics collector
4. **Frontend displays it** automatically!

---

**What do you want to do?**

A) Quick fix (30 min) - just add missing tracking  
B) Pydantic migration (3 hours) - do it right  
C) Let's discuss the approach more first

Let me know and I'll implement it! 🚀
