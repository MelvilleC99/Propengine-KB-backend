# Agent System Architecture

This folder contains the intelligent agent system that processes user queries and generates responses for the PropertyEngine Knowledge Base.

## Files Overview

### `orchestrator.py`
**Purpose**: Main agent orchestrator with fail-safe protection and intelligent query routing
- Coordinates query classification, vector search, and response generation
- Implements fail-safe mechanisms to prevent infinite loops and cascading failures
- Manages conversation context and session integration
- Provides comprehensive error handling and fallback strategies

**Key Features**:
- **Fail-Safe Protection**: Prevents infinite loops with request tracking and circuit breakers
- **Query Classification**: Intelligent routing based on query type (definition, error, howto, etc.)
- **Multi-Stage Search**: Primary search with intelligent fallback strategies
- **Context-Aware Responses**: Uses conversation history for better responses
- **Performance Monitoring**: Tracks API calls, search attempts, and processing time

### Core Components

#### Request Tracking & Fail-Safes
```python
class RequestTracker:
    max_duration: 60 seconds          # Maximum processing time per request
    max_api_calls: 10                 # Maximum API calls per request
    max_search_attempts: 3            # Maximum vector search attempts
    max_retry_attempts: 3             # Maximum retries for failed operations
```

#### Circuit Breaker Protection
```python
class CircuitBreaker:
    failure_threshold: 5              # Open circuit after 5 consecutive failures
    recovery_timeout: 60 seconds      # Block requests for 60 seconds to recover
    states: closed, open, half_open   # Circuit breaker states
```

#### Search Strategy
1. **Primary Search**: Uses classified query type (definition, error, howto, etc.)
2. **Fallback 1**: Broader search without entry type filter
3. **Fallback 2**: Smart type-based fallbacks (howto → error, definition → error if query contains "error")
4. **Fail-Safe Exit**: All attempts tracked and limited by RequestTracker

## Query Processing Flow

```
1. User Query → Request Tracker Creation
              ↓
2. Query Classification → Fail-Safe Protected
              ↓
3. Vector Search (Primary) → Timeout Protected (15s)
              ↓
4. Fallback Searches → Max 3 attempts total
              ↓
5. LLM Response Generation → Timeout Protected (30s)
              ↓
6. Response + Fail-Safe Status → Frontend
```

## Fail-Safe Integration

### Protected Operations
All critical operations are wrapped with fail-safe protection:

```python
@with_failsafe("vector_search", timeout=15)
async def _perform_search(query, query_type, user_type, tracker):
    # Vector search with automatic timeout and circuit breaker

@with_failsafe("llm_generation", timeout=30)
async def _safe_generate_response(query, results, tracker):
    # LLM response generation with timeout protection
```

### Request Limits
Per-request limitations prevent resource abuse:
- **Total Processing Time**: 60 seconds maximum
- **API Calls**: 10 maximum (includes LLM + embeddings)
- **Search Attempts**: 3 maximum with intelligent fallbacks
- **Retry Operations**: 3 maximum per operation type

### Error Recovery
```python
# Graceful degradation strategy
try:
    # Primary operation
    result = await primary_operation()
except Exception:
    # Automatic fallback with circuit breaker
    if circuit_breaker.can_proceed():
        result = await fallback_operation()
    else:
        # Safe fallback response
        result = generate_safe_fallback()
```

## Performance Optimization

### Query Classification Caching
- Pattern-based classification (no LLM calls)
- Fast regex matching for common query types
- Fallback to "general" for unknown patterns

### Vector Search Optimization
- Metadata filtering reduces search space
- Similarity threshold filtering (0.7 default)
- Connection reuse via AstraDB connection pooling

### Response Generation
- Context limiting (top 3 search results)
- LLM timeout protection (30 seconds)
- Streaming responses for long queries (planned)

## Chat Summary Integration

The agent integrates with the chat summarization system:

### Summary Triggers
- **Every 5 messages**: Regular conversation summaries
- **Session end**: 30-minute timeout or explicit end
- **Escalation**: When queries require human intervention

### Summary Content
```python
{
    "summary": "2-3 sentence overview of conversation",
    "topics": ["property definitions", "error resolution"],
    "resolution_status": "resolved|partial|escalated|abandoned",
    "user_satisfaction": "satisfied|neutral|frustrated|unknown",
    "key_issues": "Main problems discussed",
    "outcome": "What was achieved",
    "message_count": 8,
    "session_duration": 450  # seconds
}
```

## Session Integration

### Session-Aware Processing
- User context influences search filtering
- Conversation history provides context for ambiguous queries
- User type filtering (internal, external, both)
- Session metadata tracking for analytics

