# Memory Module - Session Management System

## 📁 Directory Structure

```
src/memory/
├── session_manager.py          # 428 lines - Main orchestrator
├── redis_message_store.py      # 387 lines - Redis caching operations
├── session_analytics.py        # 245 lines - Analytics buffering & batch writing
├── session_fallback.py         # 239 lines - In-memory fallback storage
├── kb_analytics.py             # 276 lines - KB entry usage tracking (PARKED)
└── README.md                   # This file
```

---

## 📝 File Descriptions

### **session_manager.py** - The Orchestrator (428 lines)

**Purpose:** Coordinates all session management components and data flow.

**What it does:**
- Creates and manages session lifecycle (create/end)
- Routes messages to appropriate storage layers (Redis → Firebase → Fallback)
- Manages rolling summaries (generates every 5 messages)
- Formats context for LLM consumption
- Coordinates batch analytics writing on session end
- Handles cleanup of all session data

**Key Methods:**
```python
create_session(user_info)                              # Create new session
get_session(session_id)                                # Get session info
add_message(session_id, role, content, metadata)       # Add message + buffer analytics
get_history(session_id, limit)                         # Get conversation history
get_context_for_llm(session_id)                        # Get formatted context with summaries
end_session_with_analytics(session_id, agent_id)       # End session + batch write
```

**Dependencies:**
- `RedisContextCache` (from redis_message_store.py)
- `SessionAnalytics` (from session_analytics.py)
- `SessionFallback` (from session_fallback.py)
- `FirebaseSessionManager` (external service)
- `chat_summarizer` (external utility)

---

### **redis_message_store.py** - Redis Operations (387 lines)

**Purpose:** Fast Redis-based message caching with in-memory fallback.

**What it does:**
- Stores last 8 messages per session in Redis
- Caches rolling summaries in Redis
- Provides in-memory fallback if Redis is unavailable
- Formats conversation context for LLM
- Monitors Redis health status
- Auto-expires sessions after 2 hours

**Key Methods:**
```python
add_message(session_id, role, content, metadata)       # Store message in Redis
get_messages(session_id, limit)                        # Retrieve recent messages
get_context(session_id, max_messages)                  # Get formatted string
store_rolling_summary(session_id, summary_data)        # Store summary
get_rolling_summary(session_id)                        # Retrieve summary
get_context_with_summary(session_id, max_messages)     # Get messages + summary
clear_session(session_id)                              # Clear cache
health_check()                                         # Redis health status
```

**Storage:**
- Redis key: `context:{session_id}` (message list)
- Redis key: `session:{session_id}:summary` (rolling summary)
- Fallback: In-memory dictionary

---

### **session_analytics.py** - Analytics Management (245 lines)

**Purpose:** Buffers query metadata during session and batch writes to Firebase on session end.

**What it does:**
- Buffers query metadata in memory (NO Firebase writes during conversation)
- Stores user information for each session
- Batch writes all analytics when session ends
- Updates user activity statistics in Firebase
- Adds sessions to user history
- Lazy loads Firebase services

**Key Methods:**
```python
store_user_info(session_id, user_info)                 # Store user data
buffer_query_metadata(session_id, query, response, metadata)  # Buffer query
get_buffered_queries(session_id)                       # Get all buffered queries
write_session_analytics(session_id, agent_id)          # Batch write to Firebase
add_session_to_user_history(session_id, agent_id)      # Add to user's recent sessions
clear_session_data(session_id)                         # Clear all buffers
```

**Storage:**
- In-memory: `query_buffers` (session_id → List of query data)
- In-memory: `session_users` (session_id → user info)
- Writes to: Firebase Analytics + Firebase Users (only on session end)

---

### **session_fallback.py** - In-Memory Fallback (239 lines)

**Purpose:** Provides in-memory storage when Redis/Firebase are unavailable.

**What it does:**
- Creates and manages in-memory sessions
- Stores messages when primary storage fails
- Handles session expiration (30-minute timeout)
- Provides fallback message history
- Keeps last 20 messages per session
- Clears expired sessions automatically

**Key Methods:**
```python
create_session(user_info)                              # Create fallback session
get_session(session_id)                                # Get session (with expiration check)
add_message(session_id, role, content)                 # Add message to memory
get_history(session_id, limit)                         # Get message history
get_context(session_id, max_messages)                  # Get formatted context
update_metadata(session_id, key, value)                # Update metadata
clear_expired_sessions()                               # Remove expired sessions
```

**Storage:**
- In-memory: `memory_sessions` (session_id → session dict)
- Session timeout: 30 minutes
- Max history: 20 messages per session

---

### **kb_analytics.py** - KB Entry Tracking (276 lines) [PARKED]

**Purpose:** Tracks which knowledge base entries are used most frequently.

**Status:** ⏸️ **PARKED** - Will be revisited when building admin dashboard.

**What it does:**
- Tracks usage counts for each KB entry
- Updates usage statistics in Firebase
- Retrieves most popular entries
- Monitors which KB sources are most helpful

**Note:** This module serves a different purpose than `session_analytics.py`:
- `session_analytics` → Tracks user queries and conversation metrics
- `kb_analytics` → Tracks KB entry popularity and usage patterns

This will be integrated or refactored when building the admin dashboard to determine exactly what analytics are needed for reporting.

---

## 🔄 Data Flow

### **Normal Operation Flow:**

