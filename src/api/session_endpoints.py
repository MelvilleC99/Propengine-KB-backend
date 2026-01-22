# Session Termination Logic
# /src/api/session_endpoints.py

"""Dedicated endpoints for session management"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from src.memory.session_manager import SessionManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["sessions"])

# Initialize session manager
session_manager = SessionManager()

class SessionEndRequest(BaseModel):
    session_id: str
    agent_id: str  # REQUIRED for analytics
    reason: Optional[str] = "user_ended"

@router.post("/end")
async def end_session(request: SessionEndRequest):
    """
    End session and write all analytics to Firebase
    
    This should be called when:
    - User closes browser (frontend detects)
    - 30 minutes of inactivity (frontend timeout)
    - User explicitly ends chat
    """
    try:
        if not request.agent_id:
            raise HTTPException(status_code=400, detail="agent_id is required")
        
        # End session with analytics batch write
        success = await session_manager.end_session_with_analytics(
            session_id=request.session_id,
            agent_id=request.agent_id,
            reason=request.reason
        )
        
        if success:
            logger.info(f"✅ Session {request.session_id} ended for agent {request.agent_id}")
            return {
                "success": True,
                "message": f"Session {request.session_id} ended successfully",
                "reason": request.reason,
                "status": "ended"
            }
        else:
            logger.warning(f"⚠️ Failed to end session {request.session_id}")
            raise HTTPException(status_code=400, detail="Failed to end session")
            
    except Exception as e:
        logger.error(f"❌ Error ending session {request.session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{session_id}/should-end")
async def check_should_end(session_id: str):
    """Check if session should be terminated"""
    try:
        session = session_manager.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        should_end, reason = session_manager.firebase_sessions.should_end_session(session)
        
        return {
            "session_id": session_id,
            "should_end": should_end,
            "reason": reason,
            "message_count": session.get("message_count", 0),
            "escalations": session.get("escalations", 0),
            "status": session.get("status", "active")
        }
        
    except Exception as e:
        logger.error(f"Error checking session termination {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Session Termination Conditions:

"""
WHEN SHOULD A SESSION END?

1. **User Explicit End**:
   - User says "goodbye", "thanks", "end chat", etc.
   - Frontend sends explicit end session request
   
2. **Natural Conversation End**:
   - User gets complete answer and doesn't respond for 30+ minutes
   - Query resolved with high confidence and no follow-up
   
3. **System Limits**:
   - 50+ messages in session (hit max_messages_per_session)
   - 24+ hours of total session duration
   
4. **Escalation**:
   - User escalated to human support
   - Multiple low-confidence responses in a row
   
5. **Inactivity**:
   - 2+ hours with no activity (standard timeout)
   - 24+ hours since session creation (extended cleanup)
   
6. **Error Conditions**:
   - Repeated system errors
   - User frustrated/negative feedback loop

HOW TO DETECT END CONDITIONS:

1. **NLP End Detection**:
   - "Thanks", "bye", "that's all", "solved"
   - Sentiment analysis showing satisfaction
   
2. **Behavioral Patterns**:
   - Query -> Answer -> No follow-up (satisfied)
   - Multiple "thank you" responses
   
3. **System Monitoring**:
   - Message count tracking
   - Confidence score patterns
   - Escalation flags
"""
