# 🔍 COMPLETE ANALYTICS ARCHITECTURE ANALYSIS

**Date:** January 29, 2026  
**Purpose:** Understanding current structure + planning refactor

---

## **PART 1: CURRENT FILE STRUCTURE**

### **Analytics-Related Files:**

```
/src/admin/
    query_metrics.py          ← Main metrics collection

/src/utils/
    token_tracker.py          ← Token usage + cost tracking
    cost_calculator.py        ← Cost calculation from YAML
    logging_helper.py         ← Logging utilities
    
/src/api/
    test_agent_routes.py      ← Test agent endpoint (sends debug_metrics)
    support_agent_routes.py   ← Support agent endpoint
    customer_agent_routes.py  ← Customer agent endpoint

/src/agent/
    orchestrator.py           ← Uses QueryMetricsCollector
```

---

## **PART 2: WHAT EACH FILE DOES**

### **1. `/src/admin/query_metrics.py` (Main Metrics)**

**Purpose:** Collects ALL query execution metrics

**Contains:**
```python
@dataclass
class SearchExecutionMetrics:
    filters_applied: Dict[str, str]
    documents_scanned: int
    documents_matched: int
    documents_returned: int
    similarity_threshold: float
    embedding_time_ms: float
    search_time_ms: float
    rerank_time_ms: float

@dataclass
class QueryExecutionMetrics:
    # Query metadata
    query_text: str
    query_type: str
    classification_confidence: float
    
    # Enhanced query
    enhanced_query: str
    query_category: str
    query_intent: str
    query_tags: List[str]
    
    # Search execution
    search_execution: SearchExecutionMetrics
    search_attempts: List[Dict]
    
    # Results
    sources_found: int
    sources_used: int
    best_confidence: float
    
    # Timing
    total_time_ms: float
    classification_time_ms: float
    query_building_time_ms: float
    response_generation_time_ms: float  # ← Exists but NOT populated!
    
    # Escalation
    escalated: bool
    escalation_reason: str

class QueryMetricsCollector:
    """Collects metrics during query processing"""
    
    def start_query(query_text: str)
    def record_classification(query_type, confidence)
    def record_query_enhancement(enhanced, category, intent, tags)
    def record_search_execution(filters, docs, times)
    def record_reranking(time)
    def record_results(sources, confidence)
    def finalize_metrics() -> Dict  # ← Returns dict for API
```

**Used by:** Orchestrator (`self.metrics_collector`)

---

### **2. `/src/utils/token_tracker.py` (Token + Cost)**

**Purpose:** Tracks token usage and calculates costs per LLM call

**Contains:**
```python
@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    timestamp: str
    cost: float                    # ← COST IS HERE!
    session_id: str
    operation: str                 # e.g., "response_generation"

class TokenTracker:
    """Tracks tokens and costs"""
    
    session_costs: Dict[str, Dict]  # session_id → cost breakdown
    
    def track_chat_usage(response, model, session_id, operation)
    def get_session_cost(session_id) → float
    def reset_session(session_id)
```

**Used by:** response_generator.py, query_builder.py (any LLM calls)

**Key insight:** Cost IS being tracked, just not aggregated into QueryExecutionMetrics!

---

### **3. `/src/utils/cost_calculator.py` (Cost Logic)**

**Purpose:** Calculates cost from token counts using YAML pricing

**Contains:**
```python
class CostCalculator:
    pricing: Dict  # Loaded from model_pricing.yaml
    
    def calculate_cost(model: str, input_tokens: int, output_tokens: int) → float
    def get_model_pricing(model: str) → Dict
```

**Pricing file:** `/src/config/model_pricing.yaml`
```yaml
gpt-4-turbo:
  input: 0.01   # per 1K tokens
  output: 0.03
gpt-4o-mini:
  input: 0.00015
  output: 0.0006
```

---

### **4. API Endpoints (How data reaches frontend)**

**Test Agent Route:** `/src/api/test_agent_routes.py`

**Request → Response Flow:**
```python
# 1. Frontend sends query
POST /api/agent/test/
{
    "message": "how do I upload photos",
    "session_id": "abc123",
    "user_info": {...}
}

# 2. Orchestrator processes query
result = await agent.process_query(
    query=request.message,
    session_id=session_id,
    user_type_filter=None
)

# 3. Orchestrator returns dict with:
{
    "response": "To upload photos...",
    "confidence": 0.72,
    "sources": [...],
    "query_type": "howto",
    "classification_confidence": 0.85,
    "enhanced_query": "upload photos listing",
    "query_metadata": {
        "category": "listing_management",
        "intent": "howto",
        "tags": ["photos", "upload"]
    },
    "debug_metrics": {  # ← QueryExecutionMetrics.finalize_metrics()
        "query_text": "how do I upload photos",
        "query_type": "howto",
        "classification_confidence": 0.85,
        "search_execution": {
            "documents_scanned": 6,
            "embedding_time_ms": 1294,
            "search_time_ms": 735,
            ...
        },
        "total_time_ms": 4958,
        # ... all metrics
    }
}

# 4. API returns Pydantic response model
return TestAgentResponse(
    response=result["response"],
    session_id=session_id,
    confidence=result["confidence"],
    sources=result["sources"],
    debug_metrics=result["debug_metrics"]  # ← Sent to frontend
)
```

