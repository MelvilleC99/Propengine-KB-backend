# 📋 ADDING DEBUG METRICS TO OTHER AGENTS

**If you want debug metrics in Support or Customer agents:**

---

## **OPTION 1: Add to Specific Agents (Manual)**

### **Support Agent Example:**

```python
# File: /src/api/support_agent_routes.py

class SupportAgentResponse(BaseModel):
    response: str
    session_id: str
    confidence: float
    sources: List[Dict]
    # ... other fields
    
    # ADD THIS:
    debug_metrics: Optional[Dict] = Field(
        None,
        description="Debug metrics (only if enabled)"
    )
```

Then in the endpoint:
```python
@router.post("/")
async def support_agent(
    request: SupportAgentRequest,
    include_debug: bool = False  # ← Optional parameter
):
    result = await agent.process_query(...)
    
    return SupportAgentResponse(
        response=result["response"],
        # ... other fields
        debug_metrics=result.get("debug_metrics") if include_debug else None
    )
```

---

## **OPTION 2: Shared Base Model (Better!)**

Create a base response model that all agents inherit from:

```python
# File: /src/api/base_models.py (NEW FILE)

from pydantic import BaseModel, Field
from typing import Optional, List, Dict

class BaseAgentResponse(BaseModel):
    """Base response model with common fields"""
    response: str
    session_id: str
    confidence: float
    sources: List[Dict]
    query_type: Optional[str] = None
    timestamp: str
    requires_escalation: bool = False
    
    # Optional debug (only populated if requested)
    debug_metrics: Optional[Dict] = Field(
        None,
        description="Query execution metrics (debug only)"
    )

class TestAgentResponse(BaseAgentResponse):
    """Test agent - always includes debug"""
    # Inherits all fields
    # Override to make debug_metrics required
    debug_metrics: Dict  # ← Always populated for test agent

class SupportAgentResponse(BaseAgentResponse):
    """Support agent - debug optional"""
    # Inherits all fields
    # debug_metrics stays optional

class CustomerAgentResponse(BaseAgentResponse):
    """Customer agent - never includes debug"""
    # Inherits all fields
    # Can exclude debug_metrics entirely
    debug_metrics: None = Field(None, exclude=True)
```

---

## **OPTION 3: Query Parameter (Most Flexible!)**

Add an optional query parameter to ALL endpoints:

```python
@router.post("/api/agent/support/")
async def support_agent(
    request: SupportAgentRequest,
    debug: bool = False  # ← Add to URL: ?debug=true
):
    result = await agent.process_query(...)
    
    return SupportAgentResponse(
        response=result["response"],
        # ...
        debug_metrics=result.get("debug_metrics") if debug else None
    )
```

**Usage:**
```bash
# Normal use
POST /api/agent/support/

# Debug mode
POST /api/agent/support/?debug=true
```

---

## **RECOMMENDATION:**

**Use Option 3 (Query Parameter)**

**Why:**
- ✅ Simple to implement
- ✅ Works for all agents
- ✅ No breaking changes
- ✅ Easy to enable/disable
- ✅ Production-safe (defaults to off)

**Implementation:**
1. Add `debug: bool = False` parameter to each endpoint
2. Pass debug_metrics only if `debug=True`
3. Frontend can enable debug mode per-agent

---

**For now, Test Agent always has debug (perfect for you!)**
