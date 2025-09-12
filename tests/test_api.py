"""Unit tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_root_endpoint():
    """Test root endpoint returns correct information"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "PropEngine Support Agent"
    assert "version" in data
    assert "endpoints" in data

def test_health_check():
    """Test health check endpoint"""
    response = client.get("/api/chat/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "services" in data
    assert data["status"] in ["healthy", "degraded", "unhealthy"]

def test_chat_endpoint():
    """Test chat endpoint with a simple query"""
    payload = {
        "message": "Hello"
    }
    response = client.post("/api/chat/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "session_id" in data
    assert "confidence" in data
    assert "sources" in data
    assert "query_type" in data

def test_chat_with_session():
    """Test chat endpoint with session continuity"""
    # First message
    payload1 = {"message": "Hello"}
    response1 = client.post("/api/chat/", json=payload1)
    assert response1.status_code == 200
    session_id = response1.json()["session_id"]
    
    # Second message with same session
    payload2 = {
        "message": "What is a levy?",
        "session_id": session_id
    }
    response2 = client.post("/api/chat/", json=payload2)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["session_id"] == session_id

def test_admin_stats():
    """Test admin statistics endpoint"""
    response = client.get("/api/admin/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_sessions" in data
    assert "active_sessions" in data
    assert "total_messages" in data

def test_get_sessions():
    """Test get sessions endpoint"""
    response = client.get("/api/admin/sessions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_session_not_found():
    """Test getting non-existent session"""
    response = client.get("/api/chat/session/non-existent-id")
    assert response.status_code == 404
