"""


All limits are per user (agent_id), tracked in Redis with automatic TTL cleanup.
"""

import os

# ============================================
# RATE LIMIT CONFIGURATION
# ============================================
# Change these values to adjust rate limits

RATE_LIMITS = {
    # === QUERY ENDPOINTS ===
    # Main agent query endpoints (support, customer, test agents)
    "query": {
        "requests": 10,       # Number of queries allowed per user per window
        "window": 86400,      # Time window in seconds (86400 = 24 hours)
        "description": "Agent queries (support/customer/test)"
    },
    
    # === PER-SESSION RATE LIMITING ===
    # Optional: Prevent burst/spam within a single session
    # Currently NOT ACTIVE - set to higher values if enabling
    "query_session": {
        "requests": 60,       # Queries per session
        "window": 60,         # Time window in seconds (60 = 1 minute)
        "description": "Per-session burst protection (not active)"
    },
    
    # === FEEDBACK ENDPOINTS ===
    # Thumbs up/down feedback submissions
    "feedback": {
        "requests": 10,       # Number of feedback submissions allowed
        "window": 86400,      # 24 hours
        "description": "Response feedback (thumbs up/down)"
    },
    
    # === TICKET/ESCALATION ENDPOINTS ===
    # Agent failure reporting and ticket creation
    "ticket": {
        "requests": 2,        # Number of tickets/failures allowed
        "window": 86400,      # 24 hours
        "description": "Agent failures and ticket creation"
    },
    
    # === DEFAULT FALLBACK ===
    # Applied to any endpoint not explicitly configured
    "default": {
        "requests": 100,      # General limit
        "window": 300,        # 5 minutes
        "description": "Default limit for unconfigured endpoints"
    }
}

# ============================================
# COMMON TIME WINDOWS (for easy reference)
# ============================================
# Use these constants to make window values more readable

ONE_MINUTE = 60
FIVE_MINUTES = 300
TEN_MINUTES = 600
THIRTY_MINUTES = 1800
ONE_HOUR = 3600
SIX_HOURS = 21600
TWELVE_HOURS = 43200
ONE_DAY = 86400
ONE_WEEK = 604800

# ============================================
# SUGGESTED CONFIGURATIONS
# ============================================

# --- HIGH VOLUME (for internal testing) ---
HIGH_VOLUME_LIMITS = {
    "query": {"requests": 1000, "window": ONE_DAY},
    "feedback": {"requests": 500, "window": ONE_DAY},
    "ticket": {"requests": 100, "window": ONE_DAY},
}

# --- STRICT LIMITS (for external users) ---
STRICT_LIMITS = {
    "query": {"requests": 50, "window": ONE_DAY},
    "feedback": {"requests": 20, "window": ONE_DAY},
    "ticket": {"requests": 5, "window": ONE_DAY},
}

# --- DEVELOPMENT/TESTING (no limits) ---
DEV_LIMITS = {
    "query": {"requests": 10000, "window": ONE_DAY},
    "feedback": {"requests": 10000, "window": ONE_DAY},
    "ticket": {"requests": 10000, "window": ONE_DAY},
}

# ============================================
# ACTIVE CONFIGURATION
# ============================================
# The active tier is chosen by the RATE_LIMIT_TIER env var and DEFAULTS TO
# "production" — so production is safe even if the env var is never set. Set
# RATE_LIMIT_TIER=dev in your local .env to lift limits while developing.
# Each tier inherits the full RATE_LIMITS set (incl. the "default" fallback) and
# overrides the per-endpoint numbers.

_TIERS = {
    "production": RATE_LIMITS,
    "high_volume": {**RATE_LIMITS, **HIGH_VOLUME_LIMITS},
    "strict": {**RATE_LIMITS, **STRICT_LIMITS},
    "dev": {**RATE_LIMITS, **DEV_LIMITS},
}

RATE_LIMIT_TIER = os.getenv("RATE_LIMIT_TIER", "production").lower()
ACTIVE_LIMITS = _TIERS.get(RATE_LIMIT_TIER, RATE_LIMITS)


def get_rate_limits():
    """
    Get the currently active rate limits
    
    Returns:
        dict: Rate limit configuration
    """
    return ACTIVE_LIMITS


def get_limit_for_endpoint(endpoint_type: str):
    """
    Get rate limit configuration for a specific endpoint
    
    Args:
        endpoint_type: Endpoint type (query, feedback, ticket, default)
        
    Returns:
        dict: Configuration with 'requests' and 'window' keys
    """
    limits = get_rate_limits()
    return limits.get(endpoint_type, limits.get("default"))


# ============================================
# USAGE EXAMPLES
# ============================================
"""
# To switch tier system-wide, set the env var (NOT a code edit):
#   RATE_LIMIT_TIER=production   (default — the real limits)
#   RATE_LIMIT_TIER=dev          (10k/day — local development only)
#   RATE_LIMIT_TIER=strict       (tighter, for external users)

# To change a specific production number, edit RATE_LIMITS above:
#   RATE_LIMITS["query"]["requests"] = 200
"""
