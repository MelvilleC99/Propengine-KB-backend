# Chat Agent API - Frontend Integration Guide

Base URL: `https://knowledge-base-backend-hrjhw2yiva-uc.a.run.app`

---

## 1. Chat Endpoint

**`POST /api/agent/customer/`**

The main chat endpoint for customer-facing CRM integration.

### Request

```json
{
  "message": "How do I create a listing?",
  "session_id": "optional-existing-session-id",
  "user_info": {
    "agent_id": "BID-12345",
    "email": "user@agency.co.za",
    "name": "John Smith",
    "agency": "Best Properties",
    "office": "Cape Town"
  }
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `message` | string | Yes | The user's message |
| `session_id` | string | No | Pass back the `session_id` from the previous response to maintain conversation. Omit on first message to start new session |
| `user_info` | object | No | User details. `agent_id` and `email` are used for rate limiting |

### Response

```json
{
  "response": "To create a listing in PropertyEngine...",
  "session_id": "abc-123-def",
  "timestamp": "2026-02-09T14:30:00.000000",
  "requires_escalation": false
}
```

| Field | Type | Notes |
|-------|------|-------|
| `response` | string | The AI agent's reply. If escalation is triggered, this will include the escalation prompt (see Escalation Flow below) |
| `session_id` | string | Always store this and send it back on the next message |
| `timestamp` | string | ISO 8601 timestamp |
| `requires_escalation` | boolean | `true` when the agent couldn't answer confidently. Frontend should show ticket creation UI |

### Rate Limit

- 100 requests per day per user (identified by `agent_id` > `email` > IP)
- Returns `429` when exceeded

```json
{
  "error": "Rate limit exceeded",
  "message": "Too many query requests. Try again in 3600 seconds.",
  "limit": 100,
  "remaining": 0,
  "reset_in_seconds": 3600
}
```

Rate limit headers are included on every response:
- `X-RateLimit-Limit` - Total limit
- `X-RateLimit-Remaining` - Requests left
- `X-RateLimit-Reset` - Unix timestamp when limit resets
- `Retry-After` - Seconds until reset (on 429 only)

---

## 2. Escalation Flow

When `requires_escalation: true`, the backend has already appended an escalation prompt to the `response` text. The flow depends on the scenario:

### Escalation Scenarios

| Scenario | Trigger | What happens |
|----------|---------|--------------|
| No results found | Agent found nothing in the KB | Response includes: *"...Would you like me to create a support ticket so our team can help you directly?"* |
| Low confidence | Confidence < 50% | Response includes: *"...Does this help answer your question, or would you like me to create a support ticket for more detailed assistance?"* |
| User requests help | User explicitly asks for human / ticket | Response: *"I'll help you raise a support ticket right away..."* |

### Frontend Implementation

When `requires_escalation` is `true`:

1. Display the response as normal (it contains the escalation prompt)
2. Show two buttons: **"Create Ticket"** and **"No thanks"**
3. Based on user choice, call the appropriate endpoint below

---

## 3. Create Failure Record

**`POST /api/agent-failure/`**

Call this when `requires_escalation: true` AND the user wants to create a ticket. This stores the failure context and returns a `failure_id` needed for ticket creation.

### Request

```json
{
  "session_id": "abc-123-def",
  "agent_id": "BID-12345",
  "query": "How do I bulk upload listings?",
  "agent_response": "I don't have enough information to fully answer this...",
  "confidence_score": 0.35,
  "escalation_reason": "low_confidence",
  "user_email": "user@agency.co.za",
  "user_name": "John Smith",
  "user_agency": "Best Properties",
  "user_office": "Cape Town",
  "agent_type": "customer"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `session_id` | string | Yes | From the chat response |
| `agent_id` | string | Yes | User's agent/business ID |
| `query` | string | Yes | The user's original question |
| `agent_response` | string | Yes | The AI response that wasn't sufficient |
| `confidence_score` | float | Yes | 0-1 (pass 0 if not available) |
| `escalation_reason` | string | Yes | `"low_confidence"` \| `"no_results"` \| `"user_requested"` |
| `user_email` | string | No | Falls back to `support@propertyengine.co.za` if empty |
| `user_name` | string | No | Requester name on the ticket |
| `user_agency` | string | No | Populated on the Freshdesk `cf_agency` field |
| `user_office` | string | No | Populated on the Freshdesk `cf_office` field |
| `agent_type` | string | No | `"customer"` for CRM integration |

### Response

```json
{
  "success": true,
  "failure_id": "fail_abc123",
  "message": "Failure recorded"
}
```

Store the `failure_id` -- you need it for the next step.

---

## 4. Create Freshdesk Ticket

**`POST /api/agent-failure/{failure_id}/create-ticket`**

Creates the actual Freshdesk support ticket. Call this immediately after creating the failure record.

### Request

```json
{
  "user_phone": "+27 82 123 4567",
  "conversation_history": [
    { "role": "user", "content": "How do I bulk upload?" },
    { "role": "assistant", "content": "I don't have information on bulk uploads..." },
    { "role": "user", "content": "Can you raise a ticket?" }
  ]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_phone` | string | No | Adds phone to the ticket |
| `conversation_history` | array | No | Last N messages. Included in ticket description for support context. Each item: `{ "role": "user"|"assistant", "content": "..." }` |

### Response (Success)

```json
{
  "success": true,
  "ticket_id": 9513,
  "message": "Ticket #9513 created"
}
```

### Response (Ticket Already Exists)

```json
{
  "success": true,
  "ticket_id": 9513,
  "message": "Ticket already exists"
}
```

The ticket is created in Freshdesk with:
- **Subject:** `PropertyEngine AI Support: {first 50 chars of query}`
- **Priority:** Auto-calculated (High if confidence < 30% or urgent keywords, Medium if < 60%, Low otherwise)
- **Tags:** `["propertyengine", "ai-escalation"]`

---

## 5. Decline Ticket

**`PATCH /api/agent-failure/{failure_id}/decline`**

Call this if the user chose "No thanks" after the escalation prompt.

### Request

No body required. Just the `failure_id` in the URL.

### Response

```json
{
  "success": true,
  "message": "Marked as declined"
}
```

---

## 6. Submit Feedback

**`POST /api/feedback/`**

Thumbs up / thumbs down on any agent response.

### Request

```json
{
  "session_id": "abc-123-def",
  "message_id": "msg-unique-id",
  "feedback_type": "positive",
  "query": "How do I create a listing?",
  "response": "To create a listing in PropertyEngine...",
  "agent_id": "BID-12345",
  "user_email": "user@agency.co.za",
  "user_name": "John Smith",
  "agent_type": "customer",
  "confidence_score": 0.85,
  "sources_used": ["Creating Listings Guide", "Listing Setup FAQ"]
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `session_id` | string | Yes | Current session |
| `message_id` | string | Yes | Unique ID for the message being rated (generate on frontend) |
| `feedback_type` | string | Yes | `"positive"` or `"negative"` |
| `query` | string | Yes | The question that was asked |
| `response` | string | Yes | The response being rated |
| `agent_id` | string | Yes | User's agent/business ID |
| `user_email` | string | No | |
| `user_name` | string | No | |
| `agent_type` | string | No | `"customer"` |
| `confidence_score` | float | No | From internal tracking if available |
| `sources_used` | string[] | No | KB entry titles used in the response |

### Response

```json
{
  "success": true,
  "feedback_id": "fb_xyz789",
  "message": "Feedback saved successfully"
}
```

---

## 7. End Session

**`POST /api/sessions/end`**

Call this when the chat ends. Writes all session analytics to the database.

### Request

```json
{
  "session_id": "abc-123-def",
  "agent_id": "BID-12345",
  "reason": "user_ended"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `session_id` | string | Yes | The session to end |
| `agent_id` | string | Yes | Required for analytics |
| `reason` | string | No | Default: `"user_ended"`. Other values: `"inactivity"`, `"escalated"`, `"browser_closed"` |

### Response

```json
{
  "success": true,
  "message": "Session abc-123-def ended successfully",
  "reason": "user_ended",
  "status": "ended"
}
```

### When to Call

- User clicks "End Chat" or closes the chat widget
- 30 minutes of inactivity (frontend timer)
- After successful ticket creation (reason: `"escalated"`)
- Browser/tab close (`beforeunload` event with `navigator.sendBeacon`)

---

## 8. Check Session Status

**`GET /api/sessions/{session_id}/should-end`**

Optional polling endpoint to check if the backend thinks the session should end.

### Response

```json
{
  "session_id": "abc-123-def",
  "should_end": false,
  "reason": "active",
  "message_count": 12,
  "escalations": 0,
  "status": "active"
}
```

Backend will return `should_end: true` when:
- 50+ messages in session
- 24+ hours since session started
- User was escalated to human support
- 2+ hours of inactivity

---

## Complete Chat Flow

```
User opens chat
    |
    v
POST /api/agent/customer/          <-- No session_id on first message
    |
    v
Store session_id from response
    |
    v
[User sends more messages] ------> POST /api/agent/customer/  (with session_id)
    |
    v
requires_escalation = true?
    |
    +----- NO ----> Show response, optional thumbs up/down
    |                   |
    |                   v
    |               POST /api/feedback/  (on thumb click)
    |
    +----- YES ---> Show response + "Create Ticket" / "No Thanks" buttons
                        |
                        +--- "Create Ticket" clicked:
                        |       1. POST /api/agent-failure/         --> get failure_id
                        |       2. POST /api/agent-failure/{id}/create-ticket  --> get ticket_id
                        |       3. Show "Ticket #XXXX created" confirmation
                        |       4. POST /api/sessions/end (reason: "escalated")
                        |
                        +--- "No Thanks" clicked:
                                1. PATCH /api/agent-failure/{id}/decline
                                2. Continue chatting

User closes chat
    |
    v
POST /api/sessions/end
```

---

## Error Handling

All endpoints return standard error responses:

| Status | Meaning | Action |
|--------|---------|--------|
| `400` | Bad request (missing required fields) | Check request body |
| `404` | Resource not found (invalid failure_id, session_id) | Check IDs |
| `429` | Rate limit exceeded | Show "Try again later" with `Retry-After` header value |
| `500` | Server error | Show generic error, allow retry |

Error response format:
```json
{
  "detail": "Human-readable error message"
}
```

---

## Rate Limits Summary

| Endpoint | Limit | Window |
|----------|-------|--------|
| Chat (`/api/agent/customer/`) | 100/day | 24 hours |
| Feedback (`/api/feedback/`) | 50/day | 24 hours |
| Failures + Tickets (`/api/agent-failure/`) | 10/day | 24 hours |

Rate limits are per user, identified by (in priority order): `agent_id` > `user_email` > IP address.
