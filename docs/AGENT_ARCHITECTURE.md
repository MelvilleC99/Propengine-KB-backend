# Agent Architecture - Component Mapping & Refactoring Strategy

## 📊 Current System Analysis

### Existing Agent Components (What You Already Have)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CURRENT AGENT FLOW                            │
└─────────────────────────────────────────────────────────────────┘

1. Query Understanding & Classification
   ├─ QueryClassifier (orchestrator.py)
   │  ├─ Pattern matching (regex)
   │  ├─ Returns: query_type, confidence
   │  └─ Types: greeting, error, definition, howto, workflow
   │
2. Context Checking
   ├─ Session Manager (memory/session_manager.py)
   │  ├─ Conversation history (Redis)
   │  ├─ Try context-first strategy
   │  └─ Fallback to vector search
   │
3. Vector Search with Fallback
   ├─ VectorSearch (query/vector_search.py)
   │  ├─ Primary search with entry_type filter
   │  ├─ Fallback 1: Remove entry_type filter
   │  ├─ Fallback 2: Try error type if howto fails
   │  └─ Embedding caching (performance)
   │
4. Re-ranking
   ├─ SearchReranker (query/reranker.py)
   │  └─ Improves result relevance
   │
5. Response Generation
   ├─ LLM (ChatOpenAI)
   │  ├─ System prompt + context
   │  ├─ Conversation-aware
   │  └─ Fallback response if no results
   │
6. Escalation Detection
   ├─ Confidence threshold (0.7)
   │  ├─ requires_escalation flag
   │  └─ Triggers ticket creation flow
   │
7. Analytics & Tracking
   ├─ KB Analytics (memory/kb_analytics.py)
   ├─ Session tracking
   └─ Failure logging (/api/agent-failure)
```

---

## 🎯 Three Agent Types - Requirements

### **1. Test Agent (Debug/Diagnostics)**
**Purpose**: Internal testing and debugging

**Features Needed**:
- ✅ Shows confidence scores (similarity + classification)
- ✅ Displays all sources with full metadata
- ✅ Shows query classification details
- ✅ Displays search attempts and fallbacks
- ✅ Timing metrics (optional)
- ✅ Full metadata visibility
- ✅ No metadata filtering (sees ALL entries)

**UI**: Floating modal/popup (existing test-agent-chat.tsx)

---

### **2. Support Staff Agent**
**Purpose**: Internal support staff use

**Features Needed**:
- ✅ Clean KB source references (not overwhelming)
- ✅ Metadata filter: `userType: "internal"` ONLY
- ✅ Agent ID tracking
- ✅ Thumbs up/down feedback
- ✅ Freshdesk ticket creation
- ✅ Escalation detection
- ❌ No debug info (clean interface)

**UI**: Full page at `/kb/support-agent`

---

### **3. Customer Agent (External)**
**Purpose**: Customer-facing widget

**Features Needed**:
- ✅ Metadata filter: `userType: "external"` ONLY
- ✅ Rate limiting (50/hour via Redis)
- ✅ Session management (Redis)
- ✅ Thumbs up/down feedback
- ✅ Freshdesk ticket creation
- ✅ Escalation detection
- ❌ NO source references shown
- ❌ NO debug info
- ❌ NO confidence scores

**UI**: Embeddable widget (for customer sites)

---

## 🏗️ Proposed Refactored Architecture

### Backend Structure

```
/src/agent/
├── core.py                 → NEW - BaseAgent (shared logic)
├── orchestrator.py         → KEEP - Main brain (current Agent class)
├── test_agent.py          → NEW - Test agent wrapper
├── support_agent.py       → NEW - Support agent wrapper  
└── customer_agent.py      → NEW - Customer agent wrapper

/src/api/
├── chat_routes.py         → KEEP - Generic endpoint (backward compat)
└── agent_routes.py        → NEW - Three separate endpoints
    ├── POST /api/agent/test
    ├── POST /api/agent/support
    └── POST /api/agent/customer
