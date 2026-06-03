# Known Limitations & Roadmap

> An honest, current list of what's incomplete or constrained, with the plan for each.
> Kept deliberately frank — if it's a known gap, it's written down here rather than hidden.

---

## Streaming buffers when the response contains PII
**Status: external (proxy behaviour), by design.** The company proxy masks PII on the way to the
model and **de-anonymises it on the way back**. To un-mask, it must collect the *entire* completion,
swap the entities back, then re-emit it as a **single SSE burst** — so any answer containing customer
PII (names, ID numbers, emails, cell numbers) arrives all-at-once after the full generation time
instead of token-by-token. `PII_MASKING_ENABLED=true` globally in prod.
- **Root cause (proven by the platform team, with proxy source + reproduction):** it's the
  **content**, not the client. A benign prompt streams normally through *both* raw httpx and the
  OpenAI SDK; a PII-laden prompt buffers even with a raw client.
- **Not the SDK, not gzip.** An earlier in-house guess (OpenAI-SDK-vs-httpx) was a red herring — the
  isolated httpx test happened to use a PII-free prompt, so it streamed.
- **Our code needs no change.** The streaming pipeline already streams when the proxy streams and
  degrades to one burst when it de-anonymises. (A raw-httpx bridge would *not* help — the trigger is
  content, not transport.)
- **Real fix (platform team):** incremental de-anonymisation (un-mask per-chunk) so PII responses can
  stream. Until then, PII answers arrive as one burst — show a "working…" indicator. **Keep PII
  masking ON;** disabling it to force streaming would send customer PII to the model un-masked.

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

## Rate limits are shared across agents
**Status: works, tune before scale.** Limits are env-driven (`RATE_LIMIT_TIER`) and enforced per
user (`email`/`agent_id`). The default production tier (query 10/day) is **shared across all three
agents** — likely too low for active support staff.
- **Plan:** separate per-agent (or per-role) limits; staff get a higher tier than the public.

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
