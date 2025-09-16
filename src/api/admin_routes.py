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
    
    # With Firebase backend, we get summary info rather than direct access
    total_sessions = 0
    total_messages = 0
    
    if active_sessions and isinstance(active_sessions, list) and len(active_sessions) > 0:
        # Check if we're getting the new Firebase format
        if isinstance(active_sessions[0], dict) and "total_sessions" in active_sessions[0]:
            total_sessions = active_sessions[0].get("total_sessions", 0)
            # Estimate messages (would need separate Firebase query for exact count)
            total_messages = total_sessions * 5  # Rough estimate
        else:
            # Legacy format compatibility
            total_sessions = len(active_sessions)
            total_messages = sum(
                session.get("total_queries", 0) for session in active_sessions
                if isinstance(session, dict)
            )
    
    return {
        "total_sessions": total_sessions,
        "active_sessions": total_sessions, 
        "total_messages": total_messages,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/sessions")
async def get_sessions(active_only: bool = True):
    """Get all sessions"""
    if active_only:
        return session_manager.get_active_sessions()
    else:
        # Note: With Firebase backend, we can't iterate through sessions directly
        # This would require a Firebase query to list all sessions
        logger.warning("Full session listing not implemented for Firebase backend")
        return {"message": "Full session listing requires Firebase query implementation"}

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session"""
    # With Firebase backend, session deletion would require Firebase operation
    # For now, this only works for in-memory fallback sessions
    if hasattr(session_manager, 'memory_sessions') and session_id in session_manager.memory_sessions:
        del session_manager.memory_sessions[session_id]
        return {"message": f"Memory session {session_id} deleted"}
    else:
        logger.warning(f"Session deletion not implemented for Firebase sessions: {session_id}")
        return {"message": "Firebase session deletion not implemented"}

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
    # Note: With Firebase backend, messages are stored separately in kb_messages collection
    # This would require a direct Firebase query to implement properly
    
    # For now, only check in-memory fallback sessions
    all_messages = []
    
    if hasattr(session_manager, 'memory_sessions'):
        for session_id, session in session_manager.memory_sessions.items():
            for message in session.get("messages", []):
                all_messages.append({
                    "session_id": session_id,
                    "role": message["role"],
                    "content": message["content"],
                    "timestamp": message["timestamp"]
                })
    
    # Sort by timestamp and limit
    all_messages.sort(key=lambda x: x["timestamp"], reverse=True)
    return all_messages[:limit]
    
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
