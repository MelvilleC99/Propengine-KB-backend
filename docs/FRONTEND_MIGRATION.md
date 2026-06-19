# Frontend Migration — old endpoints → new `/api/chatbot/*`

> For the Penny frontend. Today (verified live) Penny calls the **legacy** endpoints. This is
> the exact swap to the new interaction-centric API. Base URL is unchanged.

## The one concept that changes: everything keys off `interaction_id`
Old flow used `message_id` (feedback) and a separate `failure_id` (tickets). **New flow: the
chat response returns an `interaction_id`, and feedback + escalation both use it.** There is **no
separate "create failure" call** anymore — the failure is recorded automatically on the interaction.

Capture it from the **first frame** of the chat stream:
```jsonc
{"type":"session","session_id":"…","interaction_id":"c3d4…"}   // ← store BOTH
```

## Endpoint swap (what Penny does today → what to call instead)

### 1. Chat
| | |
|---|---|
| OLD | `POST /api/agent/customer/stream` |
| NEW | `POST /api/chatbot/interactions` |
Body is the same shape: `{ "message", "session_id"?, "user_info" }`. Response is the same NDJSON
stream — just also carries `interaction_id` in the opening `session` frame. **Store `interaction_id`.**
(Reminder: concatenate `token` frames directly — no space separator.)

### 2. Feedback (👍 / 👎)
| | |
|---|---|
| OLD | `POST /api/feedback/` (big body with session_id/message_id/query/response…) |
| NEW | `POST /api/chatbot/interactions/{interaction_id}/feedback` |
New body is just: `{ "feedback_type": "positive" \| "negative", "comment"?: string }`

### 3. Raise a ticket
| | |
|---|---|
| OLD | `POST /api/agent-failure/` → get `failure_id` → `POST /api/agent-failure/{failure_id}/create-ticket` |
| NEW | `POST /api/chatbot/interactions/{interaction_id}/escalation` |
New body: `{ "escalationDecision": "create-ticket" }`. **Drop the `POST /api/agent-failure/`
create-failure call entirely** — it's gone. The backend builds the conversation history itself.

### 4. Decline a ticket
| | |
|---|---|
| OLD | (PATCH decline on the failure) |
| NEW | `POST /api/chatbot/interactions/{interaction_id}/escalation` with `{ "escalationDecision": "decline" }` |

### 5. Conversation history (new capability)
- `GET /api/chatbot/sessions` — list the user's past conversations
- `GET /api/chatbot/sessions/{session_id}` — one conversation + all its turns

## Knowing when to escalate (unchanged)
The chat's `metadata` frame still carries `requires_escalation` + `escalation_reason`. The UI
reacts to that flag to offer the "create a ticket?" button — same as today.

## Cutover
Once Penny calls `/api/chatbot/*` for **chat + feedback + ticket**, tell us and we set
`ENABLE_LEGACY_ENDPOINTS=false` + deploy → the old endpoints are retired and everything writes to
`chatbot_interactions` only. Until then both run in parallel (don't disable the old ones early).

See `CHATBOT_API.md` for full request/response detail and `CHATBOT_FIREBASE.md` for the stored schema.
