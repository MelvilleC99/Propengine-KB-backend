"""
PropEngine Support Agent - Main Application Entry Point
Clean, modular FastAPI backend with intelligent query routing
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from src.config.settings import settings
from src.api import admin_routes, kb_routes, session_endpoints, user_routes
from src.api import test_agent_routes, support_agent_routes, customer_agent_routes
from src.api import feedback_routes, agent_failure_routes, health_routes
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_routes.router, tags=["health"])  # Health check endpoints
app.include_router(test_agent_routes.router, tags=["test-agent"])
app.include_router(support_agent_routes.router, tags=["support-agent"])
app.include_router(customer_agent_routes.router, tags=["customer-agent"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["admin"])
app.include_router(kb_routes.router, tags=["kb"])
app.include_router(feedback_routes.router, tags=["feedback"])
app.include_router(agent_failure_routes.router, tags=["agent-failure"])
app.include_router(session_endpoints.router, prefix="/api", tags=["sessions"])
app.include_router(user_routes.router, tags=["users"])  # User management endpoints

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
            "health": "/api/chat/health",
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
