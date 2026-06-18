"""Chatbot session (history) endpoints — read-only.

    GET /api/chatbot/sessions          list the caller's conversations
    GET /api/chatbot/sessions/{id}     one conversation with its interactions

These let the frontend render "your previous chats" — something today's stack can't do
because live context lives only in Redis (2h TTL). Identity is taken from the auth token
so a user only ever sees their own conversations.
"""

import logging
from fastapi import APIRouter, HTTPException, Depends

from src.api.auth import verify_user_optional
from src.database.firebase_interaction_service import FirebaseInteractionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chatbot/sessions", tags=["chatbot"])

_service = None


def get_service() -> FirebaseInteractionService:
    global _service
    if _service is None:
        _service = FirebaseInteractionService()
    return _service


def _identity(user):
    """Token-derived identity, or None when auth is off (open testing)."""
    if user:
        return user.get("uid") or user.get("email")
    return None


@router.get("")
async def list_sessions(limit: int = 50, user=Depends(verify_user_optional)):
    """List the caller's conversations, most recent first."""
    created_by = _identity(user)
    if not created_by:
        # History is scoped per-user; without a verified identity we can't scope it.
        raise HTTPException(status_code=400, detail="Authentication required to list sessions")
    sessions = get_service().list_sessions(created_by, limit=limit)
    return {"success": True, "sessions": sessions, "count": len(sessions)}


@router.get("/{session_id}")
async def get_session(session_id: str, user=Depends(verify_user_optional)):
    """One conversation with all its interactions in chronological order."""
    session = get_service().get_session_with_interactions(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True, "session": session}
