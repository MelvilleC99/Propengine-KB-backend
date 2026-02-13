"""
System Health Check Routes

Provides real-time status of all system components for monitoring dashboard.
"""

from fastapi import APIRouter, Response
from typing import Dict, Any
import time
import asyncio
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


async def check_redis() -> Dict[str, Any]:
    """Check Redis connection and response time"""
    try:
        from src.memory.redis_message_store import RedisContextCache
        
        start = time.time()
        cache = RedisContextCache()
        
        if cache.redis_client:
            cache.redis_client.ping()
            response_time = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "message": "Connected",
                "response_time_ms": round(response_time, 2)
            }
        else:
            return {
                "status": "degraded",
                "message": "Using in-memory fallback",
                "response_time_ms": 0
            }
    except Exception as e:
        return {
            "status": "down",
            "message": f"Connection failed: {str(e)}",
            "response_time_ms": None
        }


async def check_firebase() -> Dict[str, Any]:
    """Check Firebase connection"""
    try:
        from src.database.firebase_client import get_firestore_client
        
        start = time.time()
        db = get_firestore_client()
        
        if db:
            # Quick test query
            db.collection("kb_sessions").limit(1).get()
            response_time = (time.time() - start) * 1000
            
            return {
                "status": "healthy",
                "message": "Connected",
                "response_time_ms": round(response_time, 2)
            }
        else:
            return {
                "status": "down",
                "message": "Firestore client not initialized",
                "response_time_ms": None
            }
    except Exception as e:
        return {
            "status": "down",
            "message": f"Connection failed: {str(e)}",
            "response_time_ms": None
        }


async def check_astra() -> Dict[str, Any]:
    """Check AstraDB vector database connection with a real query"""
    try:
        from src.database.astra_client import astra_client

        start = time.time()

        if not astra_client.is_connected():
            return {
                "status": "down",
                "message": "Vector store not initialized",
                "response_time_ms": None
            }

        # Actually query the collection to verify the connection is live
        collection = astra_client._vector_store.astra_env.collection
        collection.find_one({}, projection={"_id": 1})
        response_time = (time.time() - start) * 1000

        return {
            "status": "healthy",
            "message": "Vector store connected",
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        return {
            "status": "down",
            "message": f"Connection failed: {str(e)[:100]}",
            "response_time_ms": None
        }


async def check_openai_chat() -> Dict[str, Any]:
    """Check OpenAI chat completions endpoint"""
    try:
        from langchain_openai import ChatOpenAI
        from langchain.schema import HumanMessage
        from src.config.settings import settings
        
        start = time.time()
        
        llm = ChatOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_MODEL,
            timeout=10,
            max_tokens=5
        )
        
        # Quick test with minimal tokens
        response = await llm.ainvoke([HumanMessage(content="test")])
        response_time = (time.time() - start) * 1000
        
        return {
            "status": "healthy",
            "message": "Chat completions working",
            "model": settings.OPENAI_MODEL,
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        return {
            "status": "down",
            "message": f"Chat endpoint failed: {str(e)}",
            "model": settings.OPENAI_MODEL if 'settings' in locals() else "unknown",
            "response_time_ms": None
        }


async def check_openai_embeddings() -> Dict[str, Any]:
    """Check OpenAI embeddings endpoint using the app's actual embeddings instance"""
    try:
        from src.database.astra_client import astra_client
        from src.config.settings import settings

        start = time.time()

        # Use the same embeddings instance the app uses (not a throwaway)
        embeddings = astra_client.get_embeddings()
        result = await embeddings.aembed_query("test")
        response_time = (time.time() - start) * 1000

        return {
            "status": "healthy",
            "message": "Embeddings working",
            "model": settings.EMBEDDING_MODEL,
            "dimensions": len(result),
            "response_time_ms": round(response_time, 2)
        }
    except Exception as e:
        from src.config.settings import settings as _settings
        error_msg = str(e)
        if "404" in error_msg or "DeploymentNotFound" in error_msg:
            message = f"Deployment not found for model: {_settings.EMBEDDING_MODEL}"
        elif "timeout" in error_msg.lower():
            message = "Embeddings endpoint timeout"
        elif "500" in error_msg:
            message = f"Embeddings API returned 500 (proxy or OpenAI issue)"
        else:
            message = f"Embeddings failed: {error_msg[:100]}"

        return {
            "status": "down",
            "message": message,
            "model": _settings.EMBEDDING_MODEL,
            "dimensions": None,
            "response_time_ms": None
        }


@router.get("/")
async def get_system_health() -> Dict[str, Any]:
    """
    Get comprehensive system health status
    
    Returns:
        {
            "timestamp": 1234567890,
            "overall_status": "healthy" | "degraded" | "down",
            "services": {
                "redis": {...},
                "firebase": {...},
                "astra": {...},
                "openai_chat": {...},
                "openai_embeddings": {...}
            }
        }
    """
    
    logger.info("Health check requested")
    
    # Run all health checks concurrently
    redis_check, firebase_check, astra_check, chat_check, embeddings_check = await asyncio.gather(
        check_redis(),
        check_firebase(),
        check_astra(),
        check_openai_chat(),
        check_openai_embeddings(),
        return_exceptions=True
    )
    
    # Handle any exceptions from checks
    def safe_result(check, name):
        if isinstance(check, Exception):
            return {
                "status": "down",
                "message": f"Health check failed: {str(check)}",
                "response_time_ms": None
            }
        return check
    
    services = {
        "redis": safe_result(redis_check, "redis"),
        "firebase": safe_result(firebase_check, "firebase"),
        "astra": safe_result(astra_check, "astra"),
        "openai_chat": safe_result(chat_check, "openai_chat"),
        "openai_embeddings": safe_result(embeddings_check, "openai_embeddings")
    }
    
    # Calculate overall status
    service_statuses = [s["status"] for s in services.values()]
    
    if all(s == "healthy" for s in service_statuses):
        overall_status = "healthy"
    elif all(s == "down" for s in service_statuses):
        overall_status = "down"
    else:
        overall_status = "degraded"
    
    # Count services by status
    healthy_count = sum(1 for s in service_statuses if s == "healthy")
    degraded_count = sum(1 for s in service_statuses if s == "degraded")
    down_count = sum(1 for s in service_statuses if s == "down")
    
    health = {
        "timestamp": int(time.time()),
        "overall_status": overall_status,
        "services": services,
        "summary": {
            "total": len(services),
            "healthy": healthy_count,
            "degraded": degraded_count,
            "down": down_count
        }
    }
    
    logger.info(f"Health check complete: {overall_status} ({healthy_count}/{len(services)} healthy)")
    
    return health


@router.get("/ping")
async def ping() -> Dict[str, str]:
    """
    Simple ping endpoint for basic uptime monitoring
    
    Returns:
        {"status": "ok", "timestamp": 1234567890}
    """
    return {
        "status": "ok",
        "timestamp": int(time.time())
    }
