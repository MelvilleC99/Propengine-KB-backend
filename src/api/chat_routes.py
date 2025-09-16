"""Chat API routes for the support agent"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager
from src.database.connection import AstraDBConnection
from src.utils.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize global instances
agent = Agent()
session_manager = SessionManager()

class ChatRequest(BaseModel):
    """Chat request model"""
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_info: Optional[Dict] = Field(default_factory=dict, description="Optional user information")

class ChatResponse(BaseModel):
    """Chat response model"""
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID for conversation continuity")
    confidence: float = Field(..., description="Confidence score of the response")
    sources: List[Dict] = Field(default_factory=list, description="Sources used for response")
    query_type: Optional[str] = Field(None, description="Detected query type")
    timestamp: str = Field(..., description="Response timestamp")
    requires_escalation: bool = Field(False, description="Whether the query requires escalation to human agent")
    # Add debug fields
    classification_confidence: Optional[float] = Field(None, description="Pattern matching confidence for debugging")
    search_attempts: Optional[List[str]] = Field(default_factory=list, description="Search attempts made for debugging")

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request):
    """Main chat endpoint with rate limiting"""
    try:
        # Apply rate limiting
        user_email = request.user_info.get("email") if request.user_info else None
        rate_limit_info = check_rate_limit(http_request, "chat", user_email)
        
        # Get or create session
        if request.session_id:
            session = session_manager.get_session(request.session_id)
            if not session:
                # Session expired or invalid, create new one
                session_id = session_manager.create_session(request.user_info)
            else:
                session_id = request.session_id
        else:
            session_id = session_manager.create_session(request.user_info)
        
        # Process query with agent
        result = await agent.process_query(
            query=request.message,
            session_id=session_id,
            user_info=request.user_info
        )
        
        # Log only essential interactions to Firebase
        # Only log if: escalation, low confidence, or feedback requested
        should_log_detailed = (
            result.get("requires_escalation", False) or
            result.get("confidence", 1.0) < 0.7 or
            "feedback" in request.message.lower()
        )
        
        if should_log_detailed:
            # Log user message for analysis
            session_manager.add_message(
                session_id=session_id,
                role="user", 
                content=request.message,
                metadata={
                    "confidence": result.get("confidence", 0.0),
                    "requires_escalation": result.get("requires_escalation", False),
                    "timestamp": datetime.now().isoformat(),
                    "reason": "low_confidence_or_escalation"
                }
            )
            
            # Log agent response for problematic cases
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=result["response"],
                metadata={
                    "confidence": result.get("confidence", 0.0),
                    "query_type": result.get("query_type"),
                    "sources_count": len(result.get("sources", [])),
                    "requires_escalation": result.get("requires_escalation", False),
                    "timestamp": datetime.now().isoformat()
                }
            )
        else:
            # Just update session activity timestamp for successful queries
            session = session_manager.get_session(session_id)
            # Session get already updates last_activity, so this is lightweight
        
        # Update session metadata if search was performed
        if "search_type" in result:
            # For Firebase sessions, we'll track this in message metadata instead
            # The old direct sessions access won't work with Firebase backend
            search_info = {
                "query_type": result.get("query_type"),
                "search_type": result.get("search_type"),
                "timestamp": datetime.now().isoformat()
            }
            logger.info(f"Search performed: {search_info}")
            # Use the update_metadata method for in-memory fallback sessions
            session_manager.update_metadata(session_id, "searches_performed", [search_info])
        
        return ChatResponse(
            response=result["response"],
            session_id=session_id,
            confidence=result.get("confidence", 0.0),
            sources=result.get("sources", []),
            query_type=result.get("query_type"),
            timestamp=datetime.now().isoformat(),
            requires_escalation=result.get("requires_escalation", False),
            classification_confidence=result.get("classification_confidence"),
            search_attempts=result.get("search_attempts", [])
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error details: {str(e)}")
        
        # Import here to avoid circular imports
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Return more helpful error information
        error_detail = {
            "error": str(e),
            "type": type(e).__name__,
            "message": "Internal server error - check logs for details"
        }
        
        raise HTTPException(status_code=500, detail=error_detail)

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db = AstraDBConnection()
        connection_results = await db.test_connection()
        all_connected = all(connection_results.values())
        
        return {
            "status": "healthy" if all_connected else "degraded",
            "timestamp": datetime.now().isoformat(),
            "services": {
                "database": "connected" if all_connected else "partial",
                "agent": "running",
                "sessions": len(session_manager.sessions),
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