```
1. USER CREATES SESSION
   → session_manager.create_session()
   → FirebaseSessionManager.create_session()
   → Returns session_id

2. USER SENDS MESSAGE
   → session_manager.add_message()
   ├→ redis_message_store.add_message()           [Fast cache]
   ├→ session_analytics.buffer_query_metadata()   [If assistant response]
   └→ Check if rolling summary needed (every 5 messages)

3. GET CONTEXT FOR LLM
   → session_manager.get_context_for_llm()
   → redis_message_store.get_context_with_summary()
   → Returns {messages, summary, formatted_context}

4. END SESSION
   → session_manager.end_session_with_analytics()
   ├→ Generate final summary
   ├→ FirebaseSessionManager.end_session_with_summary()
   ├→ session_analytics.write_session_analytics()  [Batch write all queries]
   ├→ session_analytics.add_session_to_user_history()
   └→ Clear all caches and buffers
```

### **Fallback Mode (if Redis/Firebase fail):**

```
1. CREATE SESSION
   → session_manager.create_session()
   → [Firebase fails]
   → session_fallback.create_session()           [In-memory]

2. ADD MESSAGE
   → session_manager.add_message()
   → [Redis fails]
   → session_fallback.add_message()              [In-memory]

3. GET HISTORY
   → session_manager.get_history()
   → [Redis fails]
   → [Firebase fails]
   → session_fallback.get_history()              [In-memory]
```

---

## ⚙️ Configuration

### Redis Message Store
```python
max_messages_per_session = 8     # Messages cached in Redis
session_ttl = 7200                # 2 hours (in seconds)
```

### Session Manager
```python
summary_interval = 5              # Generate rolling summary every 5 messages
```

### Session Fallback
```python
max_history_length = 20           # Max messages stored in memory
session_timeout = 30              # Minutes before session expires
```

---

## 🚀 Usage Example

```python
from src.memory.session_manager import SessionManager

# Initialize
session_mgr = SessionManager()

# Create session
session_id = session_mgr.create_session(user_info={
    "user_id": "BID-123",
    "platform": "web"
})

# Add messages
await session_mgr.add_message(
    session_id=session_id,
    role="user",
    content="What is your return policy?"
)

await session_mgr.add_message(
    session_id=session_id,
    role="assistant",
    content="Our return policy allows...",
    metadata={
        "confidence": 0.95,
        "sources": ["kb_entry_123"],
        "collection": "policies"
    }
)

# Get context for LLM
context = session_mgr.get_context_for_llm(session_id)
print(context["formatted_context"])

# End session with analytics
await session_mgr.end_session_with_analytics(
    session_id=session_id,
    agent_id="BID-123",
    reason="completed"
)
```

---

## 🎨 Design Principles

### 1. **Separation of Concerns**
Each file has ONE clear responsibility:
- `session_manager` → Orchestration
- `redis_message_store` → Redis operations
- `session_analytics` → Analytics buffering/writing
- `session_fallback` → In-memory backup

### 2. **Graceful Degradation**
System continues working even if components fail:
- Redis fails → Use in-memory fallback
- Firebase fails → Store locally
- Both fail → Full in-memory mode

### 3. **Lazy Loading**
Firebase services only loaded when first needed:
- Reduces startup time
- Allows partial functionality if Firebase unavailable

### 4. **Batch Operations**
Analytics written in ONE batch at session end:
- No Firebase writes during conversation
- Reduces database operations
- Improves performance

### 5. **Clear Data Flow**
Data flows through orchestrator:
- Components don't call each other directly
- `session_manager` coordinates everything
- Easy to trace operations

---

## 📊 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    SESSION MANAGER                          │
│                    (Orchestrator)                           │
│                                                             │
│  • Creates sessions                                         │
│  • Routes messages                                          │
│  • Generates rolling summaries                              │
│  • Coordinates session ending                               │
└──────────────┬──────────────┬──────────────┬───────────────┘
               │              │              │
       ┌───────▼───────┐  ┌──▼───────────┐ ┌▼──────────────┐
       │ REDIS MESSAGE │  │   SESSION    │ │   SESSION     │
       │     STORE     │  │  ANALYTICS   │ │   FALLBACK    │
       │               │  │              │ │               │
       │ • Fast cache  │  │ • Buffer     │ │ • In-memory   │
       │ • Summaries   │  │ • Batch write│ │ • Backup      │
       │ • TTL: 2hrs   │  │ • User stats │ │ • 30min TTL   │
       └───────┬───────┘  └──┬───────────┘ └───────────────┘
               │              │
       ┌───────▼──────┐  ┌───▼────────────┐
       │    REDIS     │  │    FIREBASE    │
       │   (Cloud)    │  │   (Sessions +  │
       │              │  │   Analytics +  │
       │              │  │   Users)       │
       └──────────────┘  └────────────────┘
```

---

## ✅ Key Features

- ✨ **Fast caching** with Redis (8 messages per session)
- ✨ **Rolling summaries** every 5 messages for context efficiency
- ✨ **Batch analytics** writing (no writes during conversation)
- ✨ **Graceful fallback** to in-memory storage
- ✨ **Automatic cleanup** of expired sessions and caches
- ✨ **Lazy loading** of Firebase services
- ✨ **Clear separation** of concerns across modules

---

## 📝 Notes

- **No breaking changes** - All public APIs remain the same
- **Battle-tested** - Refactored from working production code
- **Well-documented** - Comprehensive inline documentation
- **Testable** - Clear module boundaries for unit testing
