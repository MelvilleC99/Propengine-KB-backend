"""Redis Connection Manager

Manages Redis connection with lazy initialization.
Connection is only created when first accessed, not at import time.
This prevents connection leaks during uvicorn --reload.
"""

import os
import redis
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class RedisConnection:
    """Lazy Redis connection manager — connects on first use, not on import"""

    _instance: Optional['RedisConnection'] = None
    _client: Optional[redis.Redis] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        # Don't connect here — wait until .client is accessed
        pass

    def _connect(self):
        """Create Redis connection pool (called lazily on first access)"""
        try:
            redis_host = os.getenv('REDIS_HOST')
            redis_port = int(os.getenv('REDIS_PORT', 6379))
            redis_password = os.getenv('REDIS_PASSWORD')
            redis_db = int(os.getenv('REDIS_DB', 0))
            redis_ssl = os.getenv('REDIS_SSL', 'false').lower() == 'true'

            logger.info(f"Connecting to Redis at {redis_host}:{redis_port}")

            # Create connection pool - use SINGLE connection to avoid hitting server max-client limits
            # Cloud Run can scale to 10 instances, so 1 connection × 10 = 10 max (safe for free tier)
            self._client = redis.Redis(
                host=redis_host,
                port=redis_port,
                password=redis_password,
                db=redis_db,
                ssl=redis_ssl,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=10,  # Timeout idle connections faster
                socket_keepalive=True,
                health_check_interval=15,  # Check health more frequently
                max_connections=1,  # Single connection per instance
                retry_on_timeout=True
            )

            # Test connection
            self._client.ping()

            logger.info("✅ Redis connection established")

        except Exception as e:
            logger.error(f"❌ Failed to connect to Redis: {e}")
            self._client = None
            raise

    @property
    def client(self) -> redis.Redis:
        """Get Redis client — connects lazily on first access"""
        if self._client is None:
            self._connect()
        return self._client

    def ping(self) -> bool:
        """Test Redis connection"""
        try:
            if self._client is None:
                return False
            return self._client.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    def close(self):
        """Close Redis connection and release pool"""
        if self._client:
            try:
                self._client.close()
                self._client.connection_pool.disconnect()
            except Exception as e:
                logger.debug(f"Redis close error: {e}")
            self._client = None
            logger.info("Redis connection closed")


# Global singleton — does NOT connect at import time anymore
redis_connection = RedisConnection()


def get_redis_client() -> redis.Redis:
    """Get Redis client instance (connects lazily on first call)"""
    return redis_connection.client
