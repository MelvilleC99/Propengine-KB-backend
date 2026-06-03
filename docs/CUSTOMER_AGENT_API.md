# Customer Agent — Frontend API Reference

> **Audience:** the frontend developer building the **customer-facing** chat.
> **Scope:** the customer agent only. (Support/test agents use the same shapes with a different
> path — see [AGENT_PIPELINE.md](AGENT_PIPELINE.md).)
> **Base URL:** set via env (Vite: `VITE_BACKEND_URL`). All requests are JSON
> (`Content-Type: application/json`) and must include the user's Firebase token —
> `Authorization: Bearer <id-token>`. See [FRONTEND_AUTH.md](FRONTEND_AUTH.md) for how to attach it.
> (Enforced when the backend's `REQUIRE_AUTH` is on; harmless to send when off.)

The chat is **streaming-only**. The old non-streaming `POST /api/agent/customer/` has been removed.

---

## The flow at a glance

```
1. User sends a message      → POST /api/agent/customer/stream      (chat, NDJSON stream)
2. User clicks 👍 / 👎       → POST /api/feedback/                  (feedback)
3. Agent can't answer        → metadata frame has requires_escalation:true; UI offers "Create ticket?"
4a. User clicks "Yes"        → POST /api/agent-failure/             (record failure → get failure_id)
                             → POST /api/agent-failure/{id}/create-ticket   (create the ticket)
4b. User clicks "No thanks"  → PATCH /api/agent-failure/{id}/decline
```

---

## 1. Chat — `POST /api/agent/customer/stream`

**Request**
```json
{
  "message": "how do I create a listing",
  "session_id": null,                       // null on the FIRST message; then echo back what you get
  "user_info": { "email": "user@x.com", "name": "Jane" }   // optional
}
```

**Response:** `application/x-ndjson` — one JSON object per line, in this order:

```jsonc
{"type":"session","session_id":"5453d3df-..."}     // 1. ALWAYS first — save this id
{"type":"sources","sources":[ ... ]}               // 2. source cards (show immediately)
{"type":"token","text":"To create "}              // 3. many of these — append to the bubble
{"type":"token","text":"a listing..."}
{"type":"metadata","confidence":1.0,"requires_escalation":false, ...}  // 4. once, at the end
{"type":"done"}                                    // 5. stream complete
// on failure instead: {"type":"error","message":"..."}
```

**How to consume it (browser):**
```js
const res = await fetch(`${BASE}/api/agent/customer/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ message, session_id, user_info }),
});
const reader = res.body.getReader();
const decoder = new TextDecoder();
let buf = "";
for (;;) {
  const { value, done } = await reader.read();
  if (done) break;
  buf += decoder.decode(value, { stream: true });
  const lines = buf.split("\n");
  buf = lines.pop();                         // keep the partial last line
  for (const line of lines) {
    if (!line.trim()) continue;
    const frame = JSON.parse(line);
    // switch(frame.type): session | sources | token | metadata | done | error
  }
}
```

---

## `session_id` and `user_info` — what to pass

**`session_id` — conversation memory.** Send `null` on the first message; the backend creates a
session and returns the id in the **`session` frame**. Save it and send it back on every
subsequent message so the agent remembers context. Reset to `null` to start a new chat. If you
send an invalid/expired id, the backend silently starts a fresh session.

**`user_info` — who's asking** (all fields optional). The backend reads:

| Key | Used for |
|---|---|
| `email` | rate limiting (per-user) + logging + stored on the session |
| `agent_id` | rate limiting + stored — **internal staff only**; customers don't have one |
| `name` | stored on session; used in escalation tickets |
| `company`, `division`, `agency`, `office`, `user_type` | stored as session metadata (analytics/ticket context) |

For a customer, `{ "email": "..." }` is enough (even `{}` works for anonymous).

---

## 2. Feedback — `POST /api/feedback/`

```json
{
  "session_id": "abc123",
  "message_id": "msg-1",              // your client-side id for the message being rated
  "feedback_type": "positive",        // MUST be "positive" | "negative"
  "query": "how do I create a listing",
  "response": "To create a listing...",
  "user_email": "user@x.com",         // optional
  "agent_type": "customer"            // optional; agent_id is optional for customers
}
```
→ `{ "success": true, "feedback_id": "fb-123", "message": "Feedback recorded" }`

> ⚠️ `feedback_type` must be exactly `"positive"` or `"negative"` (not "helpful"/"unhelpful").
> Also POST to the path **with the trailing slash** (`/api/feedback/`) to avoid a 307 redirect.

---

## 3. Record an escalation — `POST /api/agent-failure/`

Call when `requires_escalation` was `true` and the user clicks **"Yes, create ticket."** Returns a
`failure_id` for step 4.

```json
{
  "session_id": "abc123",
  "query": "how do I create a listing",
  "agent_response": "I couldn't find...",
  "confidence_score": 0.0,
  "escalation_reason": "no_results",  // e.g. "low_confidence" | "no_results"
  "user_email": "user@x.com",
  "user_name": "Jane",                // optional
  "agent_type": "customer",
  "agent_id": null                    // customers don't have one
}
```

## 4. Create the ticket — `POST /api/agent-failure/{failure_id}/create-ticket`

```json
{ "user_phone": "0123456789", "conversation_history": [ ... ] }   // both optional
```
→ `{ "success": true, "ticket_id": 123, ... }` (or an error).

> ⚠️ A valid **requester email** is required for Freshdesk; an empty/placeholder email can cause a
> `400`. Pass the user's real email in `user_info.email` (step 1) / the failure record (step 3).

## 5. Decline escalation — `PATCH /api/agent-failure/{failure_id}/decline`

Call when the user clicks **"No thanks."** No body needed (`failure_id` is in the URL).

---

## Notes for the developer
- **Always thread `session_id`** (save from the `session` frame, resend each message).
- **Escalation is 2 calls:** record the failure (3) → create the ticket (4) with the returned id.
- **Pre-stream errors** are normal HTTP codes: handle `429` (rate limit) with a "try again shortly"
  message and `422` (validation) as a bug in the request body.
- **`401 Unauthorized`** → the Firebase token is missing/expired; send the user back to login
  (see [FRONTEND_AUTH.md](FRONTEND_AUTH.md)).
- **CORS:** your origin must be on the backend allow-list.
