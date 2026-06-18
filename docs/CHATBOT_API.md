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
session  (one conversation; belongs to a user; has a `summary` label for the history UI)
└── interaction  (one turn)
      question, answer, status, created_at, completed_at,
      metadata { sources_count, query_type, sources_used, enhanced_query, confidence },
      escalation_required, escalation_reason,
      escalation_decision, escalation_decided_at,
      feedback { type, comment, at },
      ticket   { ticket_id, subject, priority, status, agent_name, root_cause, solution_steps, created_at, closed_at }
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
  "created_at":"…","completed_at":"…",
  "metadata":{"sources_count":1,"query_type":"howto","sources_used":["Syncing listings to portals"],"enhanced_query":"…","confidence":0.78},
  "escalation_required":false,"escalation_reason":"none",
  "escalation_decision":null,"escalation_decided_at":null,   // 'create-ticket'|'decline'|null
  "feedback":null,
  "ticket":null   // when set: {ticket_id, subject, priority, status:'open'|'closed', agent_name, root_cause, solution_steps, created_at, closed_at}
}}
```
Poll this after a refresh if a stream was interrupted (`status` tells you if it finished).
This matches the agreed `TInteraction` type exactly (snake_case fields).

### 3. `POST /api/chatbot/interactions/{id}/feedback` — 👍 / 👎
```json
{ "feedback_type": "positive", "comment": "optional" }     // "positive" | "negative"
```
→ `{ "success": true, "message": "Feedback saved" }`

### 4. `POST /api/chatbot/interactions/{id}/escalation` — record the escalation decision
Send **only** the decision. The backend builds the conversation history itself (from the
session's stored interactions) — it never trusts a UI-supplied transcript.
```json
{ "escalationDecision": "create-ticket" }      // or "decline"
```
- `decline` → records the decision, no ticket → `{ "success": true, "decision": "decline" }`
- `create-ticket` → records the decision, builds trusted history, raises a Freshdesk ticket
  → `{ "success": true, "ticket_id": 18500, "message": "Ticket #18500 created" }`

Both decisions store `escalation_decision` + `escalation_decided_at` on the interaction.
`create-ticket` is idempotent (a second call returns the existing ticket). The resolution
(root cause / steps, `status:"closed"`) is written back onto the interaction's `ticket`
automatically when support closes the ticket.

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
- **Field casing — needs a decision (contract item #1):** stored docs and GET responses are
  `snake_case` (matches your `TInteraction`), but the escalation request you specified uses
  `camelCase` (`escalationDecision`), and `POST /interactions` uses `snake_case` (`session_id`,
  `user_info`). Let's pick one rule: **(a)** request bodies `camelCase` + stored/responses
  `snake_case`, or **(b)** everything `snake_case`. Right now the escalation endpoint **accepts
  both** `escalationDecision` and `escalation_decision` so you're not blocked — but we should
  lock the rule and make it consistent.
- **Streaming:** answers stream token-by-token (the backend uses a self-hosted model for this).
- **Errors:** a failed turn ends the stream with `{"type":"error","message":"…"}` and the
  interaction is saved with `status:"failed"`.