**Frontend receives:**
```typescript
{
  response: "To upload photos...",
  debug_metrics: {
    query_text: "...",
    total_time_ms: 4958,
    search_execution: {...},
    // ... everything
  }
}
```

**Frontend displays:** `<DebugAnalytics metrics={debug_metrics} />`

---

## **PART 3: THE PROBLEMS**

### **Problem 1: LLM Time Not Tracked**

**Location:** `/src/agent/orchestrator.py` line ~253

**Current:**
```python
# === STEP 11: Generate response ===
response = await self.response_generator.generate_response(
    query, contexts, conversation_context
)
# No timing! ❌
```

**Should be:**
```python
# === STEP 11: Generate response ===
self.metrics_collector._start_timer("response_generation")
response = await self.response_generator.generate_response(
    query, contexts, conversation_context
)
llm_time = self.metrics_collector._stop_timer("response_generation")
self.metrics_collector.record_response_time(llm_time)  # ← Need to add this method
```

---

### **Problem 2: Cost Not in Metrics**

**TokenTracker has costs:**
```python
# In token_tracker.py
session_costs = {
    "session_123": {
        "response_generation": 0.0005,
        "query_building": 0.0001,
        "total": 0.0006
    }
}
```

**But QueryExecutionMetrics doesn't:**
```python
@dataclass
class QueryExecutionMetrics:
    total_time_ms: float = 0.0
    # NO cost fields! ❌
```

**Need to add:**
```python
@dataclass
class QueryExecutionMetrics:
    # Timing
    total_time_ms: float = 0.0
    
    # Cost breakdown (NEW!)
    embedding_cost: float = 0.0
    response_generation_cost: float = 0.0
    total_cost: float = 0.0
```

---

### **Problem 3: Dataclasses → Should be Pydantic**

**Current (dataclasses):**
```python
from dataclasses import dataclass, field

@dataclass
class QueryExecutionMetrics:
    sources_found: int = 0
    # No validation
    # No automatic JSON schema
    # No type coercion
```

**Pydantic (better):**
```python
from pydantic import BaseModel, Field

class QueryExecutionMetrics(BaseModel):
    sources_found: int = Field(default=0, ge=0)  # Must be >= 0
    total_time_ms: float = Field(default=0.0, ge=0.0)
    # ✅ Validation
    # ✅ JSON schema
    # ✅ Type coercion
    # ✅ Better FastAPI integration
```

---

### **Problem 4: Scattered Structure**

**Current:**
```
/src/admin/query_metrics.py     ← Metrics models
/src/utils/token_tracker.py     ← Cost tracking
/src/utils/cost_calculator.py   ← Cost calculation
```

**Issues:**
- "admin" folder for metrics? Confusing
- "utils" has too much responsibility
- No clear separation

---

## **PART 4: PROPOSED NEW STRUCTURE**

### **Option A: Minimal Changes (Keep Current Structure)**

```
/src/admin/
    query_metrics.py          ← Convert to Pydantic, add cost fields

/src/utils/
    token_tracker.py          ← Keep as-is
    cost_calculator.py        ← Keep as-is
```

**Pros:** Minimal disruption  
**Cons:** Still confusing structure

---

### **Option B: Create Analytics Module (RECOMMENDED)**

```
/src/analytics/
    __init__.py
    models.py                 ← All Pydantic models
    collectors.py             ← QueryMetricsCollector
    trackers.py               ← TokenTracker
    calculators.py            ← CostCalculator

/src/api/
    test_agent_routes.py      ← No change

/src/agent/
    orchestrator.py           ← Import from src.analytics
```

**Benefits:**
- ✅ Clear purpose
- ✅ All analytics in one place
- ✅ Better organization
- ✅ Easier to find/maintain

---

### **Option C: Full Separation (Most Organized)**

```
/src/analytics/
    __init__.py
    
    /models/
        __init__.py
        query_metrics.py       ← QueryExecutionMetrics (Pydantic)
        token_usage.py         ← TokenUsage (Pydantic)
        cost_breakdown.py      ← CostBreakdown (Pydantic)
    
    /collectors/
        __init__.py
        metrics_collector.py   ← QueryMetricsCollector
        token_tracker.py       ← TokenTracker
    
    /calculators/
        __init__.py
        cost_calculator.py     ← CostCalculator
```

**Benefits:**
- ✅ Maximum clarity
- ✅ Scalable
- ✅ Professional

**Cons:**
- More folders
- More imports

---

## **PART 5: PYDANTIC MIGRATION CHANGES**

### **Before (Dataclass):**

```python
from dataclasses import dataclass, field, asdict

@dataclass
class QueryExecutionMetrics:
    query_text: str = ""
    sources_found: int = 0
    total_time_ms: float = 0.0
    
# Usage
metrics = QueryExecutionMetrics(query_text="test", sources_found=5)
metrics_dict = asdict(metrics)  # Convert to dict
```

