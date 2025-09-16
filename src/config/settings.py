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
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # Firebase Configuration (optional)
    FIREBASE_PROJECT_ID: Optional[str] = os.getenv("FIREBASE_PROJECT_ID")
    FIREBASE_CLIENT_EMAIL: Optional[str] = os.getenv("FIREBASE_CLIENT_EMAIL")
    FIREBASE_PRIVATE_KEY: Optional[str] = os.getenv("FIREBASE_PRIVATE_KEY")
    
    # FreshDesk Configuration (optional)
    FRESHDESK_DOMAIN: Optional[str] = os.getenv("FRESHDESK_DOMAIN")
    FRESHDESK_API_KEY: Optional[str] = os.getenv("FRESHDESK_API_KEY")
    
    # Query Settings
    MAX_SEARCH_RESULTS: int = 3
    MIN_CONFIDENCE_SCORE: float = 0.7
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env

# Create global settings instance
settings = Settings()
