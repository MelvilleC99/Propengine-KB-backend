# Agent Refactoring - Quick Visual Guide

## 🎯 The Goal: One Brain, Three Interfaces

```
                    ┌─────────────────────────────┐
                    │   ORCHESTRATOR (Brain)      │
                    │   • Query classification    │
                    │   • Vector search           │
                    │   • Response generation     │
                    │   • Fail-safes              │
                    └──────────┬──────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                 │
              ▼                ▼                 ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  TEST AGENT     │ │ SUPPORT AGENT   │ │ CUSTOMER AGENT  │
    │  (Diagnostics)  │ │ (Internal)      │ │ (External)      │
    └─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 📊 What Each Agent Does

### Test Agent (Debug)
```
Input:  "what is an API key?"
          ↓
Filter: NONE (sees all entries)
          ↓
Output: {
  response: "An API key is...",
  confidence: 0.92,
  classification_confidence: 0.8,
  sources: [full metadata...],
  debug: {
    query_type: "definition",
    search_attempts: ["primary", "fallback"],
    timing: {...}
  }
}
```

### Support Agent (Internal Staff)
```
Input:  "what is an API key?"
          ↓
Filter: userType = "internal"
          ↓
Output: {
  response: "An API key is...",
  confidence: 0.92,
  sources: [
    {title, section, category, confidence}
  ],
  requires_escalation: false
}
```

### Customer Agent (External)
```
Input:  "what is an API key?"
          ↓
Filter: userType = "external"
          ↓
Rate Limit Check: ✅ OK (45/50)
          ↓
Output: {
  response: "An API key is...",
  requires_escalation: false
}
```

---

## 🏗️ Code Structure

### Backend (Python)

```
BEFORE (Current):
/src/agent/
└── orchestrator.py (all logic + routing)

AFTER (Refactored):
/src/agent/
├── orchestrator.py   (KEEP - brain)
├── core.py          (NEW - base class)
├── test_agent.py    (NEW - no filter)
├── support_agent.py (NEW - internal filter)
└── customer_agent.py (NEW - external filter + rate limit)
```

### Frontend (TypeScript)

```
BEFORE (Current):
/components/
└── chat/
    └── chat-widget.tsx (450 lines - does everything)

AFTER (Refactored):
/components/agents/
├── shared/              (NEW - reusable)
│   ├── chat-message.tsx
│   ├── chat-input.tsx
│   └── feedback-buttons.tsx
├── test-agent/
│   └── debug-panel.tsx  (NEW - diagnostics)
├── support-agent/
│   └── kb-sources-list.tsx (NEW - clean sources)
└── customer-agent/
    └── chat-widget.tsx (NEW - embeddable)
```

---

## 🔄 Implementation Phases

### Phase 1: Backend Foundation (2-3 hrs)
```bash
Create:
✓ /src/agent/core.py
✓ /src/agent/test_agent.py
✓ /src/api/agent_routes.py

Test:
✓ POST /api/agent/test works
✓ Returns debug info
✓ No filtering applied
```

### Phase 2: Support Agent (4-5 hrs)
```bash
Create:
✓ /src/agent/support_agent.py
✓ /app/kb/support-agent/page.tsx
✓ /components/agents/support-agent/*

Test:
✓ POST /api/agent/support works
✓ Only internal entries returned
✓ Clean source formatting
✓ Feedback working
✓ Freshdesk integration
```

### Phase 3: Customer Agent (5-6 hrs)
```bash
Create:
✓ /src/agent/customer_agent.py
✓ /components/agents/customer-agent/*
✓ Rate limiting (Redis)

Test:
✓ POST /api/agent/customer works
✓ Only external entries returned
✓ Rate limit enforced (50/hr)
✓ No sources shown
✓ Freshdesk integration
```

---

## 🎯 Key Differences at a Glance

| Feature | Test | Support | Customer |
|---------|------|---------|----------|
| **Sees** | All | Internal | External |
| **Shows Confidence** | ✅ | ✅ | ❌ |
| **Shows Sources** | ✅ Full | ✅ Clean | ❌ |
| **Shows Debug** | ✅ | ❌ | ❌ |
| **Feedback** | ❌ | ✅ | ✅ |
| **Tickets** | ❌ | ✅ | ✅ |
| **Rate Limit** | ❌ | ❌ | ✅ |

---

## 💡 Best Practices Applied

### 1. DRY (Don't Repeat Yourself)
```python
# ❌ BAD: Duplicate logic
class TestAgent:
    def classify_query(self, query):
        # 50 lines of classification...

class SupportAgent:
    def classify_query(self, query):
        # Same 50 lines duplicated...

# ✅ GOOD: Shared logic
class TestAgent(BaseAgent):
    async def process_query(self, query):
        return await self.orchestrator.process_query(query)
        # Orchestrator has classification
```

### 2. Single Responsibility
```python
# Each agent = ONE job
TestAgent     → Debug diagnostics
SupportAgent  → Internal support
CustomerAgent → External help
```

### 3. Thin Wrappers
```python
# Agent wrappers are <100 lines
class SupportAgent(BaseAgent):
    async def process_query(self, query, session_id):
        # Just filter + format
        result = await self.orchestrator.process_query(
            query, session_id, user_type_filter="internal"
        )
        return self._format_for_support(result)
```

---

## 🚀 Start Here

**Recommended First Step**:

```bash
1. Read: AGENT_ARCHITECTURE.md (full details)
2. Start: Phase 1 - Backend Foundation
3. Create: core.py, test_agent.py, agent_routes.py
4. Test: With existing test agent frontend
5. Move: Phase 2 after Phase 1 works
```

**Time Investment**:
- Phase 1: 2-3 hours (foundation)
- Phase 2: 4-5 hours (support agent)
- Phase 3: 5-6 hours (customer agent)

**Total**: ~11-14 hours

---

## 📚 Related Docs

- **AGENT_ARCHITECTURE.md** - Full detailed guide
- **DB_Endpoints.md** - API reference
- **Chunking.md** - How data is structured
- **QUICK_REFERENCE.md** - Cheat sheet

---

**Print this diagram and keep it visible while coding!**
