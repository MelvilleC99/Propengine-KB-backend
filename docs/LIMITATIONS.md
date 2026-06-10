# Known Limitations & Roadmap

> An honest, current list of what's incomplete or constrained, with the plan for each.
> Kept deliberately frank — if it's a known gap, it's written down here rather than hidden.

---

## Streaming is buffered by the proxy for any non-trivial prompt
**Status: external (proxy), blocking token-by-token streaming.** The company proxy buffers the whole
completion and returns it as a **single SSE event for any prompt longer than ~100 characters** — its
PII de-anonymisation pipeline collects the full response before returning. Since every real RAG prompt
(system prompt + KB context + question) is thousands of characters, **100% of chat answers are
buffered**, so the live "typing" effect isn't possible through the proxy.
- **Proven (clean length test, neutral filler, no PII):** 74-char prompt → **844** SSE deltas streamed;
  142-char prompt → **1** delta (buffered); 210 / 410 / 618 chars → 1 delta each.
- **Control (rules out client/content):** the *same* 547-char prompt sent **direct to a provider**
  (bypassing the proxy) streams fine (8 deltas over 1.7s). So it's the **proxy** — not our client/SDK,
  not the content, not output length.
- **Our code is ready:** `generate_response_stream` yields token-by-token via raw httpx — it will
  stream the instant the proxy stops buffering, and already streams short prompts (greetings).
- **Real fix (platform team):** allow streaming for longer prompts — skip the collect-and-buffer, or
  do incremental de-anonymisation (un-mask per chunk). Reported to the proxy owner with reproduction.
- **Interim:** answers arrive as one chunk after generation — show a "working…" indicator. Going
  direct to a provider would stream but **bypasses PII masking** (a deliberate compliance decision,
  not a default).

## Backend authentication — built, pending rollout
**Status: implemented, dormant until the frontend sends tokens.** A FastAPI dependency
(`src/api/auth.py` `verify_user`) verifies the caller's **Firebase ID token**
(`firebase_admin.auth.verify_id_token`) on every protected router (wired in `main.py`); `/` and
`/api/health/` stay public. Enforcement is controlled by `REQUIRE_AUTH` (**default: on**).
- **Rollout sequence:** the frontend adds `Authorization: Bearer <token>` (see
  [FRONTEND_AUTH.md](FRONTEND_AUTH.md)) → deploy → confirm. ⚠️ With `REQUIRE_AUTH=true`, deploying
  **before** the frontend sends tokens will 401 the live UI; set `REQUIRE_AUTH=false` on the service
  for that window if needed.
- **Still token-only:** any logged-in user passes. Role-gating the destructive endpoints
  (`verify_admin` on the admin-claim) is the next small step before non-staff logins exist.
- The Cloud Run service stays `--allow-unauthenticated` **by design** — a browser frontend can't
  present a Google IAM token, so auth is enforced in-app via the Firebase token instead.
- **⚠️ TESTING/DEMO right now:** `CUSTOMER_AGENT_PUBLIC=true` opens the **customer flow**
  (chat / feedback / escalation — all non-destructive) with **no auth**, so the tokenless demo UI
  can use it. Support/test agents, KB management and admin **stay locked**. Revert to `false` when
  the customer UI sends Firebase tokens.

## Rate limits are shared across agents
**Status: lifted for testing.** Limits are env-driven (`RATE_LIMIT_TIER`) and keyed per user
(`email`/`agent_id`), **falling back to IP when there's no auth** — so a tokenless tester shares one
IP counter and hits the cap fast.
- **⚠️ TESTING/DEMO right now:** `RATE_LIMIT_TIER=dev` (10,000/day ≈ no limit) so the tokenless demo
  isn't blocked. Set back to `production` for real limits.
- The `production` tier (query 10/day) is shared across all three agents and is too low even for real
  customers — **Plan:** separate per-agent/per-role limits and a sensible production number.

## <a id="vector-drift"></a>Vector drift — edits aren't auto-synced
**Status: by design, needs discipline.** Editing a KB entry updates Firebase but does **not**
re-embed it. The entry is stale in search until it's manually re-synced (`/sync`). Silent: search
just quietly returns worse matches.
- **Mitigation today:** re-sync after edits; the dashboard shows `vectorStatus`.
- **Plan:** auto-reset `vectorStatus="pending"` on edit + a "needs re-sync" surface / batch re-sync.

## Latency floor
**Status: inherent.** ~2s to first token even when healthy: embedding (~1.5s, proxy floor) +
search (~0.2s). Response generation (~2.8s) overlaps with reading **once streaming works**.
- **Plan:** streaming (above) hides most of it; caching embeddings for repeat queries later.

## Cost tracking for streamed answers is estimated
Streamed responses don't return token-usage metadata from the proxy, so cost for the streamed
answer is **estimated from text length** (~4 chars/token). Non-streamed calls use exact usage.

## Smaller known gaps
- **`/restore` endpoint** is not implemented though a frontend stub calls it.
- **Orchestrator decomposition debt:** `process_query_stream` is now the sole pipeline, but the
  orchestrator still carries history worth splitting further (noted in-file).
- **Update doesn't auto-reset `vectorStatus`** (intentional — see Vector drift).