### Message Logging Strategy
**New Approach** (Performance Optimized):
- Log only problematic interactions (low confidence, escalations)
- Generate summaries instead of storing every message
- Reduce Firebase writes by ~80% for normal successful queries

## Configuration & Settings

### Agent Settings
```python
# Response generation
MAX_SEARCH_RESULTS = 5               # Vector search result limit
SIMILARITY_THRESHOLD = 0.7           # Minimum similarity for results
ESCALATION_THRESHOLD = 0.7           # Escalate below this confidence

# Fail-safe settings
MAX_REQUEST_DURATION = 60            # Seconds per request
MAX_API_CALLS_PER_REQUEST = 10       # API call limit
VECTOR_SEARCH_TIMEOUT = 15           # Seconds
LLM_GENERATION_TIMEOUT = 30          # Seconds
```

### Query Type Classification
```python
PATTERNS = {
    "greeting": [r"\b(hi|hello|hey)\b"],
    "error": [r"\berror\s*\d+\b", r"\bissue\b", r"\bproblem\b"],
    "definition": [r"\bwhat (is|are|does)\b", r"\bdefine\b"],
    "howto": [r"\bhow (to|do|can)\b", r"\bsteps to\b"],
    "workflow": [r"\bworkflow\b", r"\bprocess\b"]
}
```

## Monitoring & Debugging

### Request Status Tracking
Every query returns detailed status information:
```python
"request_status": {
    "request_id": "query_session123",
    "elapsed_time": 2.5,
    "api_calls": 3,
    "search_attempts": 2,
    "retry_attempts": 0,
    "within_limits": True,
    "operations": ["API call #1", "Search attempt #1", "Search attempt #2"]
}
```

### Circuit Breaker Monitoring
```python
# System status endpoint provides circuit breaker states
{
    "circuit_breakers": {
        "vector_search": {"state": "closed", "failure_count": 0},
        "llm_generation": {"state": "open", "failure_count": 5}
    }
}
```

### Performance Metrics
- Average response time by query type
- Success/failure rates per operation
- Circuit breaker trip frequency
- Resource usage per request

## Error Handling

### Graceful Degradation
1. **Primary Failure**: Use fallback search strategies
2. **Search Failure**: Return relevant fallback response
3. **LLM Failure**: Use template-based responses
4. **Complete Failure**: Safe error message with escalation

### Error Response Format
```python
{
    "response": "Safe fallback message",
    "confidence": 0.0,
    "query_type": "error",
    "requires_escalation": True,
    "sources": [],
    "search_attempts": [],
    "request_status": {...},
    "error": "Detailed error for debugging"
}
```

## Future Enhancements

### Conversation Intelligence
- **Context Awareness**: Use previous messages to disambiguate queries
- **Intent Prediction**: Predict what user likely wants next
- **Proactive Suggestions**: Suggest related topics based on conversation

### Advanced Fail-Safes
- **Redis Circuit Breakers**: Persistent circuit breaker state across restarts
- **Rate Limiting Integration**: Coordinate with API rate limits
- **Resource Monitoring**: CPU/memory usage tracking

### Performance Improvements
- **Response Streaming**: Stream LLM responses for faster perceived performance
- **Search Caching**: Cache frequent queries to reduce vector search overhead
- **Connection Pooling**: Optimize database connection reuse

## Troubleshooting

### Common Issues

**High Latency (>3 seconds for simple queries)**
- Check AstraDB connection latency
- Monitor vector search performance (should be <100ms for small datasets)
- Review fail-safe timeouts and circuit breaker states

**Frequent Escalations**
- Review similarity thresholds (currently 0.7)
- Check knowledge base content quality and coverage
- Monitor search fallback success rates

**Circuit Breaker Trips**
- Check external service availability (OpenAI, AstraDB)
- Review error logs for recurring failure patterns
- Consider adjusting failure thresholds

### Debug Mode
Enable detailed logging for troubleshooting:
```python
# Set logging level to DEBUG for detailed operation tracking
import logging
logging.getLogger("src.agent").setLevel(logging.DEBUG)
```

## Integration Points

### With Session Manager
```python
# Session-aware message logging
session_manager.add_message(session_id, role, content, metadata)

# Conversation history retrieval
history = session_manager.get_history(session_id, limit=5)
```

### With Vector Search
```python
# Multi-strategy search with fail-safe protection
results = await vector_search.search(
    query=query,
    entry_type=query_type,
    user_type=user_filter,
    k=max_results
)
```

### With Chat Summary
```python
# Triggered every 5 messages or at session end
summary = chat_summarizer.create_summary(messages, session_info)
```
