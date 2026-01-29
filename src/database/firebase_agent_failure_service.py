"""Firebase Agent Failure Service - Tracks when agent can't answer and ticket escalations"""

import logging
from datetime import datetime
from typing import Dict, Optional, List
from google.cloud.firestore_v1 import SERVER_TIMESTAMP
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)


class FirebaseAgentFailureService:
    """
    Manages agent failure documents in Firebase
    
    Collection: 'agent_failures'
    """
    
    def __init__(self):
        self.db = get_firestore_client()
        self.collection_name = "agent_failures"
    
    def create_failure(
        self,
        session_id: str,
        agent_id: str,
        query: str,
        agent_response: str,
        confidence_score: float,
        escalation_reason: str,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        user_agency: Optional[str] = None,
        user_office: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> Dict:
        """Create initial agent failure record"""
        try:
            if not self.db:
                logger.error("Firebase not available")
                return {"success": False, "error": "Firebase not available"}
            
            failure_doc = {
                # Identity
                "session_id": session_id,
                "agent_id": agent_id,
                "user_email": user_email,
                "user_name": user_name,
                "user_agency": user_agency,
                "user_office": user_office,
                
                # The failed interaction
                "query": query,
                "agent_response": agent_response,
                "confidence_score": confidence_score,
                "escalation_reason": escalation_reason,
                "agent_type": agent_type,
                
                # Timestamps
                "created_at": SERVER_TIMESTAMP,
                "timestamp": datetime.now().isoformat(),
                
                # Ticket status (initial)
                "ticket_offered": True,
                "ticket_created": False,
                "ticket_id": None,
                "ticket_created_at": None,
                
                # User action
                "user_action": "pending",
                "action_timestamp": None,
                
                # Analytics flags
                "needs_kb_entry": True,
                "resolved": False
            }
            
            doc_ref = self.db.collection(self.collection_name).add(failure_doc)
            failure_id = doc_ref[1].id
            
            logger.info(f"✅ Agent failure recorded: {failure_id}")
            
            return {"success": True, "failure_id": failure_id}
            
        except Exception as e:
            logger.error(f"❌ Failed to create agent failure: {e}")
            return {"success": False, "error": str(e)}
    
    def update_ticket_created(
        self,
        failure_id: str,
        ticket_id: int,
        ticket_subject: Optional[str] = None,
        ticket_priority: Optional[str] = None
    ) -> Dict:
        """Update failure record when ticket is created"""
        try:
            if not self.db:
                return {"success": False, "error": "Firebase not available"}
            
            doc_ref = self.db.collection(self.collection_name).document(failure_id)
            
            doc = doc_ref.get()
            if not doc.exists:
                return {"success": False, "error": "Failure record not found"}
            
            doc_ref.update({
                "ticket_created": True,
                "ticket_id": ticket_id,
                "ticket_subject": ticket_subject,
                "ticket_priority": ticket_priority,
                "ticket_created_at": SERVER_TIMESTAMP,
                "user_action": "accepted",
                "action_timestamp": SERVER_TIMESTAMP
            })
            
            logger.info(f"✅ Failure {failure_id} updated with ticket #{ticket_id}")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"❌ Failed to update ticket info: {e}")
            return {"success": False, "error": str(e)}
    
    def update_declined(self, failure_id: str) -> Dict:
        """Update failure record when user declines ticket"""
        try:
            if not self.db:
                return {"success": False, "error": "Firebase not available"}
            
            doc_ref = self.db.collection(self.collection_name).document(failure_id)
            
            doc = doc_ref.get()
            if not doc.exists:
                return {"success": False, "error": "Failure record not found"}
            
            doc_ref.update({
                "user_action": "declined",
                "action_timestamp": SERVER_TIMESTAMP
            })
            
            logger.info(f"✅ Failure {failure_id} marked as declined")
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"❌ Failed to update decline: {e}")
            return {"success": False, "error": str(e)}
    
    def get_failure(self, failure_id: str) -> Optional[Dict]:
        """Get a failure record by ID"""
        try:
            if not self.db:
                return None
            
            doc = self.db.collection(self.collection_name).document(failure_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                data["id"] = doc.id
                return data
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Failed to get failure: {e}")
            return None
    
    def get_failures_needing_kb(self, limit: int = 20) -> List[Dict]:
        """Get failures that need KB entries"""
        try:
            if not self.db:
                return []
            
            docs = (
                self.db.collection(self.collection_name)
                .where("needs_kb_entry", "==", True)
                .where("ticket_created", "==", False)
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
                .get()
            )
            
            results = []
            for doc in docs:
                data = doc.to_dict()
                data["id"] = doc.id
                results.append(data)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to get failures needing KB: {e}")
            return []
    
    def get_failure_stats(self) -> Dict:
        """Get failure statistics for dashboard"""
        try:
            if not self.db:
                return {"error": "Firebase not available"}
            
            docs = self.db.collection(self.collection_name).get()
            
            total = 0
            tickets_created = 0
            declined = 0
            pending = 0
            
            for doc in docs:
                data = doc.to_dict()
                total += 1
                
                action = data.get("user_action", "pending")
                if action == "accepted" or data.get("ticket_created"):
                    tickets_created += 1
                elif action == "declined":
                    declined += 1
                else:
                    pending += 1
            
            return {
                "total_failures": total,
                "tickets_created": tickets_created,
                "declined": declined,
                "pending": pending,
                "ticket_rate": round(tickets_created / total * 100, 1) if total > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get failure stats: {e}")
            return {"error": str(e)}
