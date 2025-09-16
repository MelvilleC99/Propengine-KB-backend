# Session Management Layer

This folder manages user sessions, conversation state, and memory persistence for the PropertyEngine Knowledge Base backend.

## Files Overview

### `session_manager.py`
**Purpose**: Core session management with Firebase persistence and in-memory fallback
- Provides unified interface for session operations
- Integrates Firebase backend with fallback mechanisms
- Manages conversation history and user context
- Handles session lifecycle and cleanup

**Key Features**:
- **Firebase-First Architecture**: Stores sessions in Firestore for persistence
- **Graceful Fallback**: Falls back to in-memory storage if Firebase fails
- **Session Timeout**: Automatic cleanup of expired sessions (2 hours)
- **Performance Optimized**: Individual message logging disabled for faster response times
- **Chat Summaries**: (Planned) Will replace individual message logging for efficiency
- **User Context**: Stores user information for personalized responses

**Core Methods**:

#### Session Lifecycle
```python
create_session(user_info: Dict) -> str
    # Creates new session in Firebase with user metadata
    # Returns: unique session_id

get_session(session_id: str) -> Optional[Dict]
    # Retrieves session with automatic expiration check
    # Updates last_activity timestamp

add_message(session_id: str, role: str, content: str, metadata: Dict) -> bool
    # Logs message to Firebase with metadata
    # Roles: "user" or "assistant"

get_history(session_id: str, limit: int) -> List[Dict]
    # Retrieves recent conversation messages
    # Used for agent context
```

#### Monitoring & Analytics
```python
get_active_sessions() -> List[Dict]
    # Returns count of active Firebase + memory sessions

clear_expired_sessions() -> int
    # Cleanup utility for memory sessions
    # Firebase handles its own cleanup
```

### Session Data Structure

#### Firebase Session
```python
{
    "session_id": "uuid-4-string",
    "user_email": "melville.duplessis@betterhome.co.za",
    "user_name": "Melville du Plessis",
    "company": "Betterhome", 
    "division": "Property Management",
    "user_type": "agent",
    
    # Timestamps
    "created_at": firestore.SERVER_TIMESTAMP,
    "last_activity": firestore.SERVER_TIMESTAMP,
    
    # Conversation tracking
    "message_count": 15,
    "total_queries": 8,
    "conversation_summary": "User asking about property definitions",
    "status": "active",
    
    # Analytics
    "escalations": 0,
    "avg_confidence": 0.85,
    "feedback_positive": 3,
    "feedback_negative": 0
}
```

#### Memory Session (Fallback)
```python
{
    "id": "session-uuid",
    "created_at": datetime.now(),
    "last_activity": datetime.now(),
    "messages": [
        {
            "role": "user",
            "content": "What does erf size mean?",
            "timestamp": "2024-01-15T10:30:00"
        }
    ],
    "user_info": {
        "email": "user@company.com",
        "name": "User Name"
    },
    "metadata": {
        "total_queries": 5,
        "collections_used": ["property_docs"],
        "escalated": False,
        "fallback": True
    }
}
```

## Integration Points

### With Firebase Layer
```python
from src.database.firebase_session import FirebaseSessionManager

# SessionManager wraps FirebaseSessionManager
firebase_sessions = FirebaseSessionManager()
```

### With Chat API
```python
from src.memory.session_manager import SessionManager

# Used in chat routes for persistent conversations
session_manager = SessionManager()
session_id = session_manager.create_session(user_info)
```

### With Agent System
```python
# Provides conversation context to agent
history = session_manager.get_history(session_id, limit=5)
# Agent uses history for context-aware responses
```

## Session Lifecycle

```
1. User Login → Create Session (Firebase)
                      ↓
2. Chat Message → Add Message (Firebase + Memory fallback)
                      ↓  
3. Agent Response → Add Response (Firebase + Memory fallback)
                      ↓
4. Conversation Context → Get History (Recent messages)
                      ↓
5. Session Timeout (2 hours) → Expire Session
```

## Configuration

### Session Settings
```python
session_timeout = timedelta(hours=2)        # Session expires after 2 hours
max_history_length = 20                     # Keep last 20 messages in memory
max_messages_per_session = 50               # Firebase limit per session
```

### Firebase Collections
- `kb_sessions` - Session metadata and user info
- `kb_messages` - Individual messages with context

## Error Handling & Fallbacks

### Firebase Unavailable
```python
# Automatic fallback to in-memory storage
try:
    firebase_sessions.create_session(user_info)
except Exception:
    # Falls back to memory_sessions dictionary
    _create_memory_session(user_info)
```

### Session Recovery
```python
# Handles expired/missing sessions gracefully
session = get_session(session_id)
if not session:
    # Creates new session transparently
    session_id = create_session(user_info)
```

## Performance Considerations

### Firebase Optimization
- Uses Firestore batch operations where possible
- Implements connection pooling via firebase_config
- Maintains local cache for active sessions

### Memory Management
- Automatically cleans up expired in-memory sessions
- Limits message history to prevent memory bloat
- Implements efficient deque structures for message storage

## Monitoring & Debugging

### Session Metrics
```python
active_sessions = session_manager.get_active_sessions()
# Returns: {"firebase_sessions": 45, "memory_sessions": 3, "total": 48}
```

### Logging
- Session creation/expiration events
- Firebase connection issues
- Fallback activations
- Performance metrics

## Future Enhancements

### Conversation Intelligence
- Automatic conversation summarization
- Topic extraction and tagging  
- User intent classification
- Escalation prediction

### Advanced Persistence
- Redis integration for high-performance caching
- Database connection pooling
- Cross-session user analytics
- Conversation export capabilities
