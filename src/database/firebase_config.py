"""Firebase Admin SDK configuration for PropertyEngine KB backend"""

import os
import json
import logging
from typing import Optional
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime

logger = logging.getLogger(__name__)

class FirebaseConfig:
    """Firebase Admin SDK configuration and initialization - Singleton Pattern"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Prevent re-initialization of already created instance
        if hasattr(self, '_initialized'):
            return
            
        self.db: Optional[firestore.Client] = None
        self._initialize_firebase()
        self._initialized = True
    
    def _initialize_firebase(self):
        """Initialize Firebase Admin SDK"""
        try:
            # Check if Firebase app already exists
            app = firebase_admin.get_app()
            logger.info("Using existing Firebase app")
        except ValueError:
            # No app exists, create one
            self._create_firebase_app()
        
        # Initialize Firestore client
        self.db = firestore.client()
        logger.info("✅ Firebase Admin SDK initialized successfully")
    
    def _create_firebase_app(self):
        """Create Firebase app with credentials from environment"""
        try:
            # Use existing environment variables from .env
            project_id = os.getenv('FIREBASE_PROJECT_ID')
            client_email = os.getenv('FIREBASE_CLIENT_EMAIL') 
            private_key = os.getenv('FIREBASE_PRIVATE_KEY')
            
            if not all([project_id, client_email, private_key]):
                raise ValueError("Missing Firebase credentials in environment variables")
            
            # Clean up private key (remove quotes and fix newlines)
            private_key = private_key.replace('\\n', '\n').strip('"')
            
            # Create credentials object
            cred_dict = {
                "type": "service_account",
                "project_id": project_id,
                "client_email": client_email,
                "private_key": private_key,
                "private_key_id": "firebase-admin-key",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs"
            }
            
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            logger.info(f"🔥 Firebase app created for project: {project_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firebase: {e}")
            # For development: continue without Firebase
            logger.warning("⚠️ Continuing without Firebase - sessions will be in-memory only")
            raise
    
    def get_db(self) -> Optional[firestore.Client]:
        """Get Firestore database client"""
        return self.db
    
    def is_available(self) -> bool:
        """Check if Firebase is available"""
        return self.db is not None

# Global Firebase instance
firebase_config = FirebaseConfig()
