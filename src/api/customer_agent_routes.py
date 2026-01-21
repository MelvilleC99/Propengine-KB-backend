"""Customer Agent API Route - For external customers"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime
import logging
from src.agent.orchestrator import Agent
from src.memory.session_manager import SessionManager

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


class CustomerAgentResponse(BaseModel):
    """Customer agent response model - minimal for customers"""
    response: str = Field(..., description="Agent's response")
    session_id: str = Field(..., description="Session ID")
    timestamp: str = Field(..., description="Response timestamp")
    requires_escalation: bool = Field(False, description="Whether escalation needed")


@router.post("/", response_model=CustomerAgentResponse)
async def customer_agent(request: CustomerAgentRequest, http_request: Request):
    """
    Customer Agent Endpoint - For external customers
    
    Features:
    - Metadata filtering: EXTERNAL entries only
    - NO source display
    - NO confidence scores
    - NO debug information
    - Rate limiting: 50 queries/hour per session
    - Escalation detection enabled
    """
    try:
        logger.info(f"👤 Customer Agent - Processing query: {request.message[:50]}...")
        
        # Get or create session
        if request.session_id:
            session = session_manager.get_session(request.session_id)
            if not session:
                session_id = session_manager.create_session(request.user_info)
            else:
                session_id = request.session_id
        else:
            session_id = session_manager.create_session(request.user_info)
        
        # Process query with EXTERNAL filtering
        result = await agent.process_query(
            query=request.message,
            session_id=session_id,
            user_info=request.user_info,
            user_type_filter="external"  # ← EXTERNAL ONLY
        )
        
        # Log only escalations for customers
        if result.get("requires_escalation", False):
            logger.warning(f"⚠️ Customer Agent - Escalation needed for query: {request.message[:50]}")
            
            session_manager.add_message(
                session_id=session_id,
                role="user",
                content=request.message,
                metadata={
                    "requires_escalation": True,
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": "customer"
                }
            )
            
            session_manager.add_message(
                session_id=session_id,
                role="assistant",
                content=result["response"],
                metadata={
                    "requires_escalation": True,
                    "timestamp": datetime.now().isoformat(),
                    "agent_type": "customer"
                }
            )
        
        logger.info(f"✅ Customer Agent - Response generated (external only)")
        
        # Return minimal response for customers
        return CustomerAgentResponse(
            response=result["response"],
            session_id=session_id,
            timestamp=datetime.now().isoformat(),
            requires_escalation=result.get("requires_escalation", False)
            # ← NO confidence, NO sources, NO debug
        )
        
    except Exception as e:
        logger.error(f"❌ Customer Agent error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="We're having trouble processing your request. Please try again or contact support."
        )


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
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