```

### Frontend Structure

```
/app/kb/
├── support-agent/         → NEW PAGE - Full page for staff
│   └── page.tsx

/components/agents/
├── shared/                → NEW - Reusable components
│   ├── chat-message.tsx
│   ├── chat-input.tsx
│   ├── typing-indicator.tsx
│   ├── feedback-buttons.tsx
│   └── escalation-prompt.tsx
│
├── test-agent/            → REFACTOR EXISTING
│   ├── test-agent-popup.tsx  (keep as modal)
│   └── debug-panel.tsx       (NEW - diagnostic display)
│
├── support-agent/         → NEW
│   ├── kb-sources-list.tsx   (clean source display)
│   └── agent-header.tsx      (agent info)
│
└── customer-agent/        → NEW (LATER - Phase 3)
    ├── chat-widget.tsx       (embeddable)
    └── widget-config.tsx     (customization)
```

---

## 📋 Component Breakdown & Responsibilities

### **Component 1: Query Understanding**

**Current**: `QueryClassifier` in `orchestrator.py`

**Refactor Strategy**: ✅ **KEEP AS-IS**
- Already works well
- Pattern-based classification
- Shared by all agents

**Agent-Specific Behavior**: None (same logic for all)

---

### **Component 2: Prompt Structuring**

**Current**: `generate_response()` in `orchestrator.py`

**Location**: `/src/prompts/system_prompts.py`

**Refactor Strategy**: ✅ **KEEP AS-IS** with agent-specific system prompts

**Agent-Specific Behavior**:
```python
# In system_prompts.py

TEST_AGENT_SYSTEM_PROMPT = """
You are a test/debug agent. Provide detailed technical responses.
Include ALL technical details and metadata in your responses.
"""

SUPPORT_AGENT_SYSTEM_PROMPT = """
You are a support agent for PropertyEngine internal staff.
Provide clear, professional responses with source references.
Be concise but thorough.
"""

CUSTOMER_AGENT_SYSTEM_PROMPT = """
You are a helpful PropertyEngine assistant.
Provide friendly, easy-to-understand responses.
Do not mention technical details or sources.
If you cannot help, offer to escalate politely.
"""
```

---

### **Component 3: Vector Search & Ranking**

**Current**: `VectorSearch` + `SearchReranker`

**Refactor Strategy**: ✅ **KEEP AS-IS** with metadata filtering

**Agent-Specific Behavior**:

| Agent | Metadata Filter | Behavior |
|-------|----------------|----------|
| **Test** | `None` | Sees ALL entries (internal + external) |
| **Support** | `{"userType": "internal"}` | Internal entries only |
| **Customer** | `{"userType": "external"}` | External entries only |

**Implementation**:
```python
# In agent wrappers
class SupportAgent(BaseAgent):
    async def process_query(self, query, session_id):
        return await self.orchestrator.process_query(
            query=query,
            session_id=session_id,
            user_type_filter="internal"  # ← Filter here
        )
