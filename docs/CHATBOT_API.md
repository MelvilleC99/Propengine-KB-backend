# Chatbot API — Integration Reference

> **Audience:** the developer integrating the **customer chatbot into PropertyEngine (PE)**.
> **Scope:** the new interaction-centric `/api/chatbot/*` API (sessions + interactions).
> **Base URL:** the deployed backend (Cloud Run). All requests are JSON
> (`Content-Type: application/json`).
> **Auth:** `Authorization: Bearer <token>`. During the current testing window the chatbot is
> open (no token required); in production it expects a verified token (see [Auth](#auth--what-we-need-from-pe)).

This API supersedes the older scattered customer endpoints (`/api/agent/customer/stream`,
`/api/feedback`, `/api/agent-failure`). Both run **in parallel** during migration — switch the
frontend to `/api/chatbot/*` when ready; the old ones keep working until then.

The backend owns all logic and storage. The collection/field names below are how the JSON is
returned to you — you never talk to the database directly.

---

## The model in one picture

Each **turn** is one durable `interaction` record (question → answer → sources → feedback →
escalation → ticket). Interactions are grouped under a `session` (one conversation).

```
session  (one conversation, belongs to a user)
└── interaction  (one turn)
      question, answer, status,
      metadata { confidence, sources_used },
      escalation_required, escalation_reason,
      feedback { type, comment },
      ticket   { ticket_id, status, root_cause, solution_steps }
```

---

## The flow at a glance

```
1. User sends a message   → POST /api/chatbot/interactions               (chat, NDJSON stream)
2. User clicks 👍 / 👎    → POST /api/chatbot/interactions/{id}/feedback
3. Agent can't answer     → metadata frame has escalation_required:true; UI offers "Create ticket?"
4. User confirms ticket   → POST /api/chatbot/interactions/{id}/escalation
5. Show past chats        → GET  /api/chatbot/sessions  +  GET /api/chatbot/sessions/{id}
```

The backend decides escalation (low confidence / no results / non-answer / user asked) and sets
`escalation_required`. The frontend just **reacts to that flag** — no thresholds client-side.

---

## Endpoints

### 1. `POST /api/chatbot/interactions` — ask a question (streams)
Creates (or continues) a session and a new interaction, then streams the answer.

**Request**
```json
{
  "message": "How do I sync my listing to Property24?",
  "session_id": null,           // null = start a new conversation; pass the id to continue one
  "user_info": {                // business context (snapshotted onto the session)
    "email": "jane@agency.co.za",
    "name": "Jane",
    "agency": "Acme", "office": "Sandton",
    "user_type": "external"
  }
}
```

**Response** — NDJSON stream (one JSON object per line). Read it via a chunked fetch.
```
{"type":"session","session_id":"a1b2…","interaction_id":"c3d4…"}   ← keep BOTH ids
{"type":"sources","sources":[{"title":"Syncing listings to portals"}]}
{"type":"token","text":"To sync "}                                  ← many of these
{"type":"token","text":"your listing…"}
{"type":"metadata","confidence":0.78,"requires_escalation":false,"escalation_reason":"none","query_type":"howto"}
{"type":"done"}
```
- Keep `interaction_id` — you need it for feedback, escalation, and resume.
- If the connection drops mid-stream, poll endpoint #2 to get the final answer.
- Frame order is fixed: `session → sources → token* → metadata → done` (or `error`).

### 2. `GET /api/chatbot/interactions/{id}` — read / resume one turn
```json
{ "success": true, "interaction": {
  "id":"c3d4…","session_id":"a1b2…","created_by":"<user-id>",
  "question":"…","answer":"…","status":"complete",          // streaming | complete | failed
  "metadata":{"confidence":0.78,"sources_used":["Syncing listings to portals"],"sources_count":1},
  "escalation_required":false,"escalation_reason":"none",
  "feedback":null,"ticket":null
}}
```
Poll this after a refresh if a stream was interrupted (`status` tells you if it finished).

### 3. `POST /api/chatbot/interactions/{id}/feedback` — 👍 / 👎
```json
{ "feedback_type": "positive", "comment": "optional" }     // "positive" | "negative"
```
→ `{ "success": true, "message": "Feedback saved" }`

### 4. `POST /api/chatbot/interactions/{id}/escalation` — raise a Freshdesk ticket
Reached by both flows (user asked, or agent offered after it couldn't answer).
```json
{ "user_phone": "optional", "conversation_history": [ /* optional */ ] }
```
→ `{ "success": true, "ticket_id": 18500, "message": "Ticket #18500 created" }`
Idempotent — a second call returns the existing ticket. The resolution (root cause / steps) is
written back onto the interaction automatically when support closes the ticket.

### 5. `GET /api/chatbot/sessions` — list the user's conversations
→ `{ "success": true, "sessions": [ {session…} ], "count": N }` (most recent first; needs auth)

### 6. `GET /api/chatbot/sessions/{id}` — one conversation + its turns
→ `{ "success": true, "session": { …, "interactions": [ {interaction…}, … ] } }`

---

## Auth — what we need from PE

The chatbot reads identity from the **token** (`created_by`), not the request body. The
business context (`user_type` especially — it controls which KB content is returned) should come
from **trusted token claims**, not the client.

When PE issues tokens, please confirm:

| Item | Why we need it |
|---|---|
| **Issuer (`iss`)** | to validate the token came from PE |
| **JWKS URL** (public keys) | to verify the RS256 signature (we hold no secret) |
| **Audience (`aud`)** | confirms the token is meant for this chatbot |
| **Claim names** | which claim is the user id (`sub`?), plus `email`, `role`, `user_type` |

(Today's other frontend uses Firebase tokens — a different issuer — so admin and chatbot tokens
are naturally separated by issuer; `aud` is an extra guard.)

---

## Notes for the build
- **Field casing:** responses currently use `snake_case` (`session_id`, `escalation_required`).
  If your types expect `camelCase`, tell us and we'll map the response keys — easy change, but
  let's agree it before you build against it.
- **Streaming:** answers stream token-by-token (the backend uses a self-hosted model for this).
- **Errors:** a failed turn ends the stream with `{"type":"error","message":"…"}` and the
  interaction is saved with `status:"failed"`.
