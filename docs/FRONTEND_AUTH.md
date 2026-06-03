# Frontend Auth — Sending the Firebase Token

> **For the frontend developer.** The app already logs users in with Firebase; this just forwards
> the token it already has to the backend on each API call.
>
> **Safe to ship anytime:** the backend ignores this header until auth enforcement is switched on
> (`REQUIRE_AUTH`), so adding it now breaks nothing.

**The rule:** every backend request needs this header:
```
Authorization: Bearer <firebase-id-token>
```

---

## 1. Get the current user's token

```js
import { getAuth } from "firebase/auth";

async function getToken() {
  const user = getAuth().currentUser;
  if (!user) return null;            // not logged in
  return await user.getIdToken();    // auto-refreshes if expired; cached if still valid
}
```

## 2. Do it once — a fetch wrapper

Route all backend calls through one wrapper so the header is added in a single place.

```js
const BASE = import.meta.env.VITE_BACKEND_URL;   // Vite

export async function apiFetch(path, options = {}) {
  const token = await getToken();
  return fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
}
```

Then existing calls become:
```js
// before:  fetch(`${BASE}/api/feedback/`, { method: "POST", body })
// after:   apiFetch("/api/feedback/", { method: "POST", body })
```

## 3. The streaming call needs it too

The chat stream is also a `fetch` — add the same header; streaming is unaffected:
```js
const token = await getToken();
const res = await fetch(`${BASE}/api/agent/customer/stream`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,        // ← add this line
  },
  body: JSON.stringify({ message, session_id, user_info }),
});
// ...existing getReader() / TextDecoder streaming code unchanged
```

---

## Where the changes live
- **Token helper + `apiFetch` wrapper** → the central API/util file (where `VITE_BACKEND_URL` already lives).
- **Header line on the streaming call** → the chat component/service that does `fetch(.../stream)`.
- Typically **2 files**.

## Notes
- **`getIdToken()` handles refresh automatically** — call it before each request; it returns the
  cached token if valid or silently refreshes if expired.
- **On a `401`** from the backend → treat as "session expired" and send the user back to login.
- **`.env` (Vite):** `VITE_BACKEND_URL=https://knowledge-base-backend-577215182671.us-central1.run.app`
