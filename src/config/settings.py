"""Configuration management for PropEngine Support Agent"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings with environment variable support"""
    
    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # AstraDB Configuration
    ASTRADB_TOKEN: str = os.getenv("ASTRADB_APPLICATION_TOKEN", "")
    ASTRADB_ENDPOINT: str = os.getenv("ASTRADB_API_ENDPOINT", "")
    ASTRADB_KEYSPACE: str = os.getenv("ASTRADB_KEYSPACE", "default_keyspace")
    
    # Collection Names - Unified PropertyEngine Collection
    PROPERTY_ENGINE_COLLECTION: str = os.getenv("ASTRADB_PROPERTY_ENGINE_COLLECTION", "property_engine")
    
    # OpenAI Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Redis Configuration (optional - set REDIS_ENABLED=false to disable)
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "true").lower() == "true"
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Firebase Configuration (optional)
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_CLIENT_EMAIL: Optional[str] = os.getenv("FIREBASE_CLIENT_EMAIL")
    FIREBASE_PRIVATE_KEY: Optional[str] = os.getenv("FIREBASE_PRIVATE_KEY")
    FIREBASE_PRIVATE_KEY_ID: Optional[str] = os.getenv("FIREBASE_PRIVATE_KEY_ID")
    FIREBASE_CLIENT_ID: Optional[str] = os.getenv("FIREBASE_CLIENT_ID")
    
    # FreshDesk Configuration (optional)
    FRESHDESK_DOMAIN: Optional[str] = os.getenv("FRESHDESK_DOMAIN")
    FRESHDESK_API_KEY: Optional[str] = os.getenv("FRESHDESK_API_KEY")
    FRESHDESK_PRODUCT_ID: Optional[int] = int(os.getenv("FRESHDESK_PRODUCT_ID", "0")) or None
    FRESHDESK_RESPONDER_ID: Optional[int] = int(os.getenv("FRESHDESK_RESPONDER_ID", "0")) or None
    
    # Query Settings
    MAX_SEARCH_RESULTS: int = 6  # Increased from 3 for better context
    MIN_CONFIDENCE_SCORE: float = 0.50  # Retrieval threshold - low to get candidates, reranker handles precision
    ENABLE_QUERY_ENHANCEMENT: bool = os.getenv("ENABLE_QUERY_ENHANCEMENT", "false").lower() == "true"  # Toggle query enhancement
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env

# Create global settings instance
settings = Settings()
