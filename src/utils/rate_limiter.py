"""Rate limiting for PropertyEngine KB API using Redis"""

import time
import logging
from typing import Dict, Optional
from fastapi import HTTPException, Request
from datetime import datetime, timedelta
from src.config.rate_limits import get_rate_limits, get_limit_for_endpoint

logger = logging.getLogger(__name__)

class RateLimiter:
    """Redis-backed rate limiter for fast, distributed rate limiting"""
    
    def __init__(self):
        # Lazy load Redis
        self._redis = None
        
        # Load rate limits from config file
        self.limits = get_rate_limits()
        logger.info("✅ Rate limits loaded from config")
        
    @property
    def redis(self):
        """Lazy load Redis client"""
        if self._redis is None:
            try:
                from src.database.redis_client import get_redis_client
                self._redis = get_redis_client()
                logger.info("✅ Redis connected for rate limiting")
            except Exception as e:
                logger.warning(f"⚠️ Redis unavailable, rate limiting disabled: {e}")
                self._redis = None
        return self._redis
    
    def check_rate_limit(self, identifier: str, endpoint_type: str = "default") -> bool:
        """
        Check if request is within rate limits using Redis
        
        Args:
            identifier: Unique identifier (user email, agent_id, or IP)
            endpoint_type: Type of endpoint (query, feedback, ticket, default)
            
        Returns:
            bool: True if within limits, False if exceeded
        """
        if not self.redis:
            logger.warning("⚠️ Redis unavailable, rate limiting bypassed")
            return True
        
        limit_config = get_limit_for_endpoint(endpoint_type)
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Redis key format: rate_limit:{endpoint_type}:{identifier}
        redis_key = f"rate_limit:{endpoint_type}:{identifier}"
        
        try:
            # Get current count
            current_count = self.redis.get(redis_key)
            
            if current_count is None:
                # First request - initialize counter
                self.redis.setex(redis_key, window_seconds, 1)
                return True
            
            current_count = int(current_count)
            
            # Check if limit exceeded
            if current_count >= max_requests:
                logger.warning(
                    f"⚠️ Rate limit exceeded for {identifier} on {endpoint_type}: "
                    f"{current_count}/{max_requests}"
                )
                return False
            
            # Increment counter
            self.redis.incr(redis_key)
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis rate limit check failed: {e}")
            # On error, allow the request (fail open)
            return True
    
    def get_rate_limit_info(self, identifier: str, endpoint_type: str = "default") -> Dict:
        """
        Get current rate limit status
        
        Args:
            identifier: Unique identifier
            endpoint_type: Type of endpoint
            
        Returns:
            Dict with limit, remaining, reset_time, window_seconds
        """
        if not self.redis:
            return {
                "limit": 0,
                "remaining": 0,
                "reset_time": 0,
                "window_seconds": 0,
                "available": False
            }
        
        limit_config = get_limit_for_endpoint(endpoint_type)
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        redis_key = f"rate_limit:{endpoint_type}:{identifier}"
        
        try:
            current_count = self.redis.get(redis_key)
            ttl = self.redis.ttl(redis_key)
            
            if current_count is None:
                current_count = 0
                reset_time = int(time.time()) + window_seconds
            else:
                current_count = int(current_count)
                reset_time = int(time.time()) + (ttl if ttl > 0 else window_seconds)
            
            return {
                "limit": max_requests,
                "remaining": max(0, max_requests - current_count),
                "reset_time": reset_time,
                "window_seconds": window_seconds,
                "available": True
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get rate limit info: {e}")
            return {
                "limit": max_requests,
                "remaining": max_requests,
                "reset_time": int(time.time()) + window_seconds,
                "window_seconds": window_seconds,
                "available": False
            }
    
    def reset_rate_limit(self, identifier: str, endpoint_type: str = "default") -> bool:
        """
        Reset rate limit for a specific identifier (admin function)
        
        Args:
            identifier: Unique identifier
            endpoint_type: Type of endpoint
            
        Returns:
            bool: Success status
        """
        if not self.redis:
            return False
        
        redis_key = f"rate_limit:{endpoint_type}:{identifier}"
        
        try:
            self.redis.delete(redis_key)
            logger.info(f"✅ Reset rate limit for {identifier} on {endpoint_type}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to reset rate limit: {e}")
            return False

# Global rate limiter instance
rate_limiter = RateLimiter()

def get_client_identifier(request: Request, user_email: Optional[str] = None, agent_id: Optional[str] = None) -> str:
    """
    Get unique identifier for rate limiting
    
    Priority:
    1. agent_id (most reliable for logged-in users)
    2. user_email
    3. IP address (fallback for anonymous users)
    
    Args:
        request: FastAPI request object
        user_email: Optional user email
        agent_id: Optional agent ID
        
    Returns:
        str: Identifier in format "type:value"
    """
    if agent_id:
        return f"agent:{agent_id}"
    
    if user_email:
        return f"user:{user_email}"
    
    # Fallback to IP address
    client_ip = request.client.host
    
    # Check for forwarded IP (if behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    
    return f"ip:{client_ip}"

def check_rate_limit(
    request: Request, 
    endpoint_type: str, 
    user_email: Optional[str] = None,
    agent_id: Optional[str] = None
):
    """
    Check rate limits and raise HTTPException if exceeded
    
    Args:
        request: FastAPI request
        endpoint_type: Type of endpoint (query, feedback, ticket, default)
        user_email: Optional user email
        agent_id: Optional agent ID
        
    Raises:
        HTTPException: 429 if rate limit exceeded
        
    Returns:
        Dict: Rate limit info for response headers
    """
    identifier = get_client_identifier(request, user_email, agent_id)
    
    if not rate_limiter.check_rate_limit(identifier, endpoint_type):
        # Get rate limit info for error message
        info = rate_limiter.get_rate_limit_info(identifier, endpoint_type)
        
        # Calculate seconds until reset
        reset_in = max(0, info["reset_time"] - int(time.time()))
        
        raise HTTPException(
            status_code=429,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Too many {endpoint_type} requests. Try again in {reset_in} seconds.",
                "limit": info["limit"],
                "remaining": 0,
                "reset_in_seconds": reset_in
            },
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(info["reset_time"]),
                "Retry-After": str(reset_in)
            }
        )
    
    # Return rate limit info for response headers
    return rate_limiter.get_rate_limit_info(identifier, endpoint_type)
