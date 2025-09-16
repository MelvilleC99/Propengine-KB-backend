# API Layer

This folder contains all REST API endpoints and route handlers for the PropertyEngine Knowledge Base backend.

## Files Overview

### `chat_routes.py`
**Purpose**: Main chat endpoint for user interactions with the knowledge base agent
- Handles user queries and agent responses
- Manages session creation and persistence
- Implements rate limiting and user authentication
- Logs all messages to Firebase for analytics

**Endpoints**:

#### `POST /chat/`
Main chat interaction endpoint

**Request Model**:
```python
class ChatRequest(BaseModel):
    message: str                    # User's question/query
    session_id: Optional[str]       # Existing session (optional)
    user_info: Optional[Dict] = {   # User context
        "email": "user@company.com",
        "name": "User Name", 
        "company": "Company",
        "division": "Department",
        "user_type": "agent"
    }
```

**Response Model**:
```python
class ChatResponse(BaseModel):
    response: str                   # Agent's answer
    session_id: str                # Session identifier
    confidence: float              # Response confidence (0.0-1.0)
    sources: List[Dict]            # Source documents used
    requires_escalation: bool      # Whether to escalate to human
    query_type: str               # Classification of query
    timestamp: str                # Response timestamp
```

**Features**:
- **Rate Limiting**: 30 requests per minute per user
- **Session Management**: Creates/retrieves persistent sessions
- **Message Logging**: All interactions stored in Firebase
- **Error Handling**: Comprehensive error responses
- **User Context**: Personalizes responses based on user info

### `feedback_routes.py` (Planned)
**Purpose**: Collect user feedback on agent responses
- Thumbs up/down ratings
- Detailed feedback comments
- Response improvement suggestions

### `ticket_routes.py` (Planned)
**Purpose**: Handle escalation to human support
- Create support tickets
- Track escalation reasons
- Integration with support systems

## Request/Response Flow

```
1. Client Request → Rate Limiting Check → Session Validation
                        ↓
2. Session Management → Create/Retrieve Session → Update Activity
                        ↓
3. Agent Processing → Vector Search → LLM Generation → Response
                        ↓
4. Message Logging → Firebase Storage → Analytics Update
                        ↓
5. Response → Client with Session Context
```

## Rate Limiting

### Configuration
```python
rate_limits = {
    "chat": {"requests": 30, "window": 60},      # 30 per minute
    "feedback": {"requests": 20, "window": 60},   # 20 per minute  
    "ticket": {"requests": 5, "window": 300},     # 5 per 5 minutes
    "default": {"requests": 100, "window": 60}    # 100 per minute
}
```

### Implementation
- Uses in-memory sliding window counter
- Tracks by user email (preferred) or IP address
- Returns 429 status code when exceeded
- Includes retry-after headers

### Rate Limit Headers
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1642685400
Retry-After: 45
```

## Error Handling

### Standard Error Response
```python
{
    "error": "Error type",
    "message": "Human readable message", 
    "details": {
        "session_id": "uuid",
        "timestamp": "2024-01-15T10:30:00Z",
        "request_id": "req_uuid"
    }
}
```

### Error Types
- `400 Bad Request` - Invalid input/malformed request
- `401 Unauthorized` - Missing or invalid authentication  
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server/database issues
- `503 Service Unavailable` - External service failures

## Authentication & Authorization

### User Context Validation
```python
user_info = {
    "email": "required - user identifier",
    "name": "optional - display name",
    "company": "optional - user's company", 
    "division": "optional - department",
    "user_type": "optional - role classification"
}
```

### Session Security
- Sessions tied to user email
- Automatic expiration after 2 hours
- Session validation on each request
- Cross-session data isolation

## Integration Points

### With Session Management
```python
from src.memory.session_manager import SessionManager

# Session lifecycle management
session_id = session_manager.create_session(user_info)
session = session_manager.get_session(session_id)
```

### With Agent System  
```python
from src.agent.orchestrator import Agent

# Query processing with context
result = await agent.process_query(
    query=message,
    session_id=session_id, 
    user_info=user_info
)
```

### With Database Layer
```python
# Firebase message logging
session_manager.add_message(
    session_id=session_id,
    role="user|assistant",
    content=content,
    metadata=metadata
)
```

## Performance Optimization

### Async Processing
- All route handlers use async/await
- Non-blocking database operations
- Concurrent processing where possible

### Response Caching
- Session data cached in memory
- Vector search results cached
- Rate limit state cached

### Connection Pooling
- Database connection reuse
- Firebase client persistence
- HTTP client pooling for external APIs

## Monitoring & Observability

### Request Logging
```python
logger.info(f"Chat request: {user_email} - {query_preview}")
logger.info(f"Response time: {duration}ms - Confidence: {confidence}")
```

### Metrics Tracked
- Request volume per endpoint
- Response times and latencies
- Error rates by type
- Rate limit hit rates
- Session creation/expiration rates

### Health Checks
```python
@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "firebase": firebase_config.is_available(),
            "astra_db": db_connection.is_connected(),
            "agent": agent.is_ready()
        }
    }
```

## Security Considerations

### Input Validation
- Request payload size limits
- Content sanitization
- SQL injection prevention
- XSS protection

### Data Privacy
- User data encryption in transit
- Session data isolation
- Audit trail for all interactions
- GDPR compliance features

### Rate Limiting
- Per-user request throttling
- IP-based fallback limits
- Gradual backoff mechanisms
- Abuse detection patterns

## API Documentation

### OpenAPI/Swagger
FastAPI automatically generates interactive API documentation at:
- `/docs` - Swagger UI
- `/redoc` - ReDoc interface

### Example Usage
```python
import requests

# Chat request
response = requests.post("http://localhost:8000/chat/", json={
    "message": "What does erf size mean?",
    "user_info": {
        "email": "user@company.com",
        "name": "User Name"
    }
})

chat_response = response.json()
session_id = chat_response["session_id"]

# Follow-up question
response = requests.post("http://localhost:8000/chat/", json={
    "message": "How do I measure it?", 
    "session_id": session_id,
    "user_info": {
        "email": "user@company.com"
    }
})
```

## Future Enhancements

### Additional Endpoints
- `GET /chat/history/{session_id}` - Retrieve conversation history
- `POST /chat/feedback` - Submit response feedback
- `POST /chat/escalate` - Create support ticket
- `GET /chat/analytics` - Usage analytics dashboard

### Advanced Features
- WebSocket support for real-time chat
- Streaming responses for long answers
- Multi-language support
- Custom agent personalities
- Integration webhooks