```

---

### **Component 4: Response Formatting**

**Current**: Raw response from LLM

**Refactor Strategy**: ✅ **ADD POST-PROCESSING** in agent wrappers

**Agent-Specific Behavior**:

**Test Agent**:
```python
response = {
    "response": llm_response,
    "confidence": similarity_score,
    "classification_confidence": pattern_confidence,
    "sources": sources_with_full_metadata,  # ← Full details
    "debug": {
        "query_type": query_type,
        "search_attempts": search_attempts,
        "timing": {...}
    }
}
```

**Support Agent**:
```python
response = {
    "response": llm_response,
    "confidence": similarity_score,
    "sources": [  # ← Clean format
        {
            "title": "...",
            "section": "...",
            "category": "...",
            "confidence": 0.92
        }
    ],
    "requires_escalation": similarity_score < 0.7
}
```

**Customer Agent**:
```python
response = {
    "response": llm_response,
    "requires_escalation": similarity_score < 0.7,
    # ← NO sources, NO confidence, NO debug info
}
```

---

### **Component 5: Context & Memory**

**Current**: `SessionManager` with Redis

**Refactor Strategy**: ✅ **KEEP AS-IS**

**Agent-Specific Behavior**:

| Agent | Session Storage | TTL |
|-------|----------------|-----|
| **Test** | In-memory only | Session-based |
| **Support** | Redis | 30 minutes |
| **Customer** | Redis | 30 minutes |

**Rate Limiting** (Customer only):
```python
# In customer_agent.py
async def process_query(self, query, session_id):
    if not await self.check_rate_limit(session_id):
        return {"error": "Rate limit exceeded (50/hour)"}
    
    # Continue...
```

---

### **Component 6: Feedback (Thumbs Up/Down)**

**Current**: Frontend only (`useChat.ts`)

**Refactor Strategy**: ✅ **ADD BACKEND TRACKING**

**Agent-Specific Behavior**:

**All agents** get feedback, but stored differently:

```python
# NEW: /src/api/feedback_routes.py

@router.post("/feedback")
async def log_feedback(
    message_id: str,
    feedback: str,  # "positive" or "negative"
    session_id: str,
    agent_type: str,  # "test", "support", "customer"
    comment: Optional[str] = None
):
    # Store in Firebase/analytics
    ...
```

---

### **Component 7: Escalation & Freshdesk**

**Current**: Frontend calls `/api/freshdesk`

**Refactor Strategy**: ✅ **KEEP AS-IS** with agent-specific triggers

**Agent-Specific Behavior**:

| Agent | Escalation Threshold | Creates Ticket? |
|-------|---------------------|-----------------|
| **Test** | N/A (diagnostic only) | ❌ No |
| **Support** | `confidence < 0.7` | ✅ Yes |
| **Customer** | `confidence < 0.7` | ✅ Yes |

**Ticket Priority**:
```python
# Customer escalations: Higher priority
if agent_type == "customer":
    priority = 3  # High
else:  # support
    priority = 2  # Medium
```

---

## 🔄 Refactoring Strategy - Step by Step

### **Phase 1: Backend Foundation** (Core architecture)

**Goal**: Create agent wrappers without breaking existing system

**Tasks**:
1. Create `/src/agent/core.py` - BaseAgent class
2. Create `/src/agent/test_agent.py` - Simplest wrapper (no filtering)
3. Create `/src/api/agent_routes.py` - New endpoints
4. Test `/api/agent/test` with existing frontend

**Estimated Time**: 2-3 hours

**Files to Create**:
```python
# /src/agent/core.py
class BaseAgent:
    def __init__(self):
        self.orchestrator = Agent()  # Reuse existing
    
    async def process_query(self, query, **kwargs):
        # Subclasses override
        raise NotImplementedError()
```

```python
# /src/agent/test_agent.py
class TestAgent(BaseAgent):
    async def process_query(self, query, session_id):
        # No filtering - see everything
        result = await self.orchestrator.process_query(
            query=query,
            session_id=session_id,
            user_type_filter=None  # ← See all
        )
        
        # Add debug info
        result['debug'] = {
            'confidence': result.get('confidence'),
            'classification_confidence': result.get('classification_confidence'),
            'search_attempts': result.get('search_attempts'),
            'query_type': result.get('query_type')
        }
        
        return result
```

```python
# /src/api/agent_routes.py
from src.agent.test_agent import TestAgent

router = APIRouter(prefix="/api/agent")
test_agent = TestAgent()

@router.post("/test")
async def test_agent_endpoint(request: ChatRequest):
    result = await test_agent.process_query(
        query=request.message,
        session_id=request.session_id
    )
    return ChatResponse(**result)