### **After (Pydantic):**

```python
from pydantic import BaseModel, Field
from typing import Optional

class QueryExecutionMetrics(BaseModel):
    query_text: str = Field(default="", description="User query")
    sources_found: int = Field(default=0, ge=0, description="Number of sources found")
    total_time_ms: float = Field(default=0.0, ge=0.0, description="Total query time")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "query_text": "how do I upload photos",
                "sources_found": 2,
                "total_time_ms": 4958.0
            }
        }
    }

# Usage
metrics = QueryExecutionMetrics(query_text="test", sources_found=5)
metrics_dict = metrics.model_dump()  # Convert to dict (Pydantic v2)
# OR metrics.dict() in Pydantic v1
```

**Key differences:**
```python
# Dataclass
asdict(obj)            → Pydantic: obj.model_dump()
obj = Class(**dict)    → Same in both

# Pydantic extras
model_validate()       → Validate external data
model_validate_json()  → Parse JSON directly
model_json_schema()    → Generate JSON schema
Field(ge=0)            → Validation (>=0)
```

---

## **PART 6: RECOMMENDED MIGRATION PLAN**

### **Step 1: Create New Analytics Module (30 min)**

```bash
mkdir -p src/analytics/models
mkdir -p src/analytics/collectors

# Create files
touch src/analytics/__init__.py
touch src/analytics/models/__init__.py
touch src/analytics/models/query_metrics.py
touch src/analytics/models/cost_breakdown.py
touch src/analytics/collectors/__init__.py
touch src/analytics/collectors/metrics_collector.py
```

---

### **Step 2: Create Pydantic Models (45 min)**

**File:** `/src/analytics/models/cost_breakdown.py`
```python
from pydantic import BaseModel, Field

class CostBreakdown(BaseModel):
    """Cost breakdown for query execution"""
    embedding_cost: float = Field(default=0.0, ge=0.0)
    query_building_cost: float = Field(default=0.0, ge=0.0)
    response_generation_cost: float = Field(default=0.0, ge=0.0)
    total_cost: float = Field(default=0.0, ge=0.0)
    
    # Token counts
    embedding_tokens: int = Field(default=0, ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
```

**File:** `/src/analytics/models/query_metrics.py`
```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from .cost_breakdown import CostBreakdown

class SearchExecutionMetrics(BaseModel):
    filters_applied: Dict[str, str] = Field(default_factory=dict)
    documents_scanned: int = Field(default=0, ge=0)
    documents_matched: int = Field(default=0, ge=0)
    documents_returned: int = Field(default=0, ge=0)
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    embedding_time_ms: float = Field(default=0.0, ge=0.0)
    search_time_ms: float = Field(default=0.0, ge=0.0)
    rerank_time_ms: float = Field(default=0.0, ge=0.0)

class QueryExecutionMetrics(BaseModel):
    # Query metadata
    query_text: str
    query_type: str
    classification_confidence: float = Field(ge=0.0, le=1.0)
    
    # Enhanced query
    enhanced_query: str = ""
    query_category: Optional[str] = None
    query_intent: Optional[str] = None
    query_tags: List[str] = Field(default_factory=list)
    
    # Search
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
    response_generation_time_ms: float = Field(default=0.0, ge=0.0)
    
    # Cost (NEW!)
    cost_breakdown: CostBreakdown = Field(default_factory=CostBreakdown)
    
    # Escalation
    escalated: bool = False
    escalation_reason: str = "none"
```

---

### **Step 3: Move & Update Collector (30 min)**

Copy `query_metrics.py` → `/src/analytics/collectors/metrics_collector.py`

Update to use Pydantic models and add cost aggregation.

---

### **Step 4: Update Orchestrator (15 min)**

```python
# Old import
from src.admin.query_metrics import QueryMetricsCollector

# New import
from src.analytics.collectors.metrics_collector import QueryMetricsCollector
```

---

### **Step 5: Add LLM Timing (15 min)**

In orchestrator.py, add timing around response generation.

---

### **Step 6: Deprecate Old Files (5 min)**

Add deprecation warnings to old files, keep for backward compat.

---

## **TOTAL TIME ESTIMATE**

- **Option A (Minimal):** 1 hour
- **Option B (Analytics Module):** 2.5 hours  ⭐ **RECOMMENDED**
- **Option C (Full Separation):** 4 hours

---

## **MY RECOMMENDATION**

### **Go with Option B: Analytics Module**

**Why:**
- Clear, organized structure
- Not too complex
- Room to grow
- Professional

**Structure:**
```
/src/analytics/
    __init__.py
    models.py              ← Pydantic models (all in one file for now)
    collectors.py          ← Metrics collection
    trackers.py            ← Token tracking
```

**Can expand later** to Option C if needed.

---

## **NEXT STEPS**

**Ready to implement?**

1. Create analytics module structure
2. Create Pydantic models with cost tracking
3. Update orchestrator with LLM timing
4. Migrate collectors
5. Test with frontend

**Or want to discuss more first?**
