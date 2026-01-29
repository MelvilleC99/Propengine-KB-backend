"""Admin API routes for monitoring and management"""

from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict
from datetime import datetime
import logging
from src.memory.session_manager import SessionManager
from src.memory.kb_analytics import KBStatsTracker
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize session manager
session_manager = SessionManager()

# Initialize KB stats tracker
kb_stats = KBStatsTracker()

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

@router.get("/kb-analytics/popular")
async def get_popular_kb_entries(limit: int = 10, entry_type: Optional[str] = None):
    """Get most popular KB entries by usage count"""
    try:
        popular_entries = kb_stats.get_popular_entries(limit, entry_type)
        return {
            "popular_entries": popular_entries,
            "count": len(popular_entries),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting popular KB entries: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kb-analytics/summary")
async def get_kb_usage_summary():
    """Get overall KB usage summary statistics"""
    try:
        summary = kb_stats.get_usage_summary()
        return {
            "usage_summary": summary,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting KB usage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/kb-analytics/entry/{parent_entry_id}")
async def get_entry_stats(parent_entry_id: str):
    """Get detailed stats for a specific KB entry"""
    try:
        stats = kb_stats.get_entry_stats(parent_entry_id)
        if stats:
            return {
                "entry_stats": stats,
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=404, detail="Entry not found or no usage data")
    except Exception as e:
        logger.error(f"Error getting entry stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/kb-analytics/sync-usage-counts")
async def sync_kb_usage_counts():
    """
    Sync usage counts from kb_stats to kb_entries
    
    Reads all kb_stats documents and updates the corresponding
    kb_entries documents with the usage_count field.
    
    Perfect for manual testing - click button to sync!
    """
    try:
        db = get_firestore_client()
        
        if not db:
            raise HTTPException(status_code=500, detail="Firebase not connected")
        
        # Get all kb_stats documents
        kb_stats_docs = db.collection("kb_stats").get()
        
        updated_count = 0
        errors = []
        
        for stat_doc in kb_stats_docs:
            stat_data = stat_doc.to_dict()
            parent_entry_id = stat_data.get("parent_entry_id")
            usage_count = stat_data.get("usage_count", 0)
            
            if not parent_entry_id:
                continue
            
            try:
                # Update kb_entries document
                kb_entry_ref = db.collection("kb_entries").document(parent_entry_id)
                kb_entry_ref.update({
                    "usageCount": usage_count,
                    "lastUsed": stat_data.get("last_used"),
                    "avgConfidence": stat_data.get("avg_confidence"),
                    "lastSyncedUsageAt": datetime.now().isoformat()
                })
                updated_count += 1
                
            except Exception as e:
                error_msg = f"Failed to update {parent_entry_id}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            "message": "Usage counts synced successfully",
            "updated_count": updated_count,
            "total_stats": len(kb_stats_docs),
            "errors": errors if errors else None,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error syncing usage counts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/cache/health")
async def get_cache_health():
    """Get Redis cache health status"""
    try:
        health = session_manager.context_cache.health_check()
        return {
            "cache_health": health,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting cache health: {e}")
        raise HTTPException(status_code=500, detail=str(e))