```

---

### **Phase 2: Support Staff Agent** (Most business value)

**Goal**: Create support-specific agent with clean UI

**Tasks**:
1. Create `/src/agent/support_agent.py` - Internal filtering
2. Add `/api/agent/support` endpoint
3. Build `/app/kb/support-agent/page.tsx` - Full page UI
4. Extract shared chat components
5. Create KB sources display component

**Estimated Time**: 4-5 hours

**Files to Create**:
```python
# /src/agent/support_agent.py
class SupportAgent(BaseAgent):
    async def process_query(self, query, session_id, agent_id):
        result = await self.orchestrator.process_query(
            query=query,
            session_id=session_id,
            user_type_filter="internal"  # ← Internal only
        )
        
        # Clean up sources for support staff
        if 'sources' in result:
            result['sources'] = self._format_sources_for_support(
                result['sources']
            )
        
        # Add agent tracking
        result['agent_id'] = agent_id
        
        # Remove debug info
        result.pop('search_attempts', None)
        result.pop('classification_confidence', None)
        
        return result
    
    def _format_sources_for_support(self, sources):
        """Format sources cleanly for support staff"""
        return [{
            'title': s['metadata']['title'],
            'section': s['entry_type'],
            'confidence': s['similarity_score'],
            'category': s['metadata'].get('category'),
            'preview': s['content'][:200]
        } for s in sources]
```

---

### **Phase 3: Customer Agent** (External-facing)

**Goal**: Create customer widget with rate limiting

**Tasks**:
1. Create `/src/agent/customer_agent.py` - External filtering + Redis
2. Add `/api/agent/customer` endpoint
3. Build embeddable widget component
4. Add rate limiting (50/hour)
5. Implement session management

**Estimated Time**: 5-6 hours

**Files to Create**:
```python
# /src/agent/customer_agent.py
class CustomerAgent(BaseAgent):
    async def process_query(self, query, session_id, redis_context):
        # Check rate limit
        if not await self.check_rate_limit(session_id):
            return {
                "response": "You've reached the maximum number of questions per hour. Please try again later.",
                "error": "rate_limit_exceeded"
            }
        
        # Add context from Redis
        enhanced_query = self.add_context(query, redis_context)
        
        result = await self.orchestrator.process_query(
            query=enhanced_query,
            session_id=session_id,
            user_type_filter="external"  # ← External only
        )
        
        # Remove ALL technical info
        customer_response = {
            "response": result['response'],
            "requires_escalation": result.get('requires_escalation', False)
        }
        
        # Track session
        await self.update_redis_context(session_id, query, customer_response)
        
        return customer_response
    
    async def check_rate_limit(self, session_id):
        """Check if user exceeded 50 queries/hour"""
        # Redis-based rate limiting
        ...
```

---

## 📊 Comparison Matrix

| Feature | Test Agent | Support Agent | Customer Agent |
|---------|-----------|---------------|----------------|
| **Access** | ALL entries | Internal ONLY | External ONLY |
| **UI** | Modal popup | Full page | Widget |
| **Confidence** | ✅ Shown | ✅ Shown | ❌ Hidden |
| **Sources** | ✅ Full metadata | ✅ Clean format | ❌ Hidden |
| **Debug Info** | ✅ All details | ❌ Hidden | ❌ Hidden |
| **Classification** | ✅ Shown | ❌ Hidden | ❌ Hidden |
| **Search Attempts** | ✅ Shown | ❌ Hidden | ❌ Hidden |
| **Feedback** | ❌ No | ✅ Yes | ✅ Yes |
| **Escalation** | ❌ No | ✅ Yes | ✅ Yes |
| **Rate Limiting** | ❌ No | ❌ No | ✅ Yes (50/hr) |
| **Session** | In-memory | Redis | Redis |
| **Freshdesk** | ❌ No | ✅ Yes | ✅ Yes |

---

## 🎨 UI Component Mapping

### Shared Components (All Agents)

```typescript
/components/agents/shared/
├── chat-message.tsx         → Message bubble
├── chat-input.tsx           → Input field + send button
├── typing-indicator.tsx     → "Agent is typing..."
├── feedback-buttons.tsx     → Thumbs up/down
└── escalation-prompt.tsx    → "Create ticket?" prompt
```

### Agent-Specific Components

**Test Agent**:
```typescript
/components/agents/test-agent/
├── test-agent-popup.tsx     → Modal container (EXISTING)
└── debug-panel.tsx          → NEW - Shows:
    ├── Confidence scores
    ├── Query classification
    ├── Search attempts
    ├── Full metadata
    └── Timing info
