"""
PropEngine Support Agent - Main Application Entry Point
Clean, modular FastAPI backend with intelligent query routing
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from src.config.settings import settings
from src.api import chat_routes, admin_routes
from src.database.connection import AstraDBConnection

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
    
    yield
    
    # Shutdown
    logger.info("Shutting down PropEngine Support Agent...")

# Create FastAPI app with lifespan
app = FastAPI(
    title="PropEngine Support Agent",
    description="AI-powered support agent with AstraDB vector search",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(chat_routes.router, prefix="/api/chat", tags=["chat"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["admin"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "PropEngine Support Agent",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "chat": "/api/chat/",
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
