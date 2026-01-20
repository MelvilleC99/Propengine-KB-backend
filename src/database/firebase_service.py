"""Firebase Service for KB Entry Management"""

import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class FirebaseService:
    """Service for interacting with Firebase Firestore"""
    
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Initialize Firebase Admin SDK"""
        if not firebase_admin._apps:
            try:
                # Get credentials from environment
                project_id = os.getenv('FIREBASE_PROJECT_ID')
                client_email = os.getenv('FIREBASE_CLIENT_EMAIL')
                private_key = os.getenv('FIREBASE_PRIVATE_KEY', '').replace('\\n', '\n')
                
                if not all([project_id, client_email, private_key]):
                    raise ValueError("Missing Firebase credentials in environment")
                
                cred_dict = {
                    "type": "service_account",
                    "project_id": project_id,
                    "client_email": client_email,
                    "private_key": private_key,
                }
                
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
                
                logger.info("✅ Firebase Admin SDK initialized")
                
            except Exception as e:
                logger.error(f"❌ Failed to initialize Firebase: {e}")
                raise
        
        self._db = firestore.client()
    
    def get_kb_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a KB entry from Firestore by ID
        
        Args:
            entry_id: The document ID
            
        Returns:
            Dictionary with entry data, or None if not found
        """
        try:
            doc_ref = self._db.collection('kb_entries').document(entry_id)
            doc = doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                data['id'] = doc.id
                return data
            else:
                logger.warning(f"KB entry not found: {entry_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error fetching KB entry {entry_id}: {e}")
            raise
    
    def update_sync_status(
        self, 
        entry_id: str, 
        status: str, 
        error: Optional[str] = None
    ):
        """
        Update the vector sync status of a KB entry
        
        Args:
            entry_id: The document ID
            status: 'pending', 'synced', or 'failed'
            error: Error message if status is 'failed'
        """
        try:
            doc_ref = self._db.collection('kb_entries').document(entry_id)
            
            update_data = {
                'vectorStatus': status,
                'lastSyncedAt': firestore.SERVER_TIMESTAMP,
            }
            
            if error:
                update_data['syncError'] = error
            else:
                # Clear any previous error
                update_data['syncError'] = firestore.DELETE_FIELD
            
            # Add to sync history
            sync_history_entry = {
                'action': f'vector_{status}',
                'timestamp': datetime.utcnow(),
            }
            
            if error:
                sync_history_entry['error'] = error
            
            update_data['syncHistory'] = firestore.ArrayUnion([sync_history_entry])
            
            doc_ref.update(update_data)
            
            logger.info(f"✅ Updated sync status for {entry_id}: {status}")
            
        except Exception as e:
            logger.error(f"Error updating sync status for {entry_id}: {e}")
            raise
