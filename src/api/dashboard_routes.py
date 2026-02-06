"""Dashboard metrics API - Provides analytics for dashboard"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from datetime import datetime, timedelta
from src.database.firebase_client import FirebaseConnection
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# Initialize Firebase connection
firebase = FirebaseConnection()


@router.get("/metrics")
async def get_dashboard_metrics(range: str = "7d"):
    """
    Get dashboard metrics for specified time range
    
    Query params:
        range: today, 7d, 30d, 90d
    
    Returns aggregated metrics from Firebase collections
    """
    try:
        # Calculate date range
        end = datetime.now()
        
        if range == "today":
            start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        elif range == "7d":
            start = end - timedelta(days=7)
        elif range == "30d":
            start = end - timedelta(days=30)
        elif range == "90d":
            start = end - timedelta(days=90)
        else:
            start = end - timedelta(days=7)  # Default to 7 days
        
        logger.info(f"📊 Fetching dashboard metrics for range: {range} ({start} to {end})")
        
        # Fetch all collections in parallel
        kb_stats_ref = firebase.db.collection('kb_stats')
        response_feedback_ref = firebase.db.collection('response_feedback')
        agent_failures_ref = firebase.db.collection('agent_failures')
        kb_entries_ref = firebase.db.collection('kb_entries')
        
        # Get all documents (we'll filter in memory to avoid index issues)
        kb_stats_docs = list(kb_stats_ref.stream())
        feedback_docs = list(response_feedback_ref.stream())
        failure_docs = list(agent_failures_ref.stream())
        kb_entries_docs = list(kb_entries_ref.stream())
        
        logger.info(f"📥 Fetched: {len(kb_stats_docs)} kb_stats, {len(feedback_docs)} feedback, {len(failure_docs)} failures, {len(kb_entries_docs)} entries")
        
        # Filter kb_stats by date
        kb_stats_filtered = []
        total_queries = 0
        for doc in kb_stats_docs:
            data = doc.to_dict()
            last_used_str = data.get('last_used')
            if last_used_str:
                try:
                    last_used = datetime.fromisoformat(last_used_str.replace('Z', '+00:00'))
                    if start <= last_used <= end:
                        kb_stats_filtered.append(data)
                        total_queries += data.get('usage_count', 0)
                except:
                    pass
        
        # Filter feedback by date
        feedback_filtered = []
        for doc in feedback_docs:
            data = doc.to_dict()
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if start <= timestamp <= end:
                        feedback_filtered.append(data)
                except:
                    pass
        
        # Filter failures by date
        failures_filtered = []
        for doc in failure_docs:
            data = doc.to_dict()
            timestamp_str = data.get('timestamp')
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if start <= timestamp <= end:
                        failures_filtered.append(data)
                except:
                    pass
        
        # Calculate confidence
        confidence_scores = [f.get('confidence_score') for f in feedback_filtered if isinstance(f.get('confidence_score'), (int, float))]
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        # Calculate feedback counts
        positive_feedback = len([f for f in feedback_filtered if f.get('feedback_type') == 'positive'])
        negative_feedback = len([f for f in feedback_filtered if f.get('feedback_type') == 'negative'])
        
        # Calculate agent failures and tickets
        agent_failure_count = len(failures_filtered)
        tickets_raised = len([f for f in failures_filtered if f.get('ticket_created') == True])
        
        # Process KB entries
        kb_entries = [doc.to_dict() for doc in kb_entries_docs]
        total_entries = len(kb_entries)
        
        by_type = {
            'how_to': {
                'total': len([e for e in kb_entries if e.get('type') == 'how_to']),
                'synced': len([e for e in kb_entries if e.get('type') == 'how_to' and e.get('vectorStatus') == 'synced']),
                'pending': len([e for e in kb_entries if e.get('type') == 'how_to' and e.get('vectorStatus') != 'synced'])
            },
            'definition': {
                'total': len([e for e in kb_entries if e.get('type') == 'definition']),
                'synced': len([e for e in kb_entries if e.get('type') == 'definition' and e.get('vectorStatus') == 'synced']),
                'pending': len([e for e in kb_entries if e.get('type') == 'definition' and e.get('vectorStatus') != 'synced'])
            },
            'error': {
                'total': len([e for e in kb_entries if e.get('type') == 'error']),
                'synced': len([e for e in kb_entries if e.get('type') == 'error' and e.get('vectorStatus') == 'synced']),
                'pending': len([e for e in kb_entries if e.get('type') == 'error' and e.get('vectorStatus') != 'synced'])
            }
        }
        
        # Count unused entries
        used_entry_ids = set(stat.get('parent_entry_id') for stat in kb_stats_filtered if stat.get('parent_entry_id'))
        unused_count = len([e for e in kb_entries if e.get('id') not in used_entry_ids])
        
        # Get last created entry
        entries_with_dates = [e for e in kb_entries if e.get('createdAt')]
        if entries_with_dates:
            last_entry = max(entries_with_dates, key=lambda e: e.get('createdAt'))
            last_created = last_entry.get('createdAt').isoformat() if hasattr(last_entry.get('createdAt'), 'isoformat') else None
        else:
            last_created = None
        
        logger.info(f"✅ Dashboard metrics calculated: {total_queries} queries, {avg_confidence:.2f} confidence")
        
        return {
            "success": True,
            "data": {
                "queries": {
                    "total": total_queries
                },
                "confidence": {
                    "average": avg_confidence
                },
                "feedback": {
                    "positive": positive_feedback,
                    "negative": negative_feedback,
                    "agentFailures": agent_failure_count,
                    "ticketsRaised": tickets_raised
                },
                "kb": {
                    "total": total_entries,
                    "byType": by_type,
                    "unusedCount": unused_count,
                    "lastCreated": last_created
                },
                "cost": {
                    "total": None,
                    "tokens": None
                }
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Dashboard metrics error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "type": type(e).__name__}
        )
