"""Test Agent API Route - For debugging and diagnostics"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager
from src.database.astra_client import AstraDBConnection
from src.utils.rate_limiter import check_rate_limit
from src.api.streaming_utils import ndjson_stream, STREAM_HEADERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/test", tags=["test-agent"])

# Initialize global instances
agent = Agent()
session_manager = SessionManager()


class TestAgentRequest(BaseModel):
    """Test agent request model"""
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_info: Optional[Dict] = Field(default_factory=dict, description="Optional user information")


@router.post("/stream")
async def test_agent_stream(request: TestAgentRequest, http_request: Request):
    """
    Streaming Test Agent — same pipeline as POST /, streamed as NDJSON frames
    (session → sources → token* → metadata → done). No audience filter (sees all).
    Rate limit (429) is enforced before the stream opens.
    """
    check_rate_limit(
        request=http_request, endpoint_type="query",
        agent_id=request.user_info.get("agent_id"), user_email=request.user_info.get("email"),
    )
    if request.session_id:
        session = session_manager.get_session(request.session_id)
        session_id = request.session_id if session else session_manager.create_session(request.user_info)
    else:
        session_id = session_manager.create_session(request.user_info)

    gen = agent.process_query_stream(
        query=request.message, session_id=session_id,
        user_info=request.user_info, user_type_filter=None,
    )
    return StreamingResponse(ndjson_stream(gen), media_type="application/x-ndjson", headers=STREAM_HEADERS)


@router.get("/health")
async def test_agent_health():
    """Health check for test agent"""
    try:
        db = AstraDBConnection()
        connection_results = await db.test_connection()
        all_connected = all(connection_results.values())
        
        return {
            "status": "healthy" if all_connected else "degraded",
            "timestamp": datetime.now().isoformat(),
            "agent": "test",
            "services": {
                "database": "connected" if all_connected else "partial",
                "sessions": len(session_manager.memory_sessions),
                "collections": connection_results
            }
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": "Health check failed",
            "timestamp": datetime.now().isoformat()
        }


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """Get session information"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    
    return {
        "session_id": session_id,
        "created_at": session["created_at"].isoformat(),
        "last_activity": session["last_activity"].isoformat(),
        "message_count": len(session["messages"]),
        "metadata": session["metadata"]
    }


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str, limit: int = 10):
    """Get chat history for a session"""
    # Check if session exists first
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    history = session_manager.get_history(session_id, limit)
    return {"session_id": session_id, "history": history, "total_messages": len(session["messages"])}
