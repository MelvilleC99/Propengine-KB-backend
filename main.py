"""
PropEngine Support Agent - Main Application Entry Point
Clean, modular FastAPI backend with intelligent query routing
"""

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
from contextlib import asynccontextmanager
from src.config.settings import settings
from src.api import admin_routes, kb_routes, session_endpoints, user_routes
from src.api import test_agent_routes, support_agent_routes, customer_agent_routes
from src.api import feedback_routes, agent_failure_routes, health_routes
from src.api.auth import verify_user
from src.database.astra_client import AstraDBConnection
from src.database.firebase_client import initialize_firebase, test_firebase_connection

# Configure logging with more detailed format
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info("=" * 60)
    logger.info("Starting PropEngine Support Agent...")
    logger.info(f"Environment: {'Development' if settings.DEBUG else 'Production'}")
    logger.info("=" * 60)
    
    # Initialize Firebase
    try:
        initialize_firebase()
        firebase_ok = await test_firebase_connection()
        if firebase_ok:
            logger.info("✅ Firebase Admin SDK connected successfully")
        else:
            logger.warning("⚠️ Firebase connection test failed")
    except Exception as e:
        logger.error(f"❌ Firebase initialization failed: {e}")
    
    # Test AstraDB connection
    try:
        db = AstraDBConnection()
        connection_results = await db.test_connection()
        
        # Log connection results
        all_connected = all(connection_results.values())
        if all_connected:
            logger.info("✅ All AstraDB collections connected successfully")
        else:
            logger.warning("⚠️ Some collections failed to connect:")
            for collection, status in connection_results.items():
                symbol = "✓" if status else "✗"
                logger.info(f"  {symbol} {collection}: {'connected' if status else 'failed'}")
    except Exception as e:
        logger.error(f"❌ AstraDB connection failed: {e}")

    # Clear stale rate limit keys on startup (prevents 429s from old counters)
    try:
        from src.database.redis_client import get_redis_client
        rc = get_redis_client()
        stale_keys = rc.keys("rate_limit:*")
        if stale_keys:
            rc.delete(*stale_keys)
            logger.info(f"✅ Cleared {len(stale_keys)} stale rate limit keys from Redis")
    except Exception as e:
        logger.debug(f"Redis rate limit cleanup skipped: {e}")

    yield

    # Shutdown — close Redis connections so they don't leak on hot-reload
    logger.info("Shutting down PropEngine Support Agent...")
    try:
        from src.database.redis_client import redis_connection
        redis_connection.close()
        logger.info("✅ Redis connection closed on shutdown")
    except Exception as e:
        logger.debug(f"Redis cleanup: {e}")

