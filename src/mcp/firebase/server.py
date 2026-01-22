"""Firebase MCP Server - Handles all Firebase Firestore operations"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime
from google.cloud.firestore_v1 import FieldFilter, Query
from src.database.firebase_client import get_firestore_client

logger = logging.getLogger(__name__)

KB_COLLECTION = "kb_entries"


class FirebaseMCP:
    """
    MCP Server for Firebase operations.
    Provides tools for CRUD operations on KB entries in Firestore.
    """
    
    def __init__(self):
        """Initialize Firebase MCP with existing Firestore connection"""
        self.db = get_firestore_client()
        logger.info("✅ Firebase MCP initialized")
    
    async def create_entry(self, entry_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new KB entry in Firebase.
        
        Args:
            entry_data: Entry data (without id, createdAt, updatedAt)
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123",
                "entry": {...full entry data...}
            }
        """
        try:
            # Add timestamps
            now = datetime.utcnow()
            entry_data.update({
                "createdAt": now,
                "updatedAt": now,
                "usageCount": 0,
                "vectorStatus": "pending"  # Will be synced later
            })
            
            # DEBUG: Log the data size
            import json
            data_size = len(json.dumps(entry_data, default=str))
            logger.info(f"📦 Entry data size: {data_size} bytes")
            
            # Check for nested arrays (Firebase limitation)
            def check_nested_arrays(obj, path=""):
                if isinstance(obj, list):
                    for i, item in enumerate(obj):
                        if isinstance(item, (list, dict)):
                            check_nested_arrays(item, f"{path}[{i}]")
                elif isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, (list, dict)):
                            check_nested_arrays(value, f"{path}.{key}")
            
            check_nested_arrays(entry_data)
            
            # Create document
            doc_ref = self.db.collection(KB_COLLECTION).document()
            doc_ref.set(entry_data)
            
            entry_id = doc_ref.id
            
            logger.info(f"✅ Created KB entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id,
                "entry": {**entry_data, "id": entry_id}
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to create entry: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Get a single KB entry by ID.
        
        Args:
            entry_id: Document ID
            
        Returns:
            {
                "success": True,
                "entry": {...entry data...}
            }
        """
        try:
            doc_ref = self.db.collection(KB_COLLECTION).document(entry_id)
            doc = doc_ref.get()
            
            if not doc.exists:
                return {
                    "success": False,
                    "error": f"Entry not found: {entry_id}"
                }
            
            entry = doc.to_dict()
            entry["id"] = doc.id
            
            logger.info(f"✅ Retrieved entry: {entry_id}")
            
            return {
                "success": True,
                "entry": entry
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get entry {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def list_entries(
        self, 
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        List KB entries with optional filters.
        
        Args:
            filters: Optional filters like {"type": "how_to", "archived": False}
            limit: Max number of entries to return
            
        Returns:
            {
                "success": True,
                "entries": [...list of entries...],
                "count": 10
            }
        """
        try:
            # Start with base collection
            query = self.db.collection(KB_COLLECTION)
            
            # Apply filters
            if filters:
                for field, value in filters.items():
                    query = query.where(filter=FieldFilter(field, "==", value))
            
            # Apply limit
            if limit:
                query = query.limit(limit)
            
            # Execute query
            docs = query.stream()
            
            entries = []
            for doc in docs:
                entry = doc.to_dict()
                entry["id"] = doc.id
                entries.append(entry)
            
            logger.info(f"✅ Listed {len(entries)} entries")
            
            return {
                "success": True,
                "entries": entries,
                "count": len(entries)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to list entries: {e}")
            return {
                "success": False,
                "error": str(e),
                "entries": [],
                "count": 0
            }
    
    async def update_entry(
        self, 
        entry_id: str, 
        update_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update an existing KB entry.
        
        Args:
            entry_id: Document ID
            update_data: Fields to update
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123"
            }
        """
        try:
            # Add updated timestamp
            update_data["updatedAt"] = datetime.utcnow()
            
            # Update document
            doc_ref = self.db.collection(KB_COLLECTION).document(entry_id)
            doc_ref.update(update_data)
            
            logger.info(f"✅ Updated entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to update entry {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def delete_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Delete a KB entry (hard delete).
        
        Args:
            entry_id: Document ID
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123"
            }
        """
        try:
            doc_ref = self.db.collection(KB_COLLECTION).document(entry_id)
            doc_ref.delete()
            
            logger.info(f"✅ Deleted entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to delete entry {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def archive_entry(self, entry_id: str) -> Dict[str, Any]:
        """
        Archive a KB entry (soft delete).
        
        Args:
            entry_id: Document ID
            
        Returns:
            {
                "success": True,
                "entry_id": "abc123"
            }
        """
        try:
            update_data = {
                "archived": True,
                "archivedAt": datetime.utcnow(),
                "updatedAt": datetime.utcnow()
            }
            
            doc_ref = self.db.collection(KB_COLLECTION).document(entry_id)
            doc_ref.update(update_data)
            
            logger.info(f"✅ Archived entry: {entry_id}")
            
            return {
                "success": True,
                "entry_id": entry_id
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to archive entry {entry_id}: {e}")
            return {
                "success": False,
                "error": str(e)
            }
