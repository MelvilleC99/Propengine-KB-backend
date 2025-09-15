"""Chat API routes for the support agent"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager
from src.database.connection import AstraDBConnection

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

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint"""
    try:
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
        
        # Update session metadata if collection was searched
        if "collection_searched" in result:
            current_collections = session_manager.sessions[session_id]["metadata"].get("collections_used", [])
            if result["collection_searched"] not in current_collections:
                current_collections.append(result["collection_searched"])
                session_manager.update_metadata(session_id, "collections_used", current_collections)
        
        return ChatResponse(
            response=result["response"],
            session_id=session_id,
            confidence=result.get("confidence", 0.0),
            sources=result.get("sources", []),
            query_type=result.get("query_type"),
            timestamp=datetime.now().isoformat(),
            requires_escalation=result.get("requires_escalation", False)
        )
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
