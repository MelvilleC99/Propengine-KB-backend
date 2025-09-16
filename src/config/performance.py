# Performance Configuration
# /src/config/performance.py

"""Performance settings for PropertyEngine KB backend"""

class PerformanceConfig:
    """Configuration for optimizing backend performance"""
    
    # Message Logging Strategy
    LOG_ALL_MESSAGES = False  # Set to True only for debugging
    LOG_ESCALATIONS_ONLY = True  # Log only problematic interactions
    LOG_LOW_CONFIDENCE_THRESHOLD = 0.7  # Log if confidence below this
    
    # Firebase Optimization
    USE_BATCH_WRITES = True  # Batch Firebase operations
    FIREBASE_TIMEOUT = 5.0  # Seconds before fallback
    CACHE_SESSION_LOCALLY = True  # Cache session data in memory
    
    # Session Management
    SESSION_UPDATE_FREQUENCY = 30  # Only update Firebase every 30 seconds
    MEMORY_CACHE_SIZE = 100  # Keep 100 sessions in memory
    
    # Rate Limiting
    RATE_LIMIT_IN_MEMORY = True  # Use memory instead of database
    CLEANUP_INTERVAL = 300  # Clean rate limit cache every 5 minutes

# Message Logging Decision Matrix
LOGGING_RULES = {
    "high_confidence_success": {"log": False, "reason": "Normal operation"},
    "low_confidence": {"log": True, "reason": "Needs analysis"},
    "escalation_required": {"log": True, "reason": "Human review needed"},
    "user_feedback": {"log": True, "reason": "Feedback analysis"},
    "error_occurred": {"log": True, "reason": "Debug information"},
    "first_message_session": {"log": True, "reason": "Session tracking"}
}
