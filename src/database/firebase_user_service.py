"""Firebase User Management Service"""

import logging
from datetime import datetime
from typing import Dict, Optional
from google.cloud.firestore_v1 import SERVER_TIMESTAMP, Increment
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)

class FirebaseUserService:
    """Manages user documents in Firebase"""
    
    def __init__(self):
        self.db = get_firestore_client()
        self.users_collection = "users"
    
    def create_or_update_user(self, agent_id: str, user_data: Dict) -> bool:
        """
        Create or update user document
        
        Args:
            agent_id: Agent ID (e.g., BID-VXDZgFkHqzphyrg)
            user_data: {email, name, phone, agency, office, user_type}
        """
        try:
            if not self.db:
                logger.warning("Firebase unavailable")
                return False
            
            user_ref = self.db.collection(self.users_collection).document(agent_id)
            user_doc = user_ref.get()
            
            if user_doc.exists():
                # Update existing user
                user_ref.update({
                    "last_seen": SERVER_TIMESTAMP,
                    **user_data  # Update any changed fields
                })
                logger.info(f"✅ Updated user: {agent_id}")
            else:
                # Create new user
                user_ref.set({
                    "agent_id": agent_id,
                    "email": user_data.get("email"),
                    "name": user_data.get("name"),
                    "phone": user_data.get("phone"),
                    "agency": user_data.get("agency"),
                    "office": user_data.get("office"),
                    "user_type": user_data.get("user_type"),
                    
                    # Stats
                    "total_sessions": 0,
                    "total_queries": 0,
                    "first_seen": SERVER_TIMESTAMP,
                    "last_seen": SERVER_TIMESTAMP,
                    
                    # Recent sessions (empty initially)
                    "recent_sessions": []
                })
                logger.info(f"✅ Created new user: {agent_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create/update user {agent_id}: {e}")
            return False
    
    async def update_user_activity(
        self, 
        agent_id: str, 
        num_queries: int, 
        user_data: Optional[Dict] = None,
        total_cost: float = 0.0
    ) -> bool:
        """
        Update user activity stats after session ends
        Creates user if doesn't exist
        
        Args:
            agent_id: Agent ID
            num_queries: Number of queries in the session
            user_data: Optional user info if creating new user
            total_cost: Total cost for this session in USD
        """
        try:
            if not self.db:
                return False
            
            user_ref = self.db.collection(self.users_collection).document(agent_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists():
                # User doesn't exist - create it first
                logger.info(f"📝 User {agent_id} doesn't exist, creating...")
                user_ref.set({
                    "agent_id": agent_id,
                    "email": user_data.get("email") if user_data else None,
                    "name": user_data.get("name") if user_data else None,
                    "phone": user_data.get("phone") if user_data else None,
                    "agency": user_data.get("agency") if user_data else None,
                    "office": user_data.get("office") if user_data else None,
                    "user_type": user_data.get("user_type") if user_data else None,
                    
                    # Stats - start with this session's stats
                    "total_sessions": 1,
                    "total_queries": num_queries,
                    "total_cost": total_cost,  # ← NEW: Cost tracking
                    "first_seen": SERVER_TIMESTAMP,
                    "last_seen": SERVER_TIMESTAMP,
                    
                    # Recent sessions (will be added separately)
                    "recent_sessions": []
                })
                logger.info(f"✅ Created new user: {agent_id}")
            else:
                # User exists - increment stats
                user_ref.update({
                    "total_sessions": Increment(1),
                    "total_queries": Increment(num_queries),
                    "total_cost": Increment(total_cost),  # ← NEW: Increment cost
                    "last_seen": SERVER_TIMESTAMP
                })
                logger.info(f"✅ Updated activity for {agent_id}: +1 session, +{num_queries} queries, +${total_cost:.6f} cost")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to update user activity: {e}")
            return False
    
    def add_recent_session(self, agent_id: str, session_summary: Dict) -> bool:
        """
        Add session to user's recent_sessions (keep last 5)
        
        Args:
            agent_id: Agent ID
            session_summary: {session_id, date, summary}
        """
        try:
            if not self.db:
                return False
            
            user_ref = self.db.collection(self.users_collection).document(agent_id)
            user_doc = user_ref.get()
            
            if user_doc.exists():
                recent = user_doc.to_dict().get("recent_sessions", [])
                
                # Add new session at beginning
                recent.insert(0, session_summary)
                
                # Keep only last 5
                recent = recent[:5]
                
                user_ref.update({"recent_sessions": recent})
                logger.info(f"✅ Added session to {agent_id}'s history")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Failed to add recent session: {e}")
            return False
