"""Customer Agent API Route - For external customers"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager
from src.utils.rate_limiter import check_rate_limit
from src.api.streaming_utils import ndjson_stream, STREAM_HEADERS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/customer", tags=["customer-agent"])

# Initialize global instances
agent = Agent()
session_manager = SessionManager()


class CustomerAgentRequest(BaseModel):
    """Customer agent request model"""
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_info: Optional[Dict] = Field(default_factory=dict, description="Optional user information")


@router.post("/stream")
async def customer_agent_stream(request: CustomerAgentRequest, http_request: Request):
    """
    Streaming Customer Agent — same pipeline as POST /, streamed as NDJSON frames
    (session → sources → token* → metadata → done). External entries only.
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
        user_info=request.user_info, user_type_filter="external",
    )
    return StreamingResponse(ndjson_stream(gen), media_type="application/x-ndjson", headers=STREAM_HEADERS)


@router.get("/health")
async def customer_agent_health():
    """Health check for customer agent"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agent": "customer",
            "sessions": len(session_manager.memory_sessions)
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": "Health check failed",
            "timestamp": datetime.now().isoformat()
        }
