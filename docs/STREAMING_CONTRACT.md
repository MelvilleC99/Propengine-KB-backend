# Agent Streaming Contract (Frontend ↔ Backend)

> **Last updated:** 2026-06-02
> **Audience:** the frontend developer implementing live-streamed agent responses.
> **Status:** backend implemented & component-tested. Old non-streaming endpoints are
> unchanged, so you can migrate incrementally.

---

## 1. What's changing & why

Today the frontend does `const data = await response.json()` and gets the whole reply at
once — the user stares at a spinner for 8–12s. The new streaming endpoints push the answer
**as it's generated** (first words in ~1–2s once retrieval is warm), plus the same
structured metadata (sources, confidence, escalation, debug) you already use.

The reply is **not** just text — it carries `response`, `sources`, `classification_confidence`,
`requires_escalation`, `debug_metrics`, `context_debug`. So streaming = **stream the text,
then deliver all that metadata at the end.** That shapes the whole contract.

---

## 2. Endpoints

```
POST /api/agent/customer/stream     (external KB only)
POST /api/agent/support/stream      (internal KB only)
POST /api/agent/test/stream         (no filter, full debug)
```

- **Request body is identical** to the existing endpoints:
  ```json
  { "message": "how do I archive a listing", "session_id": "abc123|null", "user_info": { "agent_id": "...", "email": "..." } }
  ```
- **Header:** `Content-Type: application/json`. (Use `fetch`, NOT `EventSource` — EventSource can't POST a body.)
- The **old** `POST /api/agent/{type}/` JSON endpoints still exist and are unchanged.

---

## 3. Response format — NDJSON (one JSON object per line)

`Content-Type: application/x-ndjson`. Read the body as a stream and parse **each line** as
JSON. Frames arrive in this **fixed order**:

```jsonc
{"type":"session","session_id":"abc123"}                       // 1. FIRST — capture session_id
{"type":"sources","sources":[ { ...source... } ]}              // 2. after retrieval, before text
{"type":"token","text":"To "}                                  // 3. many of these — append live
{"type":"token","text":"archive "}
{"type":"token","text":"a listing..."}
{"type":"metadata", "confidence":1.0, "requires_escalation":false,
   "query_type":"how_to", "classification_confidence":0.9,
   "enhanced_query":"...", "query_metadata":{...},
   "debug_metrics":{...}, "context_debug":{...}}                // 4. LAST data — final timing/cost/escalation
{"type":"done"}                                                // 5. terminal sentinel
```

On failure you may instead receive (then the stream ends):
```jsonc
{"type":"error","message":"I apologize, but I encountered an error. Please try again."}
```

### Where your existing fields now come from
| Old field (from `data.*`) | New source |
|---|---|
| `data.response` | **accumulate** all `token` frames' `text` |
| `data.session_id` | `session` frame's `session_id` |
| `data.sources` | `sources` frame's `sources` |
| `data.confidence` | `metadata.confidence` |
| `data.requires_escalation` | `metadata.requires_escalation` |
| `data.classification_confidence` | `metadata.classification_confidence` |
| `data.debug_metrics` | `metadata.debug_metrics` |
| `data.context_debug` | `metadata.context_debug` |

> **Important:** `metadata` arrives **after** all tokens (final timing/cost/escalation aren't
> known until generation finishes). So render the text live, then fill in
> sources/confidence/escalation/debug when `metadata` lands.

---

## 4. Reference reader (TypeScript — adapt into `useChat.ts`'s `sendMessage`)

```ts
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

type AgentType = "customer" | "support" | "test";

export async function sendMessageStreaming(
  message: string,
  sessionId: string | null,
  userInfo: Record<string, any>,
  agentType: AgentType,
  cb: {
    onSession?: (sessionId: string) => void;
    onSources?: (sources: any[]) => void;
    onToken?: (text: string) => void;     // append to the visible answer
    onMetadata?: (meta: any) => void;     // confidence, requires_escalation, debug_metrics, context_debug, ...
    onDone?: () => void;
    onError?: (message: string) => void;
  }
) {
  const res = await fetch(`${BACKEND_URL}/api/agent/${agentType}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, user_info: userInfo }),
  });

  // 429 / other errors arrive BEFORE the stream opens — handle as a normal HTTP response
  // (your existing rate-limit handling for status 429 still applies here).
  if (!res.ok || !res.body) {
    if (res.status === 429) { /* existing rate-limit UX */ }
    cb.onError?.(`Request failed: ${res.status}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // NDJSON: split on newlines; keep the trailing partial line in the buffer
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.trim()) continue;
      let frame: any;
      try { frame = JSON.parse(line); } catch { continue; }
      switch (frame.type) {
        case "session":  cb.onSession?.(frame.session_id); break;
        case "sources":  cb.onSources?.(frame.sources); break;
        case "token":    cb.onToken?.(frame.text); break;
        case "metadata": cb.onMetadata?.(frame); break;
        case "done":     cb.onDone?.(); return;
        case "error":    cb.onError?.(frame.message); return;
      }
    }
  }
}
```

### Wiring into the UI (sketch)
```ts
let answer = "";
await sendMessageStreaming(text, sessionId, userInfo, "support", {
  onSession: (sid) => setSessionId(sid),
  onSources: (s) => setSources(s),
  onToken: (t) => { answer += t; updateAssistantMessageText(answer); },  // re-render live
  onMetadata: (m) => {
    setConfidence(m.confidence);
    setRequiresEscalation(m.requires_escalation);
    setDebugMetrics(m.debug_metrics);     // test agent's debug panel
    setContextDebug(m.context_debug);
  },
  onError: (msg) => showError(msg),
});
```

---

## 5. Gotchas / must-handle
1. **Buffer partial lines.** A TCP chunk can split a JSON line in half — always keep the last
   partial line in a buffer (the reader above does this). Don't `JSON.parse` a half line.
2. **The answer may arrive as one `token` frame or many.** Short/cached responses can come as a
   single chunk; long ones stream incrementally. Your `onToken` (append) handles both.
3. **`metadata` is last.** Don't expect confidence/escalation/debug until after the tokens.
4. **Errors are in-band once streaming starts.** Once you're reading the body, an error is an
   `{"type":"error"}` frame, not an HTTP status. Only pre-stream failures (incl. **429**) are HTTP statuses.
5. **No client config needed for proxy buffering** — the backend already sends
   `X-Accel-Buffering: no`. Just read the stream.

---

## 6. Backend specifics (FYI — no action needed)
- Transport: NDJSON over a chunked `fetch` POST response (keeps your POST body).
- Headers set by backend: `X-Accel-Buffering: no`, `Cache-Control: no-cache`.
- Same pipeline as the non-stream endpoint; only the final answer is streamed.
- TTFT depends on retrieval speed (embedding + search) finishing first — backend is
  separately optimizing that (warmup), so first-token latency will improve over time.
