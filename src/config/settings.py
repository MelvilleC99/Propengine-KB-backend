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
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Authentication — require a valid Firebase ID token on protected routes.
    # Secure by default (ON). Set REQUIRE_AUTH=false ONLY for local dev or a brief
    # migration window (e.g. before the frontend has started sending the token).
    REQUIRE_AUTH: bool = os.getenv("REQUIRE_AUTH", "true").lower() == "true"

    # DEV/demo escape hatch: open ONLY the customer-facing flow (customer agent chat,
    # feedback, escalation — all non-destructive) without auth, so a UI that can't yet
    # authenticate can use it. KB management + admin stay locked regardless. Re-lock by
    # setting this false once the UI sends Firebase tokens.
    CUSTOMER_AGENT_PUBLIC: bool = os.getenv("CUSTOMER_AGENT_PUBLIC", "false").lower() == "true"

    # Migration kill-switch. When TRUE (default) the LEGACY customer endpoints stay registered
    # alongside the new /api/chatbot/* ones (parallel run). Set FALSE — once the frontend is
    # FULLY on /api/chatbot/* — to retire the old chat (/api/agent/customer/stream),
    # /api/feedback and /api/agent-failure so ONLY the new endpoints serve the chatbot.
    # The Freshdesk close-webhook stays registered either way.
    ENABLE_LEGACY_ENDPOINTS: bool = os.getenv("ENABLE_LEGACY_ENDPOINTS", "true").lower() == "true"

    # Extra CORS origins (e.g. a demo/DEV UI on another domain), comma-separated.
    # Merged with the built-in defaults in main.py.
    CORS_ALLOWED_ORIGINS: str = os.getenv("CORS_ALLOWED_ORIGINS", "")

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

    # Response model selection. The OpenAI proxy buffers streamed responses (>~100 chars,
    # PII de-anonymisation), so the answer arrives as one chunk. The Qwen gateway streams
    # token-by-token (verified). Set RESPONSE_USE_QWEN=true to generate ANSWERS via Qwen.
    # Embeddings ALWAYS stay on OpenAI (EMBEDDING_MODEL) — only answer generation switches.
    RESPONSE_USE_QWEN: bool = os.getenv("RESPONSE_USE_QWEN", "false").lower() == "true"
    QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
    QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://ai-api.betterhome-ai.co.za/v1")
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen3.6")

    # LLM request safety — a single call fails fast instead of hanging if the proxy stalls.
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    
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
    # Route AI-created tickets to a group queue (e.g. Customer Support) instead of one agent.
    FRESHDESK_GROUP_ID: Optional[int] = int(os.getenv("FRESHDESK_GROUP_ID", "0")) or None
    # Shared secret Freshdesk sends as the X-Webhook-Secret header on the ticket-closed webhook.
    FRESHDESK_WEBHOOK_SECRET: Optional[str] = os.getenv("FRESHDESK_WEBHOOK_SECRET")
    
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
