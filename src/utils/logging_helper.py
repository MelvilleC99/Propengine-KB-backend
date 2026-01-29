"""
Structured Logging Utility for PropertyEngine KB

Provides consistent, structured logging across the application with
context-aware debug information.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime


class StructuredLogger:
    """
    Structured logger that provides consistent formatting and debug helpers
    
    Usage:
        from src.utils.logging_helper import get_logger
        
        logger = get_logger(__name__)
        logger.log_context_retrieval(session_id, message_count, context_length)
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    # === SESSION & CONTEXT LOGGING ===
    
    def log_session_start(self, session_id: str, user_info: Optional[Dict] = None):
        """Log session creation"""
        self.logger.info(
            f"🆕 Session created: {session_id} | "
            f"User: {user_info.get('email', 'unknown') if user_info else 'anonymous'}"
        )
    
    def log_message_stored(self, session_id: str, role: str, content_preview: str):
        """Log message storage"""
        preview = content_preview[:60] + "..." if len(content_preview) > 60 else content_preview
        self.logger.debug(f"💾 Message stored [{role}] in {session_id}: {preview}")
    
    def log_context_retrieval(
        self, 
        session_id: str, 
        message_count: int, 
        context_length: int,
        has_summary: bool = False
    ):
        """Log context retrieval for debugging"""
        self.logger.info(
            f"🔍 Context retrieved for {session_id} | "
            f"Messages: {message_count} | "
            f"Length: {context_length} chars | "
            f"Summary: {'Yes' if has_summary else 'No'}"
        )
    
    def log_context_preview(self, session_id: str, context_preview: str):
        """Log a preview of the context being sent to LLM"""
        self.logger.debug(
            f"📄 Context preview for {session_id}:\n"
            f"{context_preview[:300]}..."
        )
    
    def log_context_empty(self, session_id: str, reason: str = "unknown"):
        """Log when context is empty (potential problem)"""
        self.logger.warning(
            f"⚠️  Empty context for {session_id} | Reason: {reason}"
        )
    
    def log_session_end(self, session_id: str, reason: str, query_count: int):
        """Log session ending"""
        self.logger.info(
            f"🔚 Session ended: {session_id} | "
            f"Reason: {reason} | "
            f"Queries: {query_count}"
        )
    
    # === QUERY PROCESSING LOGGING ===
    
    def log_query_start(self, session_id: str, query: str):
        """Log query processing start"""
        preview = query[:80] + "..." if len(query) > 80 else query
        self.logger.info(f"🔎 Processing query in {session_id}: {preview}")
    
    def log_query_classification(self, query_type: str, confidence: float):
        """Log query classification"""
        self.logger.info(f"📋 Classified as '{query_type}' (confidence: {confidence:.2f})")
    
    def log_search_results(self, query: str, result_count: int, best_score: float):
        """Log search results"""
        self.logger.info(
            f"🔍 Search completed | "
            f"Results: {result_count} | "
            f"Best score: {best_score:.2f}"
        )
    
    def log_response_generated(self, confidence: float, sources_used: int, time_ms: float):
        """Log response generation"""
        self.logger.info(
            f"✅ Response generated | "
            f"Confidence: {confidence:.2f} | "
            f"Sources: {sources_used} | "
            f"Time: {time_ms:.0f}ms"
        )
    
    # === ERROR LOGGING ===
    
    def log_error(self, operation: str, error: Exception, context: Optional[Dict] = None):
        """Log errors with context"""
        self.logger.error(
            f"❌ Error in {operation}: {str(error)}" +
            (f" | Context: {context}" if context else ""),
            exc_info=True
        )
    
    def log_fallback(self, operation: str, reason: str):
        """Log when falling back to alternative method"""
        self.logger.warning(f"⚠️  Fallback in {operation}: {reason}")
    
    # === REDIS & STORAGE LOGGING ===
    
    def log_redis_connected(self):
        """Log successful Redis connection"""
        self.logger.info("✅ Redis connected")
    
    def log_redis_failed(self, error: str):
        """Log Redis connection failure"""
        self.logger.warning(f"⚠️  Redis unavailable: {error} | Using fallback")
    
    def log_storage_operation(self, operation: str, success: bool, details: str = ""):
        """Log storage operations"""
        status = "✅" if success else "❌"
        self.logger.debug(f"{status} {operation}" + (f" | {details}" if details else ""))
    
    # === ANALYTICS LOGGING ===
    
    def log_analytics_buffered(self, session_id: str, buffer_size: int):
        """Log analytics buffering"""
        self.logger.debug(f"📊 Analytics buffered for {session_id} | Total: {buffer_size}")
    
    def log_analytics_written(self, session_id: str, query_count: int):
        """Log analytics batch write"""
        self.logger.info(f"📊 Analytics written for {session_id} | Queries: {query_count}")
    
    # === GENERIC LOGGING (passthrough to standard logger) ===
    
    def info(self, message: str):
        self.logger.info(message)
    
    def debug(self, message: str):
        self.logger.debug(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        self.logger.error(message, exc_info=exc_info)


# === FACTORY FUNCTION ===

def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance
    
    Usage:
        from src.utils.logging_helper import get_logger
        logger = get_logger(__name__)
    """
    return StructuredLogger(name)


# === USAGE EXAMPLES ===

if __name__ == "__main__":
    # Example usage
    logger = get_logger("example")
    
    logger.log_session_start("test-123", {"email": "user@example.com"})
    logger.log_context_retrieval("test-123", message_count=5, context_length=450)
    logger.log_query_start("test-123", "How do I upload photos?")
    logger.log_response_generated(confidence=0.92, sources_used=3, time_ms=450)