```

**Support Agent**:
```typescript
/components/agents/support-agent/
├── kb-sources-list.tsx      → Clean source display
│   ├── Title + section
│   ├── Category
│   ├── Confidence bar
│   └── Content preview
│
└── agent-header.tsx         → Shows:
    ├── Agent name/ID
    └── Session info
```

**Customer Agent**:
```typescript
/components/agents/customer-agent/
├── chat-widget.tsx          → Embeddable widget
│   ├── Floating button
│   ├── Chat window
│   └── Minimizable
│
└── widget-config.tsx        → Customization
    ├── Theme colors
    ├── Position
    └── Initial message
```

---

## 🔑 Key Principles

### 1. **Don't Repeat Yourself (DRY)**
- Orchestrator contains ALL core logic
- Agent wrappers are THIN (< 100 lines each)
- Shared components used across agents

### 2. **Single Responsibility**
- Each agent = ONE user type
- Each component = ONE UI concern
- Clear separation of concerns

### 3. **Backwards Compatibility**
- Keep `/api/chat` endpoint (existing system)
- New agents use `/api/agent/*` endpoints
- Gradual migration path

### 4. **Fail-Safe Design**
- All agents inherit orchestrator's fail-safes
- Circuit breakers
- Graceful degradation

### 5. **Performance**
- Embedding caching (already implemented)
- Connection pooling (already implemented)
- Rate limiting (customer only)

---

## 📝 Implementation Checklist

### Phase 1: Backend Foundation
- [ ] Create `/src/agent/core.py`
- [ ] Create `/src/agent/test_agent.py`
- [ ] Create `/src/api/agent_routes.py`
- [ ] Add `/api/agent/test` endpoint
- [ ] Test with existing frontend
- [ ] Update documentation

### Phase 2: Support Agent
- [ ] Create `/src/agent/support_agent.py`
- [ ] Add `/api/agent/support` endpoint
- [ ] Extract shared chat components
- [ ] Build `/app/kb/support-agent/page.tsx`
- [ ] Create `kb-sources-list.tsx`
- [ ] Add feedback tracking
- [ ] Test Freshdesk integration
- [ ] Update documentation

### Phase 3: Customer Agent
- [ ] Create `/src/agent/customer_agent.py`
- [ ] Add `/api/agent/customer` endpoint
- [ ] Implement Redis rate limiting
- [ ] Build embeddable widget
- [ ] Add session management
- [ ] Test rate limiting
- [ ] Create widget documentation
- [ ] Update documentation

---

## 🚀 Next Steps

**Recommend starting with Phase 1** because:
1. Smallest scope (2-3 hours)
2. Tests architecture without breaking anything
3. Validates agent wrapper pattern
4. Builds confidence before bigger changes

**Ready to start with Phase 1: Backend Foundation?**

We can:
1. Create `core.py` - BaseAgent wrapper
2. Create `test_agent.py` - Simplest implementation
3. Create `agent_routes.py` - New endpoints
4. Test with existing test agent frontend

This will prove the pattern works before we tackle the more complex support and customer agents.

---

**Last Updated**: January 21, 2026  
**Total Estimated Time**: 11-14 hours across 3 phases
