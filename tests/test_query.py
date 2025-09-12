"""Unit tests for vector search functionality"""

import pytest
from src.query.vector_search import VectorSearch

@pytest.mark.asyncio
async def test_vector_search_initialization():
    """Test vector search initialization"""
    search = VectorSearch()
    assert search.embeddings is not None
    assert len(search.collection_configs) == 4

@pytest.mark.asyncio
async def test_query_cleaning():
    """Test query cleaning functionality"""
    search = VectorSearch()
    
    # Test removal of stop words
    cleaned = search.clean_query("What is a home owner levy?")
    assert "what" not in cleaned.lower()
    assert "is" not in cleaned.lower()
    assert "home" in cleaned.lower()
    assert "owner" in cleaned.lower()
    assert "levy" in cleaned.lower()

@pytest.mark.asyncio
async def test_search_definitions():
    """Test searching definitions collection"""
    search = VectorSearch()
    results = await search.search(
        query="home owner levy",
        collection_type="definitions",
        k=3
    )
    
    # Check result structure
    if results:
        assert isinstance(results, list)
        for result in results:
            assert "content" in result
            assert "metadata" in result
            assert "collection" in result
            assert result["collection"] == "definitions"

@pytest.mark.asyncio
async def test_search_workflows():
    """Test searching workflows collection"""
    search = VectorSearch()
    results = await search.search(
        query="property management",
        collection_type="workflows",
        k=3
    )
    
    # Check result structure
    if results:
        assert isinstance(results, list)
        for result in results:
            assert "content" in result
            assert "metadata" in result
            assert "collection" in result
            assert result["collection"] == "workflows"

@pytest.mark.asyncio
async def test_content_extraction():
    """Test content extraction from different document formats"""
    search = VectorSearch()
    
    # Create mock document with page_content
    class MockDoc:
        def __init__(self):
            self.page_content = "Test content"
            self.metadata = {"key": "value"}
    
    doc = MockDoc()
    content = search.extract_content(doc, "page_content")
    assert content == "Test content"
    
    # Test with content in metadata
    doc.metadata["content"] = "Metadata content"
    content = search.extract_content(doc, "content")
    assert content == "Metadata content"
