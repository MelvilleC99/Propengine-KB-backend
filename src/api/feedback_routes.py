"""Feedback API Route - Save user feedback to Firebase"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from datetime import datetime
from google.cloud import firestore
from src.database.firebase_session_service import FirebaseSessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/feedback", tags=["feedback"])

# Lazy load Firebase - don't initialize at module level!
_firebase_sessions = None

def get_firebase_sessions():
    """Lazy load Firebase session manager"""
    global _firebase_sessions
    if _firebase_sessions is None:
        _firebase_sessions = FirebaseSessionManager()
    return _firebase_sessions


class FeedbackRequest(BaseModel):
    """User feedback on agent response"""
    session_id: str
    message_id: Optional[str] = None
    feedback: str  # "positive" or "negative"
    query: str
    response: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    comment: Optional[str] = None


@router.post("/")
async def save_feedback(request: FeedbackRequest):
    """
    Save user feedback to Firebase
    
    Writes to both:
    - kb_sessions: Update feedback counters
    - feedback: New document with full context
    """
    try:
        logger.info(f"📝 Saving {request.feedback} feedback for session: {request.session_id}")
        
        # Get Firebase session manager (lazy loaded)
        firebase_sessions = get_firebase_sessions()
        
        # Get Firestore client
        db = firebase_sessions.db
        
        if not db:
            raise HTTPException(status_code=500, detail="Firebase not available")
        
        # 1. Create feedback document
        feedback_data = {
            "session_id": request.session_id,
            "message_id": request.message_id,
            "feedback": request.feedback,
            "query": request.query,
            "response": request.response,
            "user_email": request.user_email,
            "user_name": request.user_name,
            "comment": request.comment,
            "timestamp": datetime.now().isoformat(),
            "created_at": firestore.SERVER_TIMESTAMP
        }
        
        feedback_ref = db.collection("feedback").add(feedback_data)
        feedback_id = feedback_ref[1].id
        
        # 2. Update session feedback counters
        session_ref = db.collection("kb_sessions").document(request.session_id)
        
        if request.feedback == "positive":
            session_ref.update({"feedback_positive": firestore.Increment(1)})
        else:
            session_ref.update({"feedback_negative": firestore.Increment(1)})
        
        logger.info(f"✅ Feedback saved: {feedback_id}")
        
        return {
            "success": True,
            "feedback_id": feedback_id,
            "message": "Feedback saved successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
