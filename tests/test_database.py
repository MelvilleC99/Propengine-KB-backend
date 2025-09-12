"""Unit tests for database connection"""

import pytest
import asyncio
from src.database.connection import AstraDBConnection

@pytest.mark.asyncio
async def test_database_connection():
    """Test that database connection initializes properly"""
    db = AstraDBConnection()
    assert db.token is not None
    assert db.endpoint is not None
    assert db.keyspace == "default_keyspace"

@pytest.mark.asyncio
async def test_connection_health_check():
    """Test connection health check to all collections"""
    db = AstraDBConnection()
    results = await db.test_connection()
    
    # Should have results for all 4 collections
    assert len(results) == 4
    assert "definitions" in results
    assert "errors" in results
    assert "howto" in results
    assert "workflows" in results

def test_get_status():
    """Test database status check"""
    db = AstraDBConnection()
    status = db.get_status()
    assert status in ["connected", "disconnected"]
    # Should be connected if credentials are present
    if db.token and db.endpoint:
        assert status == "connected"
