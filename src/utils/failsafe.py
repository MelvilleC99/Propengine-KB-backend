"""
Fail-safe utilities for preventing infinite loops and handling system failures
"""

import time
import logging
import functools
from typing import Dict, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RequestLimits:
    """Limits for a single request processing"""
    max_duration: int = 60  # Maximum seconds per request
    max_api_calls: int = 10  # Maximum API calls per request  
    max_search_attempts: int = 3  # Maximum search fallback attempts
    max_retry_attempts: int = 3  # Maximum retry attempts for failed operations
    firebase_timeout: int = 10  # Firebase operation timeout
    llm_timeout: int = 30  # LLM API call timeout
    vector_search_timeout: int = 15  # Vector search timeout

class RequestTracker:
    """Tracks resource usage for a single request"""
    
    def __init__(self, request_id: str, limits: RequestLimits = None):
        self.request_id = request_id
        self.limits = limits or RequestLimits()
        self.start_time = time.time()
        self.api_calls = 0
        self.search_attempts = 0
        self.retry_attempts = 0
        self.operations = []  # Track operations for debugging
        
    def check_time_limit(self) -> bool:
        """Check if request has exceeded time limit"""
        elapsed = time.time() - self.start_time
        if elapsed > self.limits.max_duration:
            logger.error(f"Request {self.request_id} exceeded time limit: {elapsed:.2f}s")
            return False
        return True
    
    def check_api_call_limit(self) -> bool:
        """Check if request has exceeded API call limit"""
        if self.api_calls >= self.limits.max_api_calls:
            logger.error(f"Request {self.request_id} exceeded API call limit: {self.api_calls}")
            return False
        return True
    
    def increment_api_calls(self) -> bool:
        """Increment API call count and check limit"""
        self.api_calls += 1
        self.operations.append(f"API call #{self.api_calls} at {time.time():.2f}")
        return self.check_api_call_limit()
    
    def increment_search_attempts(self) -> bool:
        """Increment search attempt count and check limit"""
        self.search_attempts += 1
        self.operations.append(f"Search attempt #{self.search_attempts} at {time.time():.2f}")
        if self.search_attempts >= self.limits.max_search_attempts:
            logger.warning(f"Request {self.request_id} reached max search attempts: {self.search_attempts}")
            return False
        return True
    
    def increment_retry_attempts(self) -> bool:
        """Increment retry attempt count and check limit"""
        self.retry_attempts += 1
        self.operations.append(f"Retry attempt #{self.retry_attempts} at {time.time():.2f}")
        if self.retry_attempts >= self.limits.max_retry_attempts:
            logger.error(f"Request {self.request_id} exceeded retry limit: {self.retry_attempts}")
            return False
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of request tracking"""
        elapsed = time.time() - self.start_time
        return {
            "request_id": self.request_id,
            "elapsed_time": elapsed,
            "api_calls": self.api_calls,
            "search_attempts": self.search_attempts,
            "retry_attempts": self.retry_attempts,
            "within_limits": all([
                elapsed < self.limits.max_duration,
                self.api_calls < self.limits.max_api_calls,
                self.search_attempts < self.limits.max_search_attempts,
                self.retry_attempts < self.limits.max_retry_attempts
            ]),
            "operations": self.operations[-5:]  # Last 5 operations for debugging
        }

class CircuitBreaker:
    """Circuit breaker to prevent cascading failures"""
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half_open
        
    def can_execute(self) -> bool:
        """Check if operation can be executed"""
        if self.state == "closed":
            return True
        elif self.state == "open":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half_open"
                logger.info(f"Circuit breaker {self.name} transitioning to half-open")
                return True
            return False
        elif self.state == "half_open":
            return True
        return False
    
    def record_success(self):
        """Record successful operation"""
        if self.state == "half_open":
            self.state = "closed"
            self.failure_count = 0
            logger.info(f"Circuit breaker {self.name} recovered - transitioning to closed")
    
    def record_failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.error(f"Circuit breaker {self.name} opened after {self.failure_count} failures")

class SafeExecutor:
    """Safe execution wrapper for operations that might fail or loop"""
    
    def __init__(self):
        self.circuit_breakers = {}
    
    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create circuit breaker for operation"""
        if name not in self.circuit_breakers:
            self.circuit_breakers[name] = CircuitBreaker(name)
        return self.circuit_breakers[name]
    
    def safe_execute(self, 
                    operation_name: str,
                    operation: Callable,
                    tracker: RequestTracker,
                    timeout: int = 30,
                    *args, **kwargs) -> tuple[bool, Any]:
        """Safely execute an operation with all fail-safes"""
        
        # Check circuit breaker
        circuit_breaker = self.get_circuit_breaker(operation_name)
        if not circuit_breaker.can_execute():
            logger.error(f"Circuit breaker {operation_name} is open - operation blocked")
            return False, f"Service temporarily unavailable: {operation_name}"
        
        # Check request limits
        if not tracker.check_time_limit():
            return False, "Request timeout exceeded"
        
        # Increment appropriate counter based on operation type
        if "api" in operation_name.lower() or "llm" in operation_name.lower():
            if not tracker.increment_api_calls():
                return False, "API call limit exceeded"
        elif "search" in operation_name.lower():
            if not tracker.increment_search_attempts():
                return False, "Search attempt limit exceeded"
        
        try:
            # Execute with timeout
            start_time = time.time()
            result = operation(*args, **kwargs)
            execution_time = time.time() - start_time
            
            # Log performance
            logger.info(f"Operation {operation_name} completed in {execution_time:.2f}s")
            
            # Record success
            circuit_breaker.record_success()
            return True, result
            
        except Exception as e:
            # Record failure
            circuit_breaker.record_failure()
            logger.error(f"Operation {operation_name} failed: {str(e)}")
            return False, f"Operation failed: {str(e)}"

# Global safe executor instance
safe_executor = SafeExecutor()

def with_failsafe(operation_name: str, timeout: int = 30):
    """Decorator to add fail-safe protection to functions"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract or create request tracker
            tracker = kwargs.pop('request_tracker', None)
            if not tracker:
                import uuid
                tracker = RequestTracker(str(uuid.uuid4()))
            
            success, result = safe_executor.safe_execute(
                operation_name, func, tracker, timeout, *args, **kwargs
            )
            
            if not success:
                raise Exception(f"Fail-safe triggered: {result}")
            
            return result
        return wrapper
    return decorator

def create_request_tracker(request_id: Optional[str] = None) -> RequestTracker:
    """Create a new request tracker"""
    if not request_id:
        import uuid
        request_id = str(uuid.uuid4())
    return RequestTracker(request_id)

def get_system_status() -> Dict[str, Any]:
    """Get overall system status including circuit breaker states"""
    circuit_breaker_status = {}
    for name, cb in safe_executor.circuit_breakers.items():
        circuit_breaker_status[name] = {
            "state": cb.state,
            "failure_count": cb.failure_count,
            "last_failure": cb.last_failure_time
        }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "circuit_breakers": circuit_breaker_status,
        "active_circuit_breakers": len(safe_executor.circuit_breakers)
    }
