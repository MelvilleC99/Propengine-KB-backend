"""Test Agent API Route - For debugging and diagnostics"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager
from src.database.astra_client import AstraDBConnection
from src.utils.rate_limiter import check_rate_limit

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


class TestAgentResponse(BaseModel):
    """Test agent response model - includes ALL debug information"""
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID for conversation continuity")
    confidence: float = Field(..., description="Confidence score of the response")
    sources: List[Dict] = Field(default_factory=list, description="Sources used for response")
    query_type: Optional[str] = Field(None, description="Detected query type")
    timestamp: str = Field(..., description="Response timestamp")
    requires_escalation: bool = Field(False, description="Whether the query requires escalation to human agent")
    
    # Debug fields (test agent shows EVERYTHING)
    classification_confidence: Optional[float] = Field(None, description="Pattern matching confidence")
    search_attempts: Optional[List[str]] = Field(default_factory=list, description="Search attempts made")
    
    # Query analytics fields
    enhanced_query: Optional[str] = Field(None, description="LLM-enhanced query")
    query_metadata: Optional[Dict] = Field(None, description="Query category, intent, and tags")
    
    # Full debug metrics (Dict works fine - Pydantic used internally)
    debug_metrics: Optional[Dict] = Field(None, description="Complete query execution metrics")


@router.post("/", response_model=TestAgentResponse)
async def test_agent(request: TestAgentRequest, http_request: Request):
    """
    Test Agent Endpoint - For debugging and diagnostics
    
    Features:
    - NO metadata filtering (sees ALL entries - internal + external)
    - Shows ALL debug information
    - Displays confidence scores
    - Shows all sources with complete metadata
    - Rate limiting: 100 queries/day (same as others for testing)
    """
    try:
        # ============ RATE LIMITING ============
        # Test agent also has rate limiting to prevent abuse
        check_rate_limit(
            request=http_request,
            endpoint_type="query",
            agent_id=request.user_info.get("agent_id"),
            user_email=request.user_info.get("email")
        )
        # =======================================
        
        logger.info(f"🧪 Test Agent - Processing query: {request.message[:50]}...")
        
        # Get or create session
        if request.session_id:
            session = session_manager.get_session(request.session_id)
            if not session:
                session_id = session_manager.create_session(request.user_info)
            else:
                session_id = request.session_id
        else:
            session_id = session_manager.create_session(request.user_info)
        
        # Process query with NO filtering (test agent sees everything)
        result = await agent.process_query(
            query=request.message,
            session_id=session_id,
            user_info=request.user_info,
            user_type_filter=None  # ← NO FILTER - sees all entries
        )
        
        # Log ALL interactions for test agent (helps with debugging)
        await session_manager.add_message(
            session_id=session_id,
            role="user",
            content=request.message,
            metadata={
                "confidence": result.get("confidence", 0.0),
                "requires_escalation": result.get("requires_escalation", False),
                "timestamp": datetime.now().isoformat(),
                "agent_type": "test"
            }
        )
        
        await session_manager.add_message(
            session_id=session_id,
            role="assistant",
            content=result["response"],
            metadata={
                "confidence": result.get("confidence", 0.0),
                "query_type": result.get("query_type"),
                "sources_count": len(result.get("sources", [])),
                "requires_escalation": result.get("requires_escalation", False),
                "timestamp": datetime.now().isoformat(),
                "agent_type": "test"
            }
        )
        
        # Update session metadata if search was performed
        if "search_type" in result:
            search_info = {
                "query_type": result.get("query_type"),
                "search_type": result.get("search_type"),
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"Search performed: {search_info}")
            session_manager.update_metadata(session_id, "searches_performed", [search_info])
        
        logger.info(f"✅ Test Agent - Response generated with {len(result.get('sources', []))} sources")
        
        return TestAgentResponse(
            response=result["response"],
            session_id=session_id,
            confidence=result.get("confidence", 0.0),
            sources=result.get("sources", []),  # ← Full sources with all metadata
            query_type=result.get("query_type"),
            timestamp=datetime.now().isoformat(),
            requires_escalation=result.get("requires_escalation", False),
            classification_confidence=result.get("classification_confidence"),
            search_attempts=result.get("search_attempts", []),
            # Query analytics
            enhanced_query=result.get("enhanced_query"),
            query_metadata=result.get("query_metadata"),
            # Full debug metrics
            debug_metrics=result.get("debug_metrics")
        )
        
    except HTTPException:
        # Re-raise HTTPException (including rate limit 429) without modification
        raise
    except Exception as e:
        logger.error(f"❌ Test Agent error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": type(e).__name__}
        )


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
            "error": str(e),
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