# Create FastAPI app with lifespan
app = FastAPI(
    title="PropEngine Support Agent",
    description="AI-powered support agent with AstraDB vector search",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS - Allow both local and production frontends
ALLOWED_ORIGINS = [
    "http://localhost:3000",  # Next.js dev server
    "http://localhost:3001",  # Alternative local port
    "http://localhost:5173",  # Vite dev server (default port)
    "http://127.0.0.1:5173",  # Vite alternative localhost
    "https://knowledge-base-agent-55afc.web.app",  # Firebase Hosting
    "https://knowledge-base-agent-55afc.firebaseapp.com",  # Firebase alternative domain
]
# Extra origins (e.g. the demo/DEV UI on another domain) added via env, comma-separated.
ALLOWED_ORIGINS += [o.strip() for o in settings.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

# CORS_ALLOWED_ORIGINS="*" → allow ALL origins (DEV/demo). Browsers forbid literal "*" together
# with credentials, so we reflect any origin via a match-all regex — functionally "allow all"
# while keeping the Authorization header working. Otherwise, use the explicit allow-list.
if "*" in ALLOWED_ORIGINS:
    _cors_origin_kwargs = {"allow_origin_regex": ".*"}
else:
    _cors_origin_kwargs = {"allow_origins": ALLOWED_ORIGINS}

app.add_middleware(
    CORSMiddleware,
    **_cors_origin_kwargs,
    allow_credentials=True,
    # Least privilege: only the methods/headers the app actually uses.
    # If the frontend sends another custom header, add it here (symptom: a
    # CORS error in the browser console naming the blocked header).
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Global error handling — defines, in one place, how this app turns errors into responses.
# Goal: never leak internal error detail to clients in production; keep full detail for us in logs.

@app.exception_handler(StarletteHTTPException)
async def safe_http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Server errors (5xx): log the real detail privately, return a generic message in production.
    if exc.status_code >= 500:
        logger.error(f"{exc.status_code} on {request.method} {request.url.path}: {exc.detail}")
        if not settings.DEBUG:
            return JSONResponse(status_code=exc.status_code, content={"detail": "Internal server error"})
    # Client errors (404, 409, etc.) and local DEBUG mode: keep FastAPI's normal, safe behavior.
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # A truly unexpected error that no route caught — log the full traceback, return a generic message.
    logger.error(f"Unhandled error on {request.method} {request.url.path}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

# ============================================================================
# ROUTERS — grouped by purpose. Full map: docs/ENDPOINTS.md
# Auth: protected routers take `_auth` (Firebase token, enforced when REQUIRE_AUTH=true).
# The customer chatbot uses `_customer_auth` (open while CUSTOMER_AGENT_PUBLIC=true, else gated).
# ============================================================================
_auth = [Depends(verify_user)]
_customer_auth = [] if settings.CUSTOMER_AGENT_PUBLIC else _auth

# --- Public (no auth) -------------------------------------------------------
app.include_router(health_routes.router, tags=["health"])

# --- Customer chatbot — NEW interaction-centric API (/api/chatbot/*) ---------
# THE current chatbot surface: one durable interaction record per turn.
# Wrapped so a failure here can never stop the app booting (worst case it just
# doesn't register and the rest keeps serving).
try:
    from src.api import chatbot
    app.include_router(chatbot.router, dependencies=_customer_auth)
    logger.info("✅ Chatbot API registered (/api/chatbot/*)")
except Exception as e:
    logger.error(f"⚠️ Chatbot API NOT registered (app still running): {e}", exc_info=True)

# --- Customer chatbot — LEGACY endpoints (DEPRECATED, being retired) ---------
# Old chat (/api/agent/customer/stream), /api/feedback, /api/agent-failure — superseded by
# /api/chatbot/*. Registered ONLY while ENABLE_LEGACY_ENDPOINTS=true (the migration parallel-run).
# Before disabling: feedback_routes/agent_failure_routes ALSO hold the admin GET /stats endpoints,
# so retire these together with the admin-dashboard re-point (see docs/ENDPOINTS.md).
if settings.ENABLE_LEGACY_ENDPOINTS:
    app.include_router(customer_agent_routes.router, tags=["customer-agent (LEGACY)"], dependencies=_customer_auth)
    app.include_router(feedback_routes.router, tags=["feedback (LEGACY)"], dependencies=_customer_auth)
    app.include_router(agent_failure_routes.router, tags=["agent-failure (LEGACY)"], dependencies=_customer_auth)
    logger.info("🔁 Legacy customer endpoints ENABLED (parallel run with /api/chatbot/*)")
else:
    logger.info("⛔ Legacy customer endpoints DISABLED — only /api/chatbot/* serves the chatbot")

# --- Webhooks (machine-to-machine; secured by X-Webhook-Secret, NOT user auth) ---
# Freshdesk ticket-closed webhook. Stays registered regardless of the legacy flag.
app.include_router(agent_failure_routes.webhook_router, tags=["webhooks"])

# --- Internal KB agents (staff consoles — support + test) -------------------
app.include_router(support_agent_routes.router, tags=["support-agent"], dependencies=_auth)
app.include_router(test_agent_routes.router, tags=["test-agent"], dependencies=_auth)

# --- Admin / KB management (LOCKED — always require auth) --------------------
app.include_router(kb_routes.router, tags=["kb"], dependencies=_auth)
app.include_router(admin_routes.router, prefix="/api/admin", tags=["admin"], dependencies=_auth)
app.include_router(session_endpoints.router, prefix="/api", tags=["sessions"], dependencies=_auth)
app.include_router(user_routes.router, tags=["users"], dependencies=_auth)

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "PropEngine Support Agent",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/api/chat/",
            "agents": {
                "test": "/api/agent/test",
                "support": "/api/agent/support",
                "customer": "/api/agent/customer"
            },
            "admin": "/api/admin/stats",
            "health": "/api/health/",
            "docs": "/docs"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )
