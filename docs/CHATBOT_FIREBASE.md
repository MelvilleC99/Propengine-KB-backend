# Chatbot Firebase Schema — what the chatbot writes, and where

> **Scope:** the **new** interaction-centric chatbot (`/api/chatbot/*`). This is the single
> source of truth for the collections + fields the chatbot agent writes to.
> Live conversation memory (the model's short-term context) is **Redis**, not Firestore.

## TL;DR — the chatbot writes to exactly TWO Firestore collections
| Collection | One document per | Holds |
|---|---|---|
| **`chatbot_sessions`** | conversation | who/when + a `summary` label + counters |
| **`chatbot_interactions`** | turn (Q→A) | the whole turn: question, answer, sources, feedback, escalation, ticket |

Everything about a turn lives in **one** `chatbot_interactions` document — feedback, escalation
and the ticket are **updates to that same document**, not separate collections.

---

## `chatbot_sessions` (one per conversation)
```jsonc
{
  "id": "a1b2-…",              // doc id; the backend creates this (frontend echoes it back)
  "created_by": "<user-id>",   // from the auth token (NOT the request body)
  "user_email": "jane@x.co",   // business-context snapshot (mirrors the request payload)
  "user_name": "Jane",
  "account_id": 1092, "account_label": "Demo Office Account",   // PropertyEngine account
  "office_id": 8496,  "office_label": "First Office",           // PropertyEngine office
  "summary": null,             // short label for the history UI (populated later)
  "interaction_count": 3,
  "status": "active",
  "created_at": <timestamp>,
  "last_activity": <timestamp>
}
```

## `chatbot_interactions` (one per turn) — matches the agreed `TInteraction`
```jsonc
{
  "id": "c3d4-…",
  "session_id": "a1b2-…",
  "created_by": "<user-id>",

  "question": "how do I create a listing?",
  "answer": "To create a listing… (1.… 2.…)",   // null until the stream completes
  "status": "complete",                          // streaming | complete | failed
  "created_at": <timestamp>,
  "completed_at": <timestamp>,                   // null until complete

  "metadata": {
    "sources_count": 2,
    "sources_used": ["How to create a listing", "Mandate setup"],  // which KB entries answered it
    "query_type": "howto",
    "enhanced_query": "create a property listing steps",
    "confidence": 0.82
  },

  "escalation_required": false,        // the "failure" flag (agent couldn't answer)
  "escalation_reason": "none",         // none | no_results | low_confidence | non_answer | user_requested
  "escalation_decision": null,         // 'create-ticket' | 'decline' | null  (set when the user decides)
  "escalation_decided_at": null,       // ISO string | null

  "feedback": null,                    // { type: 'positive'|'negative', comment, at } | null

  "ticket": null                       // null until a ticket is raised; then:
  // {
  //   "ticket_id": 18500, "subject": "...", "priority": "3",
  //   "status": "open",                    // 'open' | 'closed'
  //   "agent_name": "", "root_cause": "", "solution_steps": "",   // filled by the close-webhook
  //   "created_at": "...", "closed_at": ""
  // }
}
```

---

## When each write happens (the lifecycle of one turn)
| Event | Endpoint | Write |
|---|---|---|
| User sends a message | `POST /api/chatbot/interactions` | create `chatbot_sessions` (if new) + create `chatbot_interactions` (`status: streaming`) |
| Answer finishes streaming | (same request) | update the interaction → `answer`, `status: complete`, `metadata` |
| Agent couldn't answer | (same request) | sets `escalation_required: true` + `escalation_reason` on the interaction |
| User 👍/👎 | `POST …/{id}/feedback` | update the interaction → `feedback` |
| User decides on a ticket | `POST …/{id}/escalation` | update → `escalation_decision` (+ `ticket` if create-ticket) |
| Support closes the ticket | Freshdesk close-webhook | update the interaction's `ticket` → `status: closed` + resolution |

**Analytics (separate, kept):** `kb_analytics` / kb_stats — per-KB-entry usage (which entries get
used). Not part of the per-turn record; written fire-and-forget.

---

## Legacy collections — being RETIRED (do not build on these)
These are written **only** by the old endpoints (`/api/agent/customer/stream`, `/api/feedback`,
`/api/agent-failure`). They disappear once the frontend is fully on `/api/chatbot/*`:

| Legacy collection | Replaced by |
|---|---|
| `kb_sessions` | `chatbot_sessions` |
| `response_feedback` | `chatbot_interactions.feedback` |
| `agent_failures` | `chatbot_interactions.escalation_*` + `.ticket` |

During the migration **both** sets exist (that's why data looks split). Cutover = point the
frontend at `/api/chatbot/*` and disable the legacy endpoints — see `CHATBOT_API.md`.
