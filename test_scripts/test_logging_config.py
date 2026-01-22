"""
Test logging configuration for debugging session management

Add this to your main.py or create a separate test file
"""

import logging

# Create specific loggers for testing
def setup_test_logging():
    """Setup detailed logging for testing"""
    
    # Root logger
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
    )
    
    # Specific loggers for components we want to test
    session_logger = logging.getLogger('src.memory.session_manager')
    session_logger.setLevel(logging.DEBUG)
    
    cache_logger = logging.getLogger('src.memory.context_cache')
    cache_logger.setLevel(logging.DEBUG)
    
    summary_logger = logging.getLogger('src.utils.chat_summary')
    summary_logger.setLevel(logging.DEBUG)
    
    firebase_logger = logging.getLogger('src.database.firebase_session_service')
    firebase_logger.setLevel(logging.DEBUG)
    
    # Create file handler for persistent logs
    file_handler = logging.FileHandler('test_session_management.log')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    
    # Add handler to all loggers
    for logger in [session_logger, cache_logger, summary_logger, firebase_logger]:
        logger.addHandler(file_handler)
    
    print("✅ Test logging configured. Logs saved to: test_session_management.log")


# Usage:
# from test_logging_config import setup_test_logging
# setup_test_logging()
