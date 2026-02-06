# PropEngine Backend Code Audit

**Date:** 2026-02-06
**Auditor:** Claude Code
**Scope:** Security, Error Handling, Performance, API Design

---

## Executive Summary

Found **37 issues** across 5 categories. This document prioritizes the findings by risk level and provides actionable fixes.

| Category | Critical | High | Medium |
|----------|----------|------|--------|
| Security | 6 | 4 | 2 |
| Error Handling | 3 | 2 | 1 |
| Performance | 1 | 3 | 2 |
| API Design | 4 | 2 | 1 |
| Code Quality | 4 | 0 | 2 |

---

## Critical Issues (Fix Immediately)

### 1. Admin Endpoints Have No Authentication

**Risk Level:** CRITICAL
**File:** `src/api/admin_routes.py`
**Lines:** 240-378

**Problem:** Anyone who knows the URL can call admin endpoints - no API key, no login check.

```python
# Current code - NO authentication
@router.post("/redis/flush")
async def flush_redis(pattern: Optional[str] = None):
    redis_client.flushdb()  # Anyone can delete all data!
```

**Attack scenario:**
```bash
curl -X POST "https://your-backend.run.app/api/admin/redis/flush"
# Result: All Redis data deleted
```

**Fix:** Add API key dependency to admin routes.

```python
from fastapi import Depends, HTTPException, Header

async def require_admin_key(x_admin_key: str = Header(...)):
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")

@router.post("/redis/flush")
async def flush_redis(pattern: Optional[str] = None, _=Depends(require_admin_key)):
    # Now protected
```

**Status:** NOT FIXED

---

### 2. Rate Limits Set to Development Mode

**Risk Level:** CRITICAL
**File:** `src/config/rate_limits.py`
**Line:** 103

**Problem:** Production is using DEV_LIMITS which allows 10,000 requests/day instead of 100.

```python
# Current - WRONG
ACTIVE_LIMITS = DEV_LIMITS  # 10,000 requests/day

# Should be
ACTIVE_LIMITS = RATE_LIMITS  # 100 requests/day
```

**Impact:**
- No effective rate limiting
- API abuse possible
- Cost overruns from excessive LLM calls

**Fix:** Change line 103 to use production limits.

**Status:** NOT FIXED

---

### 3. Error Messages Expose Internal Details

**Risk Level:** HIGH
**Files:** Multiple (30+ locations)

**Problem:** Exception messages are returned directly to clients.

```python
# Current - VULNERABLE
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
    # Could return: "Connection refused to redis:6379"
    # Or: "Invalid API key for OpenAI"
```

**Fix:** Return generic error messages, log details internally.

```python
except Exception as e:
    logger.error(f"Internal error: {e}")
    raise HTTPException(status_code=500, detail="An internal error occurred")
```

**Affected files:**
- `src/api/support_agent_routes.py:154`
- `src/api/test_agent_routes.py:162`
- `src/api/feedback_routes.py:111,129,148`
- `src/api/kb_routes.py:123,159,217,266,312,358,463,538`
- `src/api/admin_routes.py:235,341,378`

**Status:** NOT FIXED

---

### 4. Rate Limiter Silently Bypassed When Redis Down

**Risk Level:** HIGH
**File:** `src/utils/rate_limiter.py`
**Lines:** 47-49

**Problem:** If Redis is unavailable, rate limiting is disabled without alerting.

```python
# Current behavior
def check_rate_limit(self, identifier: str, endpoint_type: str) -> bool:
    if not self.redis:
        logger.warning("Redis unavailable, rate limiting bypassed")
        return True  # ALL requests allowed!
```

**Impact:** Redis outage = unlimited API access

**Fix:** Fail closed (deny) instead of fail open (allow).

```python
def check_rate_limit(self, identifier: str, endpoint_type: str) -> bool:
    if not self.redis:
        logger.error("CRITICAL: Redis unavailable, denying requests")
        return False  # Deny when Redis down
```

**Status:** NOT FIXED

---

### 5. CORS Allows Wildcard Headers with Credentials

**Risk Level:** HIGH
**File:** `main.py`
**Lines:** 101-107

