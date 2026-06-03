# Firebase Collections

> What this backend reads/writes in Firestore, and what triggers each write.
>
> ⚠️ **The Firebase project is shared with other systems** (WhatsApp insights, Sudonum, BetterID,
> user registration, etc.). This document lists **only the collections this backend owns or
> touches** — not every collection you'll see in the Firestore console.

---

## Collections this backend writes

| Collection | What's written | Triggered by |
|---|---|---|
| **`kb_entries`** | A KB article: title, content, `entryType`, `userType`, `category`, `tags`, `vectorStatus` (`pending`/`synced`/`partial`), timestamps | Creating/editing a KB entry — `POST/PUT /api/kb/entries…` ([KB_INGESTION](KB_INGESTION.md)) |
| **`kb_sessions`** | One doc per chat session: `session_id`, `agent_id`, `user_email`, `created_at`, `status` (`active`→`ended`) | First message of a chat (create); session end (status update) |
| **`kb_messages`** | One doc per message: `session_id`, `role` (`user`/`assistant`), `content`, metadata (sources used, confidence, escalated) | Every user message and every agent reply |
| **`kb_stats`** | Per-KB-entry usage rollup: `parent_entry_id`, `entry_title`, `usage_count`, `avg_confidence`, `avg_similarity_score`, `first_used`, `last_used`, `last_query` | Each answered query, for every source it used (background write) |
| **`response_feedback`** | A 👍/👎: `session_id`, `message_id`, `feedback_type` (`positive`/`negative`), `query`, `response`, confidence, sources, user info, `timestamp` | `POST /api/feedback/` |
| **`agent_failures`** | An escalation: query, agent_response, confidence, `escalation_reason`, user details; later updated with `ticket_created`, `ticket_id` | `POST /api/agent-failure/` (create); `…/create-ticket` and `…/decline` (update) |
| **`kb_analytics`** | Aggregate analytics records | Analytics service (`firebase_analytics_service.py`) |
| **`users`** | User records (profile/permissions read & write) | `src/api/user_routes.py` |

---

## Where each lives in code

| Collection | Service file |
|---|---|
| `kb_entries` | `src/services/firebase/server.py` |
| `kb_sessions`, `kb_messages` | `src/database/firebase_session_service.py` |
| `kb_stats` | `src/memory/kb_analytics.py` |
| `response_feedback` | `src/database/firebase_feedback_service.py` |
| `agent_failures` | `src/database/firebase_agent_failure_service.py` |
| `kb_analytics` | `src/database/firebase_analytics_service.py` |
| `users` | `src/database/firebase_user_service.py` |

The dashboard (`src/api/dashboard_routes.py`) **reads** `kb_stats`, `response_feedback`,
`agent_failures`, and `kb_entries` to compute metrics — it does not write them.

---

## What happens to collections during one chat query

A single answered query touches three collections (the last two are **fire-and-forget** background
writes so they never block the response):

```
1. kb_messages   ← user message stored (step 1 of the pipeline)
2. kb_messages   ← assistant reply stored          (background)
3. kb_sessions   ← session created/updated         (background)
4. kb_stats      ← usage_count++ for each KB source used in the answer  (background)
```

See [AGENT_PIPELINE.md](AGENT_PIPELINE.md) for the full pipeline.

---

## Notes
- **Session truth is Redis, not Firestore.** Live conversation state (recent messages, rolling
  summary) lives in Redis for speed; `kb_sessions`/`kb_messages` are the durable record. If Redis
  is unavailable the backend falls back (see `src/memory/session_fallback.py`).
- **No PII beyond email/name** is stored on sessions by design; tickets carry more context but go to
  Freshdesk, not Firestore.
