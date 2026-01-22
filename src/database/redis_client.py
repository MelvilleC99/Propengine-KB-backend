"""Redis Connection Manager

Manages Redis connection pool with singleton pattern.
"""

import os
import redis
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisConnection:
    """Singleton Redis connection manager"""
    
    _instance: Optional['RedisConnection'] = None
    _client: Optional[redis.Redis] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize Redis connection (only once)"""
        if self._client is None:
            self._connect()
    
    def _connect(self):
        """Create Redis connection pool"""
        try:
            redis_host = os.getenv('REDIS_HOST')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD')
            redis_db = int(os.getenv('REDIS_DB', 0))
            redis_ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'
            
            logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")
            
            # Create connection pool
            self._client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                ssl=redis_ssl,
                decode_responses=True,  # Return strings instead of bytes
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
                max_connections=50  # Connection pool size
            )
            
            # Test connection
            self._client.ping()
            
            logger.info("✅ Redis connection established")
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            raise
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client"""
        if self._client is None:
            self._connect()
        return self._client
    
    def ping(self) -> bool:
        """Test Redis connection"""
        try:
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False
    
    def close(self):
        """Close Redis connection"""
        if self._client:
            self._client.close()
            self._client = None
            logger.info("Redis connection closed")


# Global singleton instance
redis_connection = RedisConnection()


def get_redis_client() -> redis.Redis:
    """Get Redis client instance"""
    return redis_connection.client