**Problem:** `allow_headers=["*"]` with `allow_credentials=True` is a known security misconfiguration.

```python
# Current - VULNERABLE
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],      # Too permissive
    allow_headers=["*"],      # Too permissive with credentials
)
```

**Fix:**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
)
```

**Status:** NOT FIXED

---

## High Priority Issues (This Week)

### 6. No File Size Validation on Upload

**File:** `src/api/kb_routes.py`
**Risk:** Memory exhaustion via large file uploads

**Current:** No `max_size` parameter on file upload endpoint.

---

### 7. No File Type Validation (Magic Bytes)

**File:** `src/api/kb_routes.py:627`
**Risk:** Malicious files with fake extensions

**Current:** Only checks file extension, not actual content type.

---

### 8. Debug Metrics Exposed to All Users

**File:** `src/api/test_agent_routes.py:54`
**Risk:** Cost/token data visible to non-admin users

---

### 9. No Message Length Limits

**File:** `src/api/support_agent_routes.py`
**Risk:** DOS via oversized request bodies

---

### 10. Blocking Redis Calls in Async Code

**File:** `src/utils/rate_limiter.py:58-84`
**Risk:** Performance degradation under load

**Problem:** Synchronous Redis calls block the async event loop.

```python
# Current - BLOCKING
def check_rate_limit(self, identifier: str, endpoint_type: str) -> bool:
    current_count = self.redis.get(redis_key)  # Blocks event loop
```

**Fix:** Use `asyncio.to_thread()` or async Redis client.

---

## Medium Priority Issues (This Sprint)

### 11. Inconsistent Response Schemas

Different agents return different response structures, making frontend code complex.

### 12. No API Versioning

No `/v1/`, `/v2/` prefixes. Breaking changes affect all clients immediately.

### 13. Duplicate Rate Limiting Code

Same rate limit check copy-pasted in 4 route files. Should use FastAPI dependency.

### 14. Magic Strings Instead of Enums

Hard-coded strings like `"rate_limit:*"`, `"how_to"` scattered throughout codebase.

---

## Architecture Notes

### Rate Limiting Structure (Current)

The rate limiting is well-structured:

```
src/config/rate_limits.py     <- Configuration (limits, windows, presets)
src/utils/rate_limiter.py     <- Logic (Redis checks, enforcement)
src/api/*_routes.py           <- Usage (calls check_rate_limit)
```

**Only change needed:** Line 103 in `rate_limits.py`:
```python
# Change from:
ACTIVE_LIMITS = DEV_LIMITS

# To:
ACTIVE_LIMITS = RATE_LIMITS
```

---

## Recommended Fix Order

### Phase 1: Quick Security Fixes (Today)
1. Change `ACTIVE_LIMITS = RATE_LIMITS` in rate_limits.py
2. Add CORS specific methods/headers in main.py
3. Add `ADMIN_API_KEY` to settings and protect admin routes

### Phase 2: Error Handling (This Week)
4. Create generic error response helper
5. Replace `str(e)` with generic messages in all routes
6. Make rate limiter fail closed

### Phase 3: Input Validation (This Week)
7. Add file size limits to upload endpoint
8. Add message length limits to agent requests
9. Add magic bytes validation for file uploads

### Phase 4: Performance (This Sprint)
10. Convert blocking Redis calls to async
11. Centralize rate limiting with FastAPI dependency

---

## Files Changed in This Session

| File | Change |
|------|--------|
| `src/memory/redis_message_store.py` | Use shared Redis connection |
| `src/api/admin_routes.py` | Added Redis admin endpoints |
| `src/services/freshdesk_service.py` | Added responder_id support |
| `src/agent/orchestrator.py` | Fixed escalation logic |
| `src/api/agent_failure_routes.py` | Fixed email fallback |

---

## Environment Secrets Updated

| Secret | Status |
|--------|--------|
| `FRESHDESK_API_KEY` | Updated |
| `FRESHDESK_RESPONDER_ID` | Added (203007581872) |

---

## Next Steps

1. Review this document with team
2. Prioritize fixes based on risk tolerance
3. Create tickets for each fix
4. Deploy with `ACTIVE_LIMITS = RATE_LIMITS` first
