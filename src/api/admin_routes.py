"""Admin API routes for monitoring and management"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.memory.session_manager import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter()

# Use the same session manager instance
from src.api.chat_routes import session_manager

@router.get("/stats")
async def get_stats():
    """Get overall statistics"""
    active_sessions = session_manager.get_active_sessions()
    total_messages = sum(
        len(session["messages"]) 
        for session in session_manager.sessions.values()
    )
    
    return {
        "total_sessions": len(session_manager.sessions),
        "active_sessions": len(active_sessions),
        "total_messages": total_messages,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/sessions")
async def get_sessions(active_only: bool = True):
    """Get all sessions"""
    if active_only:
        return session_manager.get_active_sessions()
    else:
        all_sessions = []
        for session_id, session in session_manager.sessions.items():
            all_sessions.append({
                "id": session_id,
                "created_at": session["created_at"].isoformat(),
                "last_activity": session["last_activity"].isoformat(),
                "message_count": len(session["messages"]),
                "metadata": session["metadata"]
            })
        return all_sessions

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session"""
    if session_id in session_manager.sessions:
        del session_manager.sessions[session_id]
        return {"message": f"Session {session_id} deleted"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")

@router.post("/clear-expired")
async def clear_expired_sessions():
    """Clear all expired sessions"""
    cleared = session_manager.clear_expired_sessions()
    return {
        "message": f"Cleared {cleared} expired sessions",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/messages")
async def get_all_messages(limit: int = 100):
    """Get recent messages across all sessions"""
    all_messages = []
    
    for session_id, session in session_manager.sessions.items():
        for message in session["messages"]:
            all_messages.append({
                "session_id": session_id,
                "role": message["role"],
                "content": message["content"],
                "timestamp": message["timestamp"]
            })
    
    # Sort by timestamp and return most recent
    all_messages.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_messages[:limit]

@router.post("/escalate/{session_id}")
async def escalate_session(session_id: str, reason: Optional[str] = None):
    """Mark a session for escalation to human support"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session_manager.update_metadata(session_id, "escalated", True)
    session_manager.update_metadata(session_id, "escalation_reason", reason or "User requested")
    session_manager.update_metadata(session_id, "escalation_time", datetime.now().isoformat())
    
    return {
        "message": f"Session {session_id} escalated to human support",
        "reason": reason or "User requested",
        "timestamp": datetime.now().isoformat()
    }
