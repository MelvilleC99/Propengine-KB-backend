# Customer Agent — Frontend API Reference

> **Last updated:** 2026-06-02
> **Audience:** the frontend designer/developer building the customer-facing chat.
> **Base URL:** `import.meta.env.VITE_BACKEND_URL` (local: `http://localhost:8000`).
> All requests are JSON: header `Content-Type: application/json`. No auth header today.

The customer chat flow uses **5 endpoints** (all POST except one PATCH). There is **no GET**
needed for the chat itself — sessions are tracked by passing `session_id` back in each call.

---

## The flow at a glance

```
1. User sends a message      → POST /api/agent/customer/           (chat)
2. User clicks 👍 / 👎       → POST /api/feedback/                 (feedback)
3. Agent can't answer        → response has requires_escalation:true; UI offers "Create ticket?"
4a. User clicks "Yes"        → POST /api/agent-failure/            (record the failure → get failure_id)
                             → POST /api/agent-failure/{id}/create-ticket   (create the ticket)
4b. User clicks "No thanks"  → PATCH /api/agent-failure/{id}/decline
```

---

## 1. Chat — `POST /api/agent/customer/`

Send the user's message, get the agent's reply.

**Request**
```json
{
  "message": "how do I create a listing",
  "session_id": "abc123 | null",      // null on the first message; reuse what comes back
  "user_info": { "email": "user@x.com", "name": "Jane" }   // optional
}
```

**Response**
```json
{
  "response": "To create a listing, follow these steps...",
  "session_id": "abc123",             // SAVE this and send it back on the next message
  "timestamp": "2026-06-02T14:33:00",
  "requires_escalation": false        // if true → show the "Create a ticket?" prompt
}
```

> **Streaming option (optional, nicer UX):** `POST /api/agent/customer/stream` returns the
> answer token-by-token instead of all at once. Different response format (NDJSON) — see
> `docs/STREAMING_CONTRACT.md`. Use the non-streaming one above to start; add streaming later.

---

## 2. Feedback — `POST /api/feedback/`

Submit 👍 / 👎 on a specific agent response.

**Request**
```json
{
  "session_id": "abc123",
  "message_id": "msg-1",              // your client-side id for the message being rated
  "feedback_type": "positive",        // "positive" | "negative"
  "query": "how do I create a listing",
  "response": "To create a listing...",
  "user_email": "user@x.com",         // optional
  "agent_type": "customer"            // optional
  // agent_id is OPTIONAL for customers (they don't have one)
}
```

**Response**
```json
{ "success": true, "feedback_id": "fb-123", "message": "Feedback recorded" }
```

---

## 3. Record an escalation — `POST /api/agent-failure/`

Call this when `requires_escalation` was `true` and the user clicks **"Yes, create ticket."**
This records the failure and returns a `failure_id` you use in step 4.

**Request**
```json
{
  "session_id": "abc123",
  "query": "how do I create a listing",
  "agent_response": "I couldn't find...",
  "confidence_score": 0.0,
  "escalation_reason": "no_results",  // e.g. "low_confidence" | "no_results"
  "user_email": "user@x.com",
  "user_name": "Jane",                // optional
  "user_agency": "...",               // optional
  "user_office": "...",               // optional
  "agent_type": "customer",
  "agent_id": null                    // customers don't have one
}
```

**Response** → contains the `failure_id` to use next.

---

## 4. Create the support ticket — `POST /api/agent-failure/{failure_id}/create-ticket`

Uses the `failure_id` from step 3 to create the actual Freshdesk ticket.

**Request**
```json
{
  "user_phone": "0123456789",         // optional
  "conversation_history": [ ... ]     // optional: recent messages for ticket context
}
```

**Response** → `{ "success": true, "ticket_id": 123, ... }` (or an error).

> ⚠️ This endpoint is currently being debugged (Freshdesk returns a `400` in some cases —
> backend fix in progress). The frontend wiring is correct; the failure is server-side.

---

## 5. Decline escalation — `PATCH /api/agent-failure/{failure_id}/decline`

Call when the user clicks **"No thanks"** on the escalation prompt. Marks the failure as declined.

**Request:** none needed (the `failure_id` is in the URL).

---

## Notes for the designer
- **Always thread `session_id`:** save it from the first chat response and send it back on every
  subsequent message so the conversation has memory.
- **Escalation is 2 calls, not 1:** record the failure (3) → then create the ticket (4) with the
  returned `failure_id`.
- **Errors before a response is sent** come back as normal HTTP status codes (e.g. `429` rate
  limit, `422` validation). Handle `429` with a "slow down / try later" message.
- **CORS:** the frontend must run on an allowed origin — `localhost:5173`, `localhost:3000`,
  `localhost:3001`, or `127.0.0.1:5173`. Other ports need adding to the backend allow-list.
- **No GET needed** for the chat flow. (GET endpoints like `/api/agent/customer/health` and
  `/api/agent-failure/stats` exist but the customer UI doesn't need them.)
