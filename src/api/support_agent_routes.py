"""Support Agent API Route - For internal support staff"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager
from src.utils.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent/support", tags=["support-agent"])

# Initialize global instances
agent = Agent()
session_manager = SessionManager()


class SupportAgentRequest(BaseModel):
    """Support agent request model"""
    message: str = Field(..., description="User's message")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    user_info: Optional[Dict] = Field(default_factory=dict, description="Optional user information")


class SupportAgentResponse(BaseModel):
    """Support agent response model - clean format for support staff"""
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID")
    confidence: float = Field(..., description="Confidence score")
    sources: List[Dict] = Field(default_factory=list, description="Clean source references")
    query_type: Optional[str] = Field(None, description="Query type")
    timestamp: str = Field(..., description="Response timestamp")
    requires_escalation: bool = Field(False, description="Whether escalation needed")


@router.post("/", response_model=SupportAgentResponse)
async def support_agent(request: SupportAgentRequest, http_request: Request):
    """
    Support Agent Endpoint - For internal support staff
    
    Features:
    - Metadata filtering: INTERNAL entries only
    - Clean source display (no overwhelming details)
    - Shows confidence scores
    - NO debug information
    - Escalation detection enabled
    - Rate limiting: 100 queries/day per user
    """
    try:
        # ============ RATE LIMITING ============
        check_rate_limit(
            request=http_request,
            endpoint_type="query",
            agent_id=request.user_info.get("agent_id"),
            user_email=request.user_info.get("email")
        )
        # =======================================
        
        logger.info(f"🎧 Support Agent - Processing query: {request.message[:50]}...")
        
        # Get or create session
        if request.session_id:
            session = session_manager.get_session(request.session_id)
            if not session:
                session_id = session_manager.create_session(request.user_info)
            else:
                session_id = request.session_id
        else:
            session_id = session_manager.create_session(request.user_info)
        
        # Process query with INTERNAL filtering
        result = await agent.process_query(
            query=request.message,
            session_id=session_id,
            user_info=request.user_info,
            user_type_filter="internal"  # ← INTERNAL ONLY
        )
        
        # Format sources cleanly for support staff
        clean_sources = []
        for source in result.get("sources", []):
            # Handle both KB sources and context sources
            metadata = source.get("metadata", {})
            
            clean_sources.append({
                "title": source.get("title") or metadata.get("title", "Untitled"),
                "section": source.get("entry_type", "unknown"),
                "confidence": source.get("confidence") or source.get("similarity_score", 0.0),
                "category": metadata.get("category"),
                "content_preview": source.get("content_preview", ""),
                "entry_type": source.get("entry_type"),
                "user_type": source.get("user_type")
            })
        
        # Log only escalations and low confidence for support staff
        should_log = (
            result.get("requires_escalation", False) or
            result.get("confidence", 1.0) < 0.7
        )
        
        if should_log:
            await session_manager.add_message(
                session_id=session_id,
                role="user",
                content=request.message,
                metadata={
                    "confidence": result.get("confidence", 0.0),
                    "requires_escalation": result.get("requires_escalation", False),
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": "support"
                }
            )
            
            await session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=result["response"],
                metadata={
                    "confidence": result.get("confidence", 0.0),
                    "query_type": result.get("query_type"),
                    "sources_count": len(clean_sources),
                    "requires_escalation": result.get("requires_escalation", False),
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": "support"
                }
            )
        
        # Log escalations
        if result.get("requires_escalation", False):
            logger.warning(f"⚠️ Support Agent - Escalation needed for query: {request.message[:50]}")
        
        logger.info(f"✅ Support Agent - Response generated with {len(clean_sources)} sources")
        
        return SupportAgentResponse(
            response=result["response"],
            session_id=session_id,
            confidence=result.get("confidence", 0.0),
            sources=clean_sources,  # ← Clean formatted sources
            query_type=result.get("query_type"),
            timestamp=datetime.now().isoformat(),
            requires_escalation=result.get("requires_escalation", False)
        )
        
    except HTTPException:
        # Re-raise HTTPException (including rate limit 429) without modification
        raise
    except Exception as e:
        logger.error(f"❌ Support Agent error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": type(e).__name__}
        )


@router.get("/health")
async def support_agent_health():
    """Health check for support agent"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "agent": "support",
            "sessions": len(session_manager.memory_sessions)
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
