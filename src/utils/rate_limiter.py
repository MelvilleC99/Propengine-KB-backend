"""Rate limiting for PropertyEngine KB API"""

import time
import logging
from typing import Dict, Optional
from collections import defaultdict, deque
from fastapi import HTTPException, Request
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RateLimiter:
    """Simple in-memory rate limiter"""
    
    def __init__(self):
        # Store request timestamps per identifier (IP or user)
        self.requests: Dict[str, deque] = defaultdict(deque)
        
        # Rate limit configurations
        self.limits = {
            "chat": {"requests": 20, "window": 1800},     # 20 requests per 30 minutes
            "feedback": {"requests": 10, "window": 300},   # 10 feedback per 5 minutes
            "ticket": {"requests": 3, "window": 900},      # 3 tickets per 15 minutes
            "default": {"requests": 50, "window": 300}     # 50 requests per 5 minutes default
        }
    
    def check_rate_limit(self, identifier: str, endpoint_type: str = "default") -> bool:
        """Check if request is within rate limits"""
        now = time.time()
        limit_config = self.limits.get(endpoint_type, self.limits["default"])
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        # Get request history for this identifier
        request_times = self.requests[identifier]
        
        # Remove old requests outside the time window
        while request_times and request_times[0] < now - window_seconds:
            request_times.popleft()
        
        # Check if within limits
        if len(request_times) >= max_requests:
            logger.warning(f"Rate limit exceeded for {identifier} on {endpoint_type}: {len(request_times)}/{max_requests}")
            return False
        
        # Add current request
        request_times.append(now)
        return True
    
    def get_rate_limit_info(self, identifier: str, endpoint_type: str = "default") -> Dict:
        """Get current rate limit status"""
        now = time.time()
        limit_config = self.limits.get(endpoint_type, self.limits["default"])
        max_requests = limit_config["requests"]
        window_seconds = limit_config["window"]
        
        request_times = self.requests[identifier]
        
        # Count requests in current window
        current_requests = len([t for t in request_times if t > now - window_seconds])
        
        return {
            "limit": max_requests,
            "remaining": max(0, max_requests - current_requests),
            "reset_time": int(now + window_seconds),
            "window_seconds": window_seconds
        }
    
    def cleanup_old_requests(self):
        """Cleanup old request records (call periodically)"""
        now = time.time()
        cutoff = now - 3600  # Remove requests older than 1 hour
        
        for identifier in list(self.requests.keys()):
            request_times = self.requests[identifier]
            while request_times and request_times[0] < cutoff:
                request_times.popleft()
            
            # Remove empty deques
            if not request_times:
                del self.requests[identifier]

# Global rate limiter instance
rate_limiter = RateLimiter()

def get_client_identifier(request: Request, user_email: Optional[str] = None) -> str:
    """Get unique identifier for rate limiting (prefer user email over IP)"""
    if user_email:
        return f"user:{user_email}"
    
    # Fallback to IP address
    client_ip = request.client.host
    
    # Check for forwarded IP (if behind proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    
    return f"ip:{client_ip}"

def check_rate_limit(request: Request, endpoint_type: str, user_email: Optional[str] = None):
    """Decorator/function to check rate limits and raise HTTPException if exceeded"""
    identifier = get_client_identifier(request, user_email)
    
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
                "reset_in_seconds": reset_in
            },
            headers={
                "X-RateLimit-Limit": str(info["limit"]),
                "X-RateLimit-Remaining": str(info["remaining"]),
                "X-RateLimit-Reset": str(info["reset_time"]),
                "Retry-After": str(reset_in)
            }
        )
    
    # Return rate limit info for response headers
    return rate_limiter.get_rate_limit_info(identifier, endpoint_type)
