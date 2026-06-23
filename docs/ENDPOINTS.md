# API Endpoints — the map

The one place that says what every endpoint is, who uses it, and its status. Mirrors the router
groups in `main.py`. (Live, browsable version: run the app and open `/docs`.)

## Groups at a glance
| Group | Prefix | Who | Auth | Status |
|---|---|---|---|---|
| **Public** | `/`, `/health` | monitoring | none | ✅ |
| **Customer chatbot (NEW)** | `/api/chatbot/*` | Penny (customers) | `_customer_auth` | ✅ **use this** |
| **Customer chatbot (LEGACY)** | `/api/agent/customer`, `/api/feedback`, `/api/agent-failure` | (old Penny) | `_customer_auth` | ⚠️ **deprecated — being retired** |
| **Webhooks** | `/api/agent-failure/webhook/*` | Freshdesk | `X-Webhook-Secret` | ✅ |
| **Internal KB agents** | `/api/agent/support`, `/api/agent/test` | staff consoles | `_auth` | ✅ |
| **Admin / KB management** | `/api/kb`, `/api/admin`, `/api/sessions`, `/api/users` | admin frontend | `_auth` (locked) | ✅ |

`_auth` = valid Firebase token (enforced when `REQUIRE_AUTH=true`).
`_customer_auth` = open while `CUSTOMER_AGENT_PUBLIC=true`, otherwise `_auth`.

---

## Customer chatbot — NEW (`/api/chatbot/*`) ✅ the current surface
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/chatbot/interactions` | ask a question (NDJSON stream) |
| GET | `/api/chatbot/interactions/{id}` | read / poll a turn |
| POST | `/api/chatbot/interactions/{id}/feedback` | 👍 / 👎 |
| POST | `/api/chatbot/interactions/{id}/escalation` | `{escalationDecision}` → raise/decline a ticket |
| GET | `/api/chatbot/sessions` | a user's conversations |
| GET | `/api/chatbot/sessions/{id}` | one conversation + its turns |

Writes to `chatbot_sessions` + `chatbot_interactions` (see `CHATBOT_FIREBASE.md`).

---

## Customer chatbot — LEGACY ⚠️ deprecated (gated by `ENABLE_LEGACY_ENDPOINTS`)
**Do not build new work against these.** Old→new mapping (full detail in `FRONTEND_MIGRATION.md`):

| Old (legacy) | New |
|---|---|
| `POST /api/agent/customer/stream` | `POST /api/chatbot/interactions` |
| `POST /api/feedback/` | `POST /api/chatbot/interactions/{id}/feedback` |
| `POST /api/agent-failure/` (create failure) | *(gone — failure is now a flag on the interaction)* |
| `POST /api/agent-failure/{id}/create-ticket` | `POST /api/chatbot/interactions/{id}/escalation` `{create-ticket}` |
| `PATCH /api/agent-failure/{id}/decline` | `POST /api/chatbot/interactions/{id}/escalation` `{decline}` |

### ⚠️ Gotcha before retiring these
The `feedback` and `agent-failure` legacy routers **also contain admin-dashboard endpoints**:
- `GET /api/feedback/stats`, `GET /api/feedback/negative`
- `GET /api/agent-failure/stats`, `GET /api/agent-failure/needs-kb`

So flipping `ENABLE_LEGACY_ENDPOINTS=false` removes **those too**. The admin dashboard also still
reads the **old** collections (`response_feedback`, `agent_failures`). **Retire the legacy
endpoints together with re-pointing the admin dashboard/analytics to `chatbot_interactions`** —
one clean pass, so nothing breaks.

---

## Webhooks ✅
| Method | Path | Auth |
|---|---|---|
| POST | `/api/agent-failure/webhook/fd-ticket-closed` | `X-Webhook-Secret` (not user auth) |

Freshdesk calls this on ticket resolve/close → writes the resolution back onto the matching
record. **Stays registered regardless of the legacy flag.**

---

## Internal KB agents ✅ (staff consoles — not customer-facing)
`/api/agent/support/*` and `/api/agent/test/*` — the support and test agents over the *internal*
KB. Separate from the customer chatbot; **not** affected by the legacy flag.

## Admin / KB management ✅ (locked — always `_auth`)
| Prefix | Purpose |
|---|---|
| `/api/kb/*` | KB entry CRUD, vector sync, document upload, duplicate detection |
| `/api/admin/*` | admin operations |
| `/api/sessions/*` | session end / termination checks |
| `/api/users/*` | user management |

These are the **admin frontend's** endpoints — **unaffected by the chatbot migration.** The KB
management side doesn't "switch to new endpoints"; only the admin *dashboard/analytics* will later
re-point to `chatbot_interactions` (see the gotcha above).
