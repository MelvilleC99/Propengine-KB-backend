"""Firebase Admin SDK initialization and connection management"""

import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional
import logging
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Global firestore client (initialized once at startup)
_firestore_client: Optional[firestore.Client] = None


def initialize_firebase() -> firestore.Client:
    """
    Initialize Firebase Admin SDK at application startup.
    Should be called once in main.py lifespan.
    
    Returns:
        Firestore client instance
    """
    global _firestore_client
    
    if _firestore_client is not None:
        logger.info("Firebase already initialized, returning existing client")
        return _firestore_client
    
    try:
        # Check if Firebase app already exists
        if not firebase_admin._apps:
            # Create credentials from environment variables
            cred_dict = {
                "type": "service_account",
                "project_id": settings.FIREBASE_PROJECT_ID,
                "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
                "private_key": settings.FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
                "client_email": settings.FIREBASE_CLIENT_EMAIL,
                "client_id": settings.FIREBASE_CLIENT_ID,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{settings.FIREBASE_CLIENT_EMAIL}"
            }
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info("✅ Firebase Admin SDK initialized successfully")
        
        # Get Firestore client
        _firestore_client = firestore.client()
        logger.info("✅ Firestore client created successfully")
        
        return _firestore_client
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Firebase Admin SDK: {e}")
        raise


def get_firestore_client() -> firestore.Client:
    """
    Get the initialized Firestore client.
    Must call initialize_firebase() first at startup.
    
    Returns:
        Firestore client instance
        
    Raises:
        RuntimeError: If Firebase not initialized
    """
    if _firestore_client is None:
        raise RuntimeError(
            "Firebase not initialized. Call initialize_firebase() at startup."
        )
    return _firestore_client


async def test_firebase_connection() -> bool:
    """
    Test Firebase connection by attempting to read from a collection.
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        db = get_firestore_client()
        
        # Try to list collections (doesn't require any data to exist)
        collections = db.collections()
        collection_list = [col.id for col in collections]
        
        logger.info(f"✅ Firebase connection test successful. Collections: {collection_list}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Firebase connection test failed: {e}")
        return False
