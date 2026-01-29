"""Feedback API Routes - Handle response feedback from frontend"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List
import logging
from datetime import datetime
from src.database.firebase_feedback_service import FirebaseFeedbackService
from src.utils.rate_limiter import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

# Lazy load service
_feedback_service = None


def get_feedback_service():
    """Lazy load Firebase feedback service"""
    global _feedback_service
    if _feedback_service is None:
        _feedback_service = FirebaseFeedbackService()
    return _feedback_service


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback"""
    # Required fields
    session_id: str = Field(..., description="Session identifier")
    message_id: str = Field(..., description="Message identifier")
    feedback_type: str = Field(..., description="'positive' or 'negative'")
    query: str = Field(..., description="The user's original question")
    response: str = Field(..., description="The agent's response")
    
    # User info
    agent_id: str = Field(..., description="User's agent ID (e.g., BID-xxx)")
    user_email: Optional[str] = Field(None, description="User's email")
    user_name: Optional[str] = Field(None, description="User's display name")
    
    # Context
    agent_type: Optional[str] = Field(None, description="'test', 'support', or 'customer'")
    confidence_score: Optional[float] = Field(None, description="Response confidence (0-1)")
    sources_used: Optional[List[str]] = Field(None, description="KB entry titles used")


class FeedbackResponse(BaseModel):
    """Response model for feedback submission"""
    success: bool
    feedback_id: Optional[str] = None
    message: str
    error: Optional[str] = None


@router.post("/", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest, http_request: Request):
    """
    Submit user feedback on an agent response
    
    Writes to Firebase 'response_feedback' collection
    Rate limited to 50 submissions per day
    """
    try:
        # ============ RATE LIMITING ============
        check_rate_limit(
            request=http_request,
            endpoint_type="feedback",
            agent_id=request.agent_id,
            user_email=request.user_email
        )
        # =======================================
        
        logger.info(f"📝 Receiving {request.feedback_type} feedback for message: {request.message_id}")
        
        # Validate feedback_type
        if request.feedback_type not in ["positive", "negative"]:
            raise HTTPException(
                status_code=400, 
                detail="feedback_type must be 'positive' or 'negative'"
            )
        
        # Get service and write feedback
        service = get_feedback_service()
        result = service.write_feedback(
            session_id=request.session_id,
            message_id=request.message_id,
            feedback_type=request.feedback_type,
            query=request.query,
            response=request.response,
            agent_id=request.agent_id,
            user_email=request.user_email,
            user_name=request.user_name,
            agent_type=request.agent_type,
            confidence_score=request.confidence_score,
            sources_used=request.sources_used
        )
        
        if result["success"]:
            return FeedbackResponse(
                success=True,
                feedback_id=result["feedback_id"],
                message="Feedback saved successfully"
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_feedback_stats():
    """Get feedback statistics for dashboard"""
    try:
        service = get_feedback_service()
        stats = service.get_feedback_stats()
        
        return {
            "success": True,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/negative")
async def get_negative_feedback(limit: int = 20):
    """Get recent negative feedback for review"""
    try:
        service = get_feedback_service()
        feedback = service.get_negative_feedback(limit=limit)
        
        return {
            "success": True,
            "feedback": feedback,
            "count": len(feedback),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to get negative feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
